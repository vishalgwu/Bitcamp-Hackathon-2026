import whisper
import os
import sys


def generate_transcript(filename):
    # 1. Absolute Path Check
    downloads_path = os.path.join(os.environ['USERPROFILE'], "Downloads")
    video_path = os.path.join(downloads_path, filename)

    print(f"DEBUG: Looking for file at: {video_path}")

    if not os.path.exists(video_path):
        return f"ERROR: File not found at {video_path}. Check the filename and extension!"

    # 2. Model Loading (This can take a minute the first time)
    print("DEBUG: Loading Whisper model 'base' (checking internet/cache)...")
    try:
        model = whisper.load_model("base")
    except Exception as e:
        return f"ERROR during model load: {e}"

    # 3. Transcription
    print("DEBUG: Starting transcription... (this will take time, please wait)")
    result = model.transcribe(video_path, verbose=False, fp16=False)

    return result["text"].strip()


if __name__ == "__main__":
    # IMPORTANT: Check if your file is actually named .mp4 or .mkv or .webm
    file_name = "videoplayback.mp4"

    print("--- SCRIPT START ---")
    try:
        transcript = generate_transcript(file_name)
        print("\n--- FINAL TRANSCRIPT ---\n")
        print(transcript)
    except Exception as e:
        print(f"CRITICAL SYSTEM ERROR: {e}")
    print("\n--- SCRIPT FINISHED ---")