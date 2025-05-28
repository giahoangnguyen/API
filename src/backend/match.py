from typing import List, Tuple
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
import base64
import logging
import re
import json
from openai import OpenAI, BadRequestError

# Initialize FastAPI
app = FastAPI(title="Resume Matching")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


openai_client = OpenAI(api_key="your-api-key")

# Request and Response Models
class MatchRequest(BaseModel):
    resume_text: str = Field(..., description="Raw resume text to be analyzed")
    job_text: str = Field(..., description="Raw job description text to be analyzed")
    threshold: float = Field(0.8, ge=0.0, le=1.0, description="Score threshold for qualification")

class MatchResponse(BaseModel):
    score: float = Field(..., description="Match score between 0.0 and 1.0")
    resume_skills: List[str]
    job_skills: List[str]
    matched_skills: List[str]
    missing_skills: List[str]
    reasoning: str

class MultiMatchRequest(BaseModel):
    resume_texts: List[str] = Field(..., description="List of resume texts to compare")
    job_text: str = Field(..., description="Raw job description text to be analyzed")
    threshold: float = Field(0.8, ge=0.0, le=1.0, description="Score threshold for qualification")

class MultiMatchResponse(BaseModel):
    results: List[MatchResponse] = Field(..., description="Match results for each resume")
    best_match_index: int = Field(..., description="Index of the best matching resume in the input list")
    best_match_name: str = Field(..., description="Name of the candidate with the best match")

# Helpers for OCR
def validate_image_content_type(content_type: str):
    if content_type not in ['image/jpeg', 'image/png']:
        raise HTTPException(status_code=400, detail='Invalid image format. Use JPEG or PNG.')

async def ocr_via_openai(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode()
    system_text = "Extract all text from this image and return only the raw text."
    message_content = [
        {"type": "text",      "text": system_text},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
    ]
    try:
        resp = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=[{'role':'user', 'content': message_content}],
            temperature=0.0
        )
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=f'OCR error: {e}')
    return resp.choices[0].message.content.strip()

# Skill extraction and reasoning

# ---------- BETTER SKILL-EXTRACTION ----------
def call_openai_extract_skills(text: str) -> List[str]:
    """
    Return a clean list of real skills (tech + soft) from free-form text.
    GPT is given explicit positive & negative examples so it no longer
    spits out names, cities, email fragments, etc.
    """
    system_prompt = (
        "You are an expert recruiter. Extract every DISTINCT skill that could "
        "appear in a CV or job post. A skill may be a programming language, "
        "software, cloud platform, data technology, methodology (e.g. scrum), "
        "or soft skill (e.g. communication, leadership). Do NOT return:\n"
        "  • personal names, cities, countries, addresses, emails, URLs\n"
        "  • generic words like 'professional', 'experience', 'new', 'resume'\n"
        "Return ONLY a JSON array of lowercase strings—no extra keys, no prose."
    )

    # few-shot examples help GPT stay on track
    examples = [
        {
            "role": "user",
            "content": "Extract skills:\n"
                       "John Doe – San Francisco CA\n"
                       "Email: john@x.com • Phone: 555-555\n"
                       "Senior Data Engineer skilled in Python, Spark, AWS EMR, "
                       "and orchestration with Airflow. Strong communication skills."
        },
        {
            "role": "assistant",
            "content": '["python","spark","aws emr","airflow","communication"]'
        },
        {
            "role": "user",
            "content": "Extract skills:\n"
                       "We need someone who knows Java, Spring Boot, Docker/K8s, "
                       "CI/CD (GitLab) and agile methodologies."
        },
        {
            "role": "assistant",
            "content": '["java","spring boot","docker","k8s","gitlab","ci/cd","agile"]'
        },
    ]

    # real query
    examples.append({"role": "user", "content": f"Extract skills:\n{text}"})

    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, *examples],
            temperature=0.0,
        )
        skills = json.loads(resp.choices[0].message.content)
        if isinstance(skills, list):
            # normalise & dedupe
            out, seen = [], set()
            for s in skills:
                if isinstance(s, str):
                    k = s.strip().lower()
                    if k and k not in seen:
                        seen.add(k)
                        out.append(k)
            return out
    except Exception as e:
        logger.warning(f"Skill-extraction fallback because: {e}")

    # ---------- fallback heuristic ----------
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9.+/#\-]{2,}", text)
    noise = {
        "professional", "experience", "resume", "worded", "linkedin",
        "com", "first", "last", "new", "york"
    }
    out, seen = [], set()
    for tok in tokens:
        k = tok.lower()
        if k not in seen and k not in noise and len(k) < 30:
            seen.add(k)
            out.append(k)
    return out[:20]



