# API Grading Project
## Getting Started

### Prerequisites 
Before you begin, make sure you have the following installed:

Python 3.10+ installed
Git installed
(Optional) Windows users: Git Bash or WSL recommended
A valid OpenAI API key

Clone the repo

git clone https://github.com/<YOUR_ORG>/<YOUR_REPO>.git
cd <YOUR_REPO>

### Create & activate a virtual environment to work with (back end)

### macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

### Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

Install Python dependencies

If the repo includes a requirements.txt:
pip install --upgrade pip
pip install -r requirements.txt

Otherwise install directly:
pip install fastapi uvicorn openai python-multipart pydantic

Set your OpenAI API key

### macOS / Linux
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"

### Windows (PowerShell)
$env:OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"

Run the service
uvicorn resume_matcher:app --reload --host 0.0.0.0 --port 8000
