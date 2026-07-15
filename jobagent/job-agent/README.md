# Job Application Agent

An AI-powered assistant for applying to jobs from **company career pages**.

Upload your resume once, paste one or more career-page URLs, and the agent:

1. **Parses your resume** (PDF / DOCX / pasted text) into a structured profile —
   contact info, education, work experience, skills, tools, certifications, projects,
   industries, and consulting / data-analysis / implementation experience.
2. **Scans each career page** and finds the open job postings
   (native support for Greenhouse, Lever, Ashby and Workable boards; a generic
   scanner + headless browser for everything else).
3. **Reads each job description** and extracts requirements, skills, and any
   application questions.
4. **Scores every job 0–1 against your resume** (title, required/preferred skills,
   education, experience, tools, industry, BA/data/consulting/implementation
   experience, keywords, and realistic qualification) and shows a dashboard:
   - **0.85–1.00** Strong fit · **0.70–0.84** Good fit · **0.55–0.69** Maybe · **< 0.55** Weak
5. **Autofills the application** for strong/good fits with a real browser
   (Playwright): contact details, links, resume upload, work authorization,
   availability, salary (if you provided it), and natural, truthful written answers
   to screening questions — generated only from what is actually in your resume.
6. **Stops before submitting.** You review every filled field and a live screenshot,
   can edit any answer, and the submit button is clicked **only after you explicitly
   confirm**.

## What it deliberately does NOT do

- ❌ No LinkedIn scraping, no LinkedIn Easy Apply automation
- ❌ No mass-applying (per-scan job cap, autofill only for strong/good fits)
- ❌ No submission without your explicit confirmation
- ❌ No answering voluntary demographic questions (unless you explicitly save preferences)
- ❌ No guessing sensitive data (SSN, DOB, licenses, banking — always skipped)
- ❌ No inventing or exaggerating experience — answers are grounded in your resume only
- ❌ No scanning pages disallowed by the site's `robots.txt`
- ✋ CAPTCHAs, logins and 2FA are never automated — the agent stops and asks you
  to finish manually

---

## Project structure

```
job-agent/
├── backend/                 FastAPI app (Python 3.11+)
│   ├── app/
│   │   ├── main.py          App entry, static serving of built frontend
│   │   ├── config.py        Env-based configuration
│   │   ├── db.py, models.py SQLite via SQLAlchemy (profiles, scans, jobs, applications)
│   │   ├── prompts.py       All AI prompts + JSON schemas (matching, answers, autofill)
│   │   ├── llm.py           Anthropic API wrapper (structured JSON outputs)
│   │   ├── routers/         REST endpoints (resume, scans, jobs, applications)
│   │   └── services/
│   │       ├── resume_parser.py   pdfplumber / python-docx / text + LLM structuring
│   │       ├── career_scanner.py  ATS APIs + generic HTML/Playwright scanner
│   │       ├── robots.py          robots.txt compliance
│   │       ├── matcher.py         job extraction + 0–1 fit scoring
│   │       ├── answers.py         tailored written answers
│   │       ├── autofill.py        Playwright form filling + human-confirmation submit
│   │       ├── scan_runner.py     background scan orchestration
│   │       └── browser.py         shared headless-browser lifecycle
│   ├── requirements.txt
│   └── .env.example
└── frontend/                React (Vite) single-page app
    └── src/components/      Resume upload, scan, dashboard, job detail, application review
```

## Setup

Prerequisites: **Python 3.11+**, **Node 18+**, an **Anthropic API key**.

### 1. Backend

```bash
cd job-agent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # one-time browser download

cp .env.example .env                 # then edit .env and set ANTHROPIC_API_KEY
```

### 2. Frontend

```bash
cd job-agent/frontend
npm install
npm run build                        # backend serves the built app at http://localhost:8000
```

### 3. Run

```bash
cd job-agent/backend
source .venv/bin/activate
uvicorn app.main:app --port 8000
```

Open **http://localhost:8000**. (For frontend development, `npm run dev` serves a
hot-reloading app on http://localhost:5173 proxied to the backend.)

## Environment variables (`backend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — (required) | API key for resume parsing, matching, answers, autofill mapping |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Model used for all AI tasks |
| `MAX_JOBS_PER_SCAN` | `25` | Cost/safety cap on postings processed per career page |
| `HEADLESS` | `true` | Set `false` to watch the browser fill forms (and finish CAPTCHAs yourself) |
| `FETCH_DELAY_SECONDS` | `1.0` | Politeness delay between page fetches |
| `STORAGE_DIR` | `backend/storage` | Resumes, screenshots, SQLite DB |
| `PLAYWRIGHT_CHROMIUM_PATH` | — | Optional path to a specific Chromium binary |

## Typical workflow

1. **Resume tab** — upload PDF/DOCX or paste text → review the parsed profile →
   fill in optional extras (LinkedIn, portfolio, salary expectation, work
   authorization, availability).
2. **Scan tab** — paste career-page URLs (one per line) → *Scan for jobs*.
   Progress updates live; each posting is read and scored as it's processed.
3. **Job matches tab** — sortable dashboard with fit score badge, category,
   matching/missing skills and an Apply / Maybe / Skip recommendation.
4. **Job detail** — why it matches / why it may not, requirements, full
   description, and one-click tailored answers to the posting's questions.
5. **Apply** (strong/good fits only) — the agent opens the real application form,
   fills it, and shows every field plus a screenshot.
6. **Confirm** — you see:
   *"Your application has been filled out. Please review all information carefully
   before submitting. Do you want to submit this application?"*
   with **Review application / Edit answers / Submit application**. Only the last
   one clicks submit.

## Limitations & compliance notes

- **Keep a human in the loop.** This is an assistant, not an auto-applier. Review
  every field before submitting; you are responsible for what is sent.
- **Form coverage.** Native HTML forms (Greenhouse, Lever, Ashby, and most
  standard pages) fill well. Heavily customized React widgets, multi-step wizards
  (e.g. Workday), and iframe-embedded forms may only partially fill — the agent
  reports what it couldn't do and you can finish manually.
- **CAPTCHA / login walls** stop the autofill by design. Run with `HEADLESS=false`
  to complete those steps yourself in the same browser window.
- **Browser session lifetime.** The filled form lives in a real browser tab on the
  server. If the backend restarts between fill and confirm, re-run Apply.
- **robots.txt** is checked before scanning; disallowed pages are refused with a
  suggestion to paste the description manually.
- **Terms of service.** Some career sites prohibit automated form submission —
  check the site's ToS. The per-scan cap, fetch delays, and identified user agent
  keep the scanner polite, but you use this tool at your own responsibility.
- **AI outputs can be imperfect.** Fit scores are advisory; answers are grounded
  in your resume but always proofread them before submitting.
- **Single user.** The MVP stores one profile in a local SQLite DB. No auth —
  run it locally, not on a public server.
- **Costs.** Each scanned job = ~1 model call; each autofill = 1–2 calls. The
  `MAX_JOBS_PER_SCAN` cap bounds spend.

## Build phases (all included in this MVP)

1. Resume upload, parsing, career-page scanning, job extraction, fit scoring
2. Dashboard with 0–1 fit scores and Apply/Maybe/Skip recommendations
3. Tailored answers for strong-fit jobs
4. Browser automation to fill applications
5. Final review-and-confirm screen before any submission
