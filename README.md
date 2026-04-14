#  hire.ai — Beyond the Resume. The Full Picture.

##  Inspiration

Hiring today often misses the full picture. Resumes are skimmed in seconds, GitHub profiles are overlooked, and interview feedback can be subjective.

We’ve experienced this from both sides:
- As candidates who were overlooked despite strong work
- As engineers who know a resume cannot capture real capability

### Key Problems:
-  Resumes get only a few seconds of attention  
-  GitHub and real work are often ignored  
-  Interview feedback can vary significantly  
-  Strong candidates can be overlooked  

---

##  What It Does

**hire.ai** is a multi-agent AI hiring platform that evaluates candidates holistically—going beyond resumes to analyze real work, job fit, and interview performance.

###  Core Features:
-  Resume parsing with structured insights  
-  GitHub scraping and real code evaluation  
-  Job-role matching with detailed scoring  
-  AI-based interview analysis  

###  Output:
- Match score  
- Strengths  
- Skill gaps  
- Skill coverage  

---

##  How We Built It

We designed hire.ai using a **multi-agent architecture**, where each agent specializes in a specific evaluation task.

###  Tech Stack:
- **Frontend & App:** Python, Streamlit  
- **LLMs & Reasoning:** Gemini API, LLaMA 3.3 (via Groq)  
- **Data Sources:** GitHub API  
- **Audio/Video:** Whisper, imageio-ffmpeg  
- **Database:** MongoDB  
- **Security:** bcrypt  

---

##  Challenges We Ran Into

Building a system that integrates multiple AI models and data sources in a short time wasn’t easy:

- Extracting meaningful insights from raw GitHub code  
- Handling API rate limits and authentication  
- Maintaining consistent scoring across agents  
- Processing and transcribing interviews accurately  
- Integrating everything into a seamless UI  

---

##  Accomplishments We're Proud Of

-  Built a complete multi-agent system in **24 hours**  
-  Combined resume, GitHub, and interview evaluation  
-  Developed an evidence-based scoring approach  
-  Delivered a clean and interactive UI  
-  Tackled a real-world hiring problem  

---

##  What We Learned

-  Multi-agent systems simplify complex workflows  
-  Real hiring evaluation requires multiple data sources  
-  LLMs are powerful when combined with structured pipelines  
-  Balancing speed and reliability is challenging  
-  UX plays a critical role in adoption  

---

##  What's Next

We’re expanding hire.ai into a more scalable, transparent, and fair hiring platform:

-  Deeper code analysis (static + semantic)  
-  Explainable and transparent scoring  
-  Recruiter feedback integration  
-  LinkedIn and portfolio support  
-  Bias detection and fairness improvements  
-  Scalable SaaS deployment  

---

##  Built With
- base64
- bcrypt
- ffmpeg
- gemini
- gemini-api
- github-api
- google-gemini-2.5-flash
- groq
- imageio-ffmpeg
- llama-3.3-70b
- mongodb
- pdfplumber
- pymongo
- pypdf2
- python
- python-docx
- requests
- streamlit
- streamlit-components