def generate_reasoning(
    resume_skills: List[str],
    job_skills: List[str],
    threshold: float,
) -> Tuple[float, List[str], List[str], str]:
    system_prompt = (
        "You are a senior technical recruiter. "
        "Given two unordered lists of skill tokens, you must:\n"
        "1. Align semantically‑equivalent items (treat synonyms, abbreviations "
        "   and near‑synonyms as a match\n"
        "2. Count how many required (job) skills are present in the candidate list.\n"
        "3. Return ONLY a JSON object with keys: matched, missing, score (0‑1 float)."
    )

    payload = json.dumps({"resume_skills": resume_skills, "job_skills": job_skills})

    resp = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload},
        ],
        temperature=0.0,
    )

    try:
        data = json.loads(resp.choices[0].message.content)
        matched: List[str] = data["matched"]
        missing: List[str] = data["missing"]
        score: float = float(data["score"])
    except (KeyError, ValueError, json.JSONDecodeError):
        # Fallback: literal intersection
        matched = [s for s in job_skills if s in resume_skills]
        missing = [s for s in job_skills if s not in resume_skills]
        score = len(matched) / len(job_skills) if job_skills else 0.0

    explanation = (
        f"{len(matched)} / {len(job_skills)} skills matched "
        f"({score*100:.1f}%). "
        f"Matched: {', '.join(matched) or '–'}. "
        f"Missing: {', '.join(missing) or '–'}."
    )

    if score < threshold:
        explanation += f" Below threshold {threshold:.2f}."

    return score, matched, missing, explanation

# ------------- UPDATED match_logic -----------------

def match_logic(resume_text: str, job_text: str, threshold: float) -> "MatchResponse":
    rs = call_openai_extract_skills(resume_text)
    js = call_openai_extract_skills(job_text)
    if not js:
        raise HTTPException(status_code=400, detail="No skills extracted from job description.")

    # lower‑case & dedupe both lists to help GPT and our fallback path
    rs = list(dict.fromkeys([s.lower() for s in rs]))
    js = list(dict.fromkeys([s.lower() for s in js]))

    score, matched, missing, reasoning = generate_reasoning(rs, js, threshold)

    return MatchResponse(
        score=round(score, 3),
        resume_skills=rs,
        job_skills=js,
        matched_skills=matched,
        missing_skills=missing,
        reasoning=reasoning,
    )

# Endpoints
@app.post("/match-text", response_model=MatchResponse)
def match_text(req: MatchRequest):
    return match_logic(req.resume_text, req.job_text, req.threshold)

@app.post("/match-image", response_model=MatchResponse)
async def match_image(
    resume_file: UploadFile = File(...),
    job_file:    UploadFile = File(...),
    threshold:   float      = Form(0.8)
):
    validate_image_content_type(resume_file.content_type)
    validate_image_content_type(job_file.content_type)
    rbytes = await resume_file.read()
    jbytes = await job_file.read()
    rtext = await ocr_via_openai(rbytes, resume_file.content_type)
    jtext = await ocr_via_openai(jbytes, job_file.content_type)
    return match_logic(rtext, jtext, threshold)

@app.post("/match-text-multiple", response_model=MultiMatchResponse)
def match_text_multiple(req: MultiMatchRequest):
    results = []
    names = []
    for text in req.resume_texts:
        # extract candidate name as first non-empty line
        name = next((line.strip() for line in text.splitlines() if line.strip()), "Unknown")
        names.append(name)
        res = match_logic(text, req.job_text, req.threshold)
        results.append(res)
    best_index = max(range(len(results)), key=lambda i: results[i].score)
    best_name = names[best_index]
    return MultiMatchResponse(results=results, best_match_index=best_index, best_match_name=best_name)

# Multiple image matching
@app.post("/match-image-multiple", response_model=MultiMatchResponse)
async def match_image_multiple(
    # Allow multiple resume image uploads in one request
    resume_files: List[UploadFile] = File(..., description="Upload one or more resume image files"),
    # Single job description image upload
    job_file: UploadFile = File(..., description="Upload the job description image file"),
    # Qualification threshold
    threshold: float = Form(0.8, description="Score threshold for qualification")
):
    # OCR job description
    jbytes = await job_file.read()
    job_text = await ocr_via_openai(jbytes, job_file.content_type)
    # OCR and match each resume
    results, names = [], []
    for f in resume_files:
        rbytes = await f.read()
        rtext = await ocr_via_openai(rbytes, f.content_type)
        name = next((l.strip() for l in rtext.splitlines() if l.strip()), "Unknown")
        names.append(name)
        results.append(match_logic(rtext, job_text, threshold))
    best_index = max(range(len(results)), key=lambda i: results[i].score)
    best_name = names[best_index]
    return MultiMatchResponse(results=results, best_match_index=best_index, best_match_name=best_name)
