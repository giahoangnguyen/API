from typing import List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
import base64
import logging
import os
import re
import json
from openai import OpenAI, BadRequestError

# Initialize FastAPI
app = FastAPI(title="Resume Matching")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


openai_client = OpenAI(api_key="OPENAI_API_KEY")

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

async def ocr_via_openai(file_bytes: bytes) -> str:
    b64 = base64.b64encode(file_bytes).decode()
    system_text = "Extract all text from this image and return only the raw text."
    message_content = [
        {"type": "text",      "text": system_text},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
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

def call_openai_extract_skills(text: str) -> List[str]:
    sys_prompt = (
        "You are an expert technical recruiter. Extract every distinct technical skill—"
        "languages, frameworks, libraries, tools, and methodologies—from the input that you think it will be related to Information Technology field. "
        "Return exactly a JSON array of lowercase strings. No extra keys or commentary."
    )
    user_prompt = f"Extract skills from:\n{text}"
    try:
        resp = openai_client.chat.completions.create(
            model='gpt-4',
            messages=[{'role':'system','content':sys_prompt},{'role':'user','content':user_prompt}],
            temperature=0.0
        )
        skills = json.loads(resp.choices[0].message.content)
        if isinstance(skills, list) and all(isinstance(s, str) for s in skills):
            seen, out = set(), []
            for s in skills:
                k = s.strip().lower()
                if k and k not in seen:
                    seen.add(k); out.append(k)
            return out
    except Exception:
        pass
    bullets = []
    for line in text.splitlines():
        pt = line.strip()
        if pt.startswith(('-', '•')) or re.match(r"^\d+[\.)]", pt):
            tok = re.sub(r"^[-•\d+\.)]+\s*", '', pt)
            for a in tok.split(','):
                k = a.strip().lower()
                if k and k not in bullets:
                    bullets.append(k)
    if bullets:
        return bullets
    toks = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+\-#]{2,}\b", text)
    seen, ordered = set(), []
    for t in toks:
        k = t.lower()
        if k not in seen:
            seen.add(k); ordered.append(k)
    return ordered[:15]


def generate_reasoning(resume_skills: List[str], job_skills: List[str], score: float, threshold: float) -> str:
    sys_text = (
        "You are an expert hiring manager. State 'X out of Y skills (Z%) matched.', "
        "then list matched skills and missing skills, and give a brief explanation of how you reach that score."
    )
    usr = (
        f"resume_skills: {resume_skills}\n"
        f"job_skills:    {job_skills}\n"
        f"match_score:   {score:.2f}\n"
        f"threshold:     {threshold:.2f}"
    )
    resp = openai_client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[{'role':'system','content':sys_text},{'role':'user','content':usr}],
        temperature=0.0, max_tokens=150
    )
    reasoning = resp.choices[0].message.content.strip()
    if score < threshold:
        reasoning += f" Below threshold {threshold:.2f}."
    return reasoning

# Core matching logic
def match_logic(resume_text: str, job_text: str, threshold: float) -> MatchResponse:
    rs = call_openai_extract_skills(resume_text)
    js = call_openai_extract_skills(job_text)
    if not js:
        raise HTTPException(status_code=400, detail="No skills extracted from job description.")
    matched = [s for s in js if s in rs]
    missing = [s for s in js if s not in rs]
    score = len(matched) / len(js)
    reasoning = generate_reasoning(rs, js, score, threshold)
    return MatchResponse(
        score=round(score,3),
        resume_skills=rs,
        job_skills=js,
        matched_skills=matched,
        missing_skills=missing,
        reasoning=reasoning
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
    rtext = await ocr_via_openai(rbytes)
    jtext = await ocr_via_openai(jbytes)
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
    job_text = await ocr_via_openai(jbytes)
    # OCR and match each resume
    results, names = [], []
    for f in resume_files:
        rbytes = await f.read()
        rtext = await ocr_via_openai(rbytes)
        name = next((l.strip() for l in rtext.splitlines() if l.strip()), "Unknown")
        names.append(name)
        results.append(match_logic(rtext, job_text, threshold))
    best_index = max(range(len(results)), key=lambda i: results[i].score)
    best_name = names[best_index]
    return MultiMatchResponse(results=results, best_match_index=best_index, best_match_name=best_name)
