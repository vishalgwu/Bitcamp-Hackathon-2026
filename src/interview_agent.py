# interview_agent.py
import os
import time
import math
import tempfile
import subprocess
import imageio_ffmpeg
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
]

# Gemini Files API supports up to 2GB per file
# We split only when a single chunk would exceed this
# Longer chunks = fewer uploads = faster + less quota usage
GEMINI_FILE_LIMIT_MB  = 1800   # stay safely under 2GB
CHUNK_DURATION_SECS   = 600    # 10 min per chunk (most interviews = 1-2 chunks)
COMPRESS_THRESHOLD_MB = 500    # compress if above this before splitting


def get_video_duration(input_path):
    """Get video duration in seconds using ffmpeg."""
    result = subprocess.run(
        [FFMPEG, "-i", input_path],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    output = result.stderr.decode("utf-8", errors="ignore")
    for line in output.split("\n"):
        if "Duration" in line:
            try:
                time_str = line.strip().split("Duration:")[1].split(",")[0].strip()
                h, m, s  = time_str.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except:
                pass
    return 0


def compress_video(input_path, output_path):
    """
    Compress video to reduce file size before uploading.
    Scales to 480p and uses high CRF — audio quality is kept
    reasonable since we only need speech for transcription.
    """
    print(f"  Compressing video...")
    subprocess.run([
        FFMPEG, "-y",
        "-i", input_path,
        "-vf", "scale=-2:480",
        "-c:v", "libx264",
        "-crf", "35",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        output_path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        print(f"  Compression failed — using original")
        return input_path

    orig_mb  = os.path.getsize(input_path)  / (1024 * 1024)
    compr_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  Compressed: {orig_mb:.0f}MB -> {compr_mb:.0f}MB")
    return output_path


def split_video(input_path, chunk_duration=600):
    """
    Split video into chunks using stream copy (no re-encode = fast).
    Falls back to re-encode only if stream copy fails.
    """
    duration    = get_video_duration(input_path)
    num_chunks  = math.ceil(duration / chunk_duration)
    chunk_paths = []
    base        = os.path.splitext(input_path)[0]

    print(f"  Duration: {duration:.0f}s — splitting into {num_chunks} chunk(s) of {chunk_duration//60} min...")

    for i in range(num_chunks):
        start      = i * chunk_duration
        chunk_path = f"{base}_chunk{i}.mp4"

        # Try stream copy first — fast, no quality loss
        subprocess.run([
            FFMPEG, "-y",
            "-i", input_path,
            "-ss", str(start),
            "-t",  str(chunk_duration),
            "-c",  "copy",
            "-avoid_negative_ts", "make_zero",
            chunk_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Fallback to re-encode if stream copy produced empty file
        if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) < 1000:
            print(f"  Stream copy failed for chunk {i+1} — re-encoding...")
            subprocess.run([
                FFMPEG, "-y",
                "-i", input_path,
                "-ss", str(start),
                "-t",  str(chunk_duration),
                "-c:v", "libx264",
                "-crf", "35",
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "64k",
                chunk_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 1000:
            size_mb = os.path.getsize(chunk_path) / (1024 * 1024)
            chunk_paths.append(chunk_path)
            print(f"  Chunk {i+1}/{num_chunks} ready ({size_mb:.0f}MB)")
        else:
            print(f"  Chunk {i+1} failed to create — skipping")

    return chunk_paths


def upload_and_wait(file_path, mime_type, retries=3):
    """Upload file to Gemini Files API and wait for processing."""
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    print(f"  Uploading {size_mb:.0f}MB to Gemini...")

    for attempt in range(retries):
        try:
            video_file = genai.upload_file(path=file_path, mime_type=mime_type)

            wait_secs = 0
            while video_file.state.name == "PROCESSING":
                time.sleep(3)
                wait_secs += 3
                video_file = genai.get_file(video_file.name)
                if wait_secs % 15 == 0:
                    print(f"  Processing... ({wait_secs}s elapsed)")

            if video_file.state.name == "FAILED":
                raise ValueError(f"Gemini failed to process file")

            print(f"  Upload ready")
            return video_file

        except Exception as e:
            if attempt < retries - 1:
                print(f"  Upload attempt {attempt+1} failed: {str(e)[:60]} — retrying in 10s...")
                time.sleep(10)
            else:
                raise e


def transcribe_chunk(video_file, chunk_index, role, total_chunks):
    """Transcribe a single video chunk."""
    part_label = (
        f"part {chunk_index + 1} of {total_chunks}"
        if total_chunks > 1
        else "the full interview"
    )
    prompt = f"""This is {part_label} of a job interview for the role of {role}.

Transcribe ONLY the speech in this video segment.
Label each speaker as Speaker 1 (interviewer) or Speaker 2 (candidate).

Format each line exactly as:
Speaker 1: [what they said]
Speaker 2: [what they said]

Do not add any analysis, commentary, headers, or extra text. Just the transcript lines."""

    for model_name in MODELS:
        try:
            model    = genai.GenerativeModel(model_name)
            response = model.generate_content(
                [video_file, prompt],
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=4000
                )
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            print(f"  {model_name} failed for chunk {chunk_index+1}: {err[:60]}")
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                print(f"  Quota hit — waiting 45s...")
                time.sleep(45)
            else:
                time.sleep(3)
            continue

    raise Exception(f"All models failed for chunk {chunk_index+1}")


def analyze_full_transcript(transcript, role):
    """Analyze full transcript and return scores + feedback."""
    prompt = f"""You are an expert technical interview evaluator with years of experience assessing candidates for top tech companies.

Below is the full transcript of a job interview for the role of: {role}

Speaker 1 is the interviewer. Speaker 2 is the candidate.

IMPORTANT INSTRUCTIONS:
- Evaluate ONLY Speaker 2 (the candidate), not the interviewer
- Be strict and honest — a poor performance MUST score low, a great performance scores high
- Base your evaluation purely on the transcript content
- Do not hallucinate or assume anything not present in the transcript
- If the candidate stammers, gives wrong answers, or deflects questions, score them low
- The RECOMMENDATION must strictly follow these thresholds:
  * HIRE: overall score 75 and above
  * CONSIDER: overall score between 45 and 74
  * REJECT: overall score below 45

Evaluate the candidate on these 5 dimensions, each scored 0 to 100:

1. TECHNICALITY — How technically accurate and knowledgeable are the answers?
2. PROBLEM_SOLVING — Does the candidate think through problems logically?
3. COMMUNICATION — Is the candidate clear and articulate? Do they use excessive filler words?
4. PERSONALITY — Does the candidate come across as enthusiastic and professional?
5. CONFIDENCE — Does the candidate speak with conviction or hesitate excessively?

Return ONLY the following format. Every field on its own line. No extra text before or after:

OVERALL_SCORE: [0-100]
TECHNICALITY: [0-100]
PROBLEM_SOLVING: [0-100]
COMMUNICATION: [0-100]
PERSONALITY: [0-100]
CONFIDENCE: [0-100]
SUMMARY: [2-3 complete sentences summarizing the candidate's overall interview performance]
TECHNICALITY_FEEDBACK: [1-2 complete sentences explaining specifically why this score was given]
PROBLEM_SOLVING_FEEDBACK: [1-2 complete sentences explaining specifically why this score was given]
COMMUNICATION_FEEDBACK: [1-2 complete sentences explaining specifically why this score was given]
PERSONALITY_FEEDBACK: [1-2 complete sentences explaining specifically why this score was given]
CONFIDENCE_FEEDBACK: [1-2 complete sentences explaining specifically why this score was given]
RECOMMENDATION: [HIRE / CONSIDER / REJECT]

TRANSCRIPT:
{transcript}
"""

    for model_name in MODELS:
        try:
            print(f"  Analyzing with {model_name}...")
            model    = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=4000
                )
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            print(f"  {model_name} failed: {err[:60]}")
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                print(f"  Quota hit — waiting 45s...")
                time.sleep(45)
            else:
                time.sleep(3)
            continue

    raise Exception("All models failed for analysis.")


def parse_results(raw_output):
    """Parse structured output from Gemini into a dictionary."""
    results = {}
    lines   = raw_output.strip().split("\n")

    for line in lines:
        if ":" in line:
            key, _, value = line.partition(":")
            key   = key.strip()
            value = value.strip()
            if key and value:
                results[key] = value

    score_keys = [
        "OVERALL_SCORE", "TECHNICALITY", "PROBLEM_SOLVING",
        "COMMUNICATION", "PERSONALITY", "CONFIDENCE"
    ]
    for key in score_keys:
        if key in results:
            try:
                results[key] = int(results[key])
            except ValueError:
                results[key] = 0

    return results


def run_interview_agent(video_bytes=None, role="", file_extension=".mp4", local_path=None):
    """
    Full pipeline — handles files of ANY size:

    1. Write to disk (or use local path directly — no memory load for big files)
    2. Compress to 480p if > 500MB  (shrinks 200MB -> ~40MB typically)
    3. Split into 10-min chunks only if still > 1800MB after compression
    4. Upload each chunk to Gemini Files API (supports up to 2GB per file)
    5. Transcribe each chunk
    6. Analyze full assembled transcript
    7. Return scores + feedback
    """

    tmp_path     = None
    owns_tmp     = False
    work_path    = None
    chunk_paths  = []
    gemini_files = []

    try:
        # ── Step 1: Write bytes to disk or use local path ─────────────────────
        if local_path:
            tmp_path       = local_path
            owns_tmp       = False
            file_extension = "." + local_path.rsplit(".", 1)[-1]
            print(f"Using local file: {local_path}")
        else:
            suffix   = file_extension if file_extension.startswith(".") else f".{file_extension}"
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp_file.write(video_bytes)
            tmp_file.close()
            tmp_path = tmp_file.name
            owns_tmp = True

        size_mb   = os.path.getsize(tmp_path) / (1024 * 1024)
        mime      = f"video/{file_extension.lstrip('.')}"
        work_path = tmp_path

        print(f"Video: {size_mb:.0f}MB")

        # ── Step 2: Compress if large ─────────────────────────────────────────
        if size_mb > COMPRESS_THRESHOLD_MB:
            compressed_path = tmp_path.rsplit(".", 1)[0] + "_compressed.mp4"
            work_path = compress_video(tmp_path, compressed_path)
            mime      = "video/mp4"

        work_size_mb = os.path.getsize(work_path) / (1024 * 1024)

        # ── Step 3: Split only if still over Gemini limit ─────────────────────
        if work_size_mb > GEMINI_FILE_LIMIT_MB:
            print(f"Still {work_size_mb:.0f}MB after compression — splitting...")
            chunk_paths   = split_video(work_path, CHUNK_DURATION_SECS)
            files_to_send = chunk_paths
        else:
            files_to_send = [work_path]

        total_chunks = len(files_to_send)
        print(f"Processing {total_chunks} file(s)...")

        # ── Step 4 + 5: Upload + transcribe each file ─────────────────────────
        all_transcripts = []
        for i, file_path in enumerate(files_to_send):
            chunk_mb = os.path.getsize(file_path) / (1024 * 1024)
            label    = f"chunk {i+1}/{total_chunks}" if total_chunks > 1 else "file"
            print(f"\n[{label}] {chunk_mb:.0f}MB")

            video_file = upload_and_wait(
                file_path,
                "video/mp4" if file_path.endswith(".mp4") else mime
            )
            gemini_files.append(video_file)

            chunk_transcript = transcribe_chunk(video_file, i, role, total_chunks)
            all_transcripts.append(chunk_transcript)
            print(f"  Chunk {i+1} transcribed ({len(chunk_transcript)} chars)")

            if i < total_chunks - 1:
                time.sleep(2)

        transcript = "\n".join(all_transcripts)
        print(f"\nTranscript complete: {len(transcript)} chars")

        # ── Step 6: Analyze ───────────────────────────────────────────────────
        print("\nAnalyzing interview performance...")
        raw_output = analyze_full_transcript(transcript, role)
        results    = parse_results(raw_output)
        results["TRANSCRIPT"] = transcript

        # Override recommendation based on score
        score = results.get("OVERALL_SCORE", 0)
        if score >= 75:
            results["RECOMMENDATION"] = "HIRE"
        elif score >= 45:
            results["RECOMMENDATION"] = "CONSIDER"
        else:
            results["RECOMMENDATION"] = "REJECT"

        return results

    finally:
        # ── Cleanup Gemini files ──────────────────────────────────────────────
        for gf in gemini_files:
            try:
                genai.delete_file(gf.name)
                print(f"Deleted Gemini file: {gf.name}")
            except:
                pass

        # ── Cleanup local temp files ──────────────────────────────────────────
        if owns_tmp and tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

        if work_path and work_path != tmp_path and os.path.exists(work_path):
            try:
                os.unlink(work_path)
            except:
                pass

        for cp in chunk_paths:
            if os.path.exists(cp):
                try:
                    os.unlink(cp)
                except:
                    pass