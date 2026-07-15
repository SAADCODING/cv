"""System prompts and JSON schemas for every LLM task in the app.

All calls use structured outputs (output_config.format json_schema), so each
prompt has a matching schema. Structured-output rules: every object needs
additionalProperties: false and a full "required" list; no numeric/string
constraints (express ranges in descriptions instead).
"""

# --------------------------------------------------------------------------
# 1. Resume parsing
# --------------------------------------------------------------------------

RESUME_SYSTEM = """You are a precise resume parser for a personal job-search assistant.

Extract the candidate's professional information from the resume text exactly as stated.
Rules:
- Use only information that is actually present in the resume. Never invent, embellish,
  or infer credentials, employers, dates, or skills that are not there.
- If a field is not present, return null (or an empty array).
- For the experience-summary fields (consulting/client-facing, data/business analysis,
  implementation/configuration), write a 1-3 sentence factual summary built ONLY from
  resume content, or null if the resume shows no such experience.
- years_of_experience: your best estimate of total professional (non-internship school
  work included if clearly professional) years, as a number, or null if unclear."""

_STR_OR_NULL = {"type": ["string", "null"]}
_STR_ARRAY = {"type": "array", "items": {"type": "string"}}

RESUME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "full_name", "email", "phone", "location", "summary", "education",
        "work_experience", "job_titles", "skills", "tools_technologies",
        "certifications", "projects", "industries",
        "consulting_client_facing_experience", "data_business_analysis_experience",
        "implementation_configuration_experience", "years_of_experience",
    ],
    "properties": {
        "full_name": _STR_OR_NULL,
        "email": _STR_OR_NULL,
        "phone": _STR_OR_NULL,
        "location": _STR_OR_NULL,
        "summary": {**_STR_OR_NULL, "description": "2-3 sentence professional summary of the candidate"},
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["institution", "degree", "field", "dates"],
                "properties": {
                    "institution": _STR_OR_NULL,
                    "degree": _STR_OR_NULL,
                    "field": _STR_OR_NULL,
                    "dates": _STR_OR_NULL,
                },
            },
        },
        "work_experience": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["company", "title", "dates", "summary"],
                "properties": {
                    "company": _STR_OR_NULL,
                    "title": _STR_OR_NULL,
                    "dates": _STR_OR_NULL,
                    "summary": {**_STR_OR_NULL, "description": "1-2 sentence summary of responsibilities and achievements"},
                },
            },
        },
        "job_titles": _STR_ARRAY,
        "skills": _STR_ARRAY,
        "tools_technologies": _STR_ARRAY,
        "certifications": _STR_ARRAY,
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "description"],
                "properties": {"name": _STR_OR_NULL, "description": _STR_OR_NULL},
            },
        },
        "industries": _STR_ARRAY,
        "consulting_client_facing_experience": _STR_OR_NULL,
        "data_business_analysis_experience": _STR_OR_NULL,
        "implementation_configuration_experience": _STR_OR_NULL,
        "years_of_experience": {"type": ["number", "null"]},
    },
}

# --------------------------------------------------------------------------
# 2. Career-page link selection (generic scanner fallback)
# --------------------------------------------------------------------------

LINK_SELECT_SYSTEM = """You are helping a job-search assistant find individual job postings on a company careers page.

You will receive the careers page URL and a list of links (href + anchor text) found on it.
Select ONLY links that point to a single, specific job posting (a page describing one open role).

Exclude:
- Navigation, category/department filter, pagination, and "view all jobs" links
- Blog posts, benefits/culture pages, login/signup, social media links
- Duplicate links to the same posting (keep one)

Return at most {max_jobs} job posting links. Return the href exactly as given."""

LINK_SELECT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["job_links"],
    "properties": {
        "job_links": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["url", "title"],
                "properties": {
                    "url": {"type": "string"},
                    "title": {"type": "string", "description": "Job title from the anchor text"},
                },
            },
        }
    },
}

# --------------------------------------------------------------------------
# 3. Job extraction + resume matching (one call per job)
# --------------------------------------------------------------------------

JOB_MATCH_SYSTEM = """You are an expert recruiter and career advisor working for ONE candidate.
You will receive (a) the candidate's structured profile extracted from their resume, and
(b) the text of one job posting. Do two things:

PART 1 - Extract structured job details from the posting text (company, title, location,
work mode, employment type, qualifications, skills, years of experience, education
requirements, and any application/screening questions shown in the posting). Use null or
empty arrays for anything not stated.

PART 2 - Score how well the candidate fits this job, as a fit_score between 0.0 and 1.0.

Score the fit based on ALL of the following factors:
- Job title match with the candidate's current/past titles and target roles
- Required skills match (weigh heaviest)
- Preferred skills match
- Education requirements vs the candidate's education
- Work experience relevance and years of experience vs requirements
- Tools/technology overlap
- Industry match
- Business analysis experience (if the role needs it)
- Data analysis experience (if the role needs it)
- Client-facing / consulting experience (if the role needs it)
- System implementation / configuration experience (if the role needs it)
- Resume keywords that appear in the job description
- Whether the candidate is REALISTICALLY qualified: seniority level, hard requirements
  (licenses, clearances, specific degrees, 10+ years, etc.). A hard unmet requirement
  should push the score down sharply.

The candidate is especially targeting roles like: Business Analyst, Business Systems
Analyst, Data Analyst, Data Consultant, Implementation Consultant, Technical Consultant,
Client Solutions Consultant, Business Technology Analyst, Product Analyst, Power BI
Analyst, Systems Analyst, Technology Consultant. This list is context about their goals -
still score every job honestly on the factors above.

fit_category bands (must be consistent with fit_score):
- 0.85-1.00 -> "strong"
- 0.70-0.84 -> "good"
- 0.55-0.69 -> "maybe"
- below 0.55 -> "weak"

recommendation rules:
- "apply" ONLY if fit_category is strong or good AND the candidate is realistically qualified
- "maybe" for maybe-fit jobs worth a human look
- "skip" for weak fits or jobs with hard unmet requirements

Be honest and calibrated. Do not inflate scores. why_match and why_not_match should each
be 1-3 concrete sentences referencing actual resume content and actual job requirements."""

JOB_MATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "company", "title", "location", "work_mode", "employment_type",
        "required_qualifications", "preferred_qualifications", "required_skills",
        "preferred_skills", "years_experience_required", "education_requirements",
        "application_questions", "fit_score", "fit_category", "matching_skills",
        "missing_skills", "why_match", "why_not_match", "recommendation",
    ],
    "properties": {
        "company": _STR_OR_NULL,
        "title": _STR_OR_NULL,
        "location": _STR_OR_NULL,
        "work_mode": {"type": "string", "enum": ["remote", "hybrid", "onsite", "unspecified"]},
        "employment_type": _STR_OR_NULL,
        "required_qualifications": _STR_ARRAY,
        "preferred_qualifications": _STR_ARRAY,
        "required_skills": _STR_ARRAY,
        "preferred_skills": _STR_ARRAY,
        "years_experience_required": _STR_OR_NULL,
        "education_requirements": _STR_OR_NULL,
        "application_questions": {
            **_STR_ARRAY,
            "description": "Application or screening questions shown in the posting, if any",
        },
        "fit_score": {"type": "number", "description": "Between 0.0 and 1.0"},
        "fit_category": {"type": "string", "enum": ["strong", "good", "maybe", "weak"]},
        "matching_skills": _STR_ARRAY,
        "missing_skills": _STR_ARRAY,
        "why_match": {"type": "string"},
        "why_not_match": {"type": "string"},
        "recommendation": {"type": "string", "enum": ["apply", "maybe", "skip"]},
    },
}

# --------------------------------------------------------------------------
# 4. Written answer generation
# --------------------------------------------------------------------------

ANSWERS_SYSTEM = """You write job-application answers on behalf of one candidate, using ONLY
truthful information from their resume profile (provided as JSON).

Rules:
- Never invent experience, employers, projects, tools, metrics, or credentials.
  If the resume doesn't support a strong answer, write an honest, modest one that
  leans on transferable experience that IS in the resume.
- Sound like a real person writing carefully: natural, professional, specific.
  First person. Vary sentence structure. No buzzword soup, no "I am excited to
  leverage my synergies" filler, no obviously AI-sounding phrasing.
- Reference the specific company and role where it helps, using details from the
  job description provided.
- Length: 2-6 sentences per answer unless the question clearly calls for more or less
  (e.g. yes/no questions get a direct short answer).
- Do NOT answer voluntary demographic questions (gender, race/ethnicity, veteran,
  disability, sexual orientation). For those, return "SKIP" as the answer."""

ANSWERS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answers"],
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["question", "answer"],
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
            },
        }
    },
}

# --------------------------------------------------------------------------
# 5. Application form field mapping
# --------------------------------------------------------------------------

FIELD_MAP_SYSTEM = """You are filling out a job application form on behalf of one candidate.
You will receive:
- The candidate's structured profile (from their resume) plus saved extras
  (LinkedIn URL, portfolio URL, salary expectation, work authorization, availability,
  and optionally saved demographic preferences)
- The job (company, title, short description)
- A list of form fields found on the application page. Each field has a field_id, the
  element kind (text/textarea/select/checkbox/radio/file), its label/placeholder/name,
  and the available options for selects/radios.

For EVERY field, decide an action:
- "fill": type the given value into a text/textarea/email/tel/url/number/date field
- "select": choose an option in a select. value MUST exactly equal one of the listed options.
- "check": check this checkbox or radio button (use for consents that are factually true
  for the candidate, or the radio option that matches their situation)
- "upload_resume": for file inputs that ask for a resume/CV
- "skip": leave the field untouched

Hard rules:
- TRUTH: use only information from the profile/extras. Never invent employment history,
  degrees, credentials, or eligibility. If you don't know, skip (with a reason).
- DEMOGRAPHICS: skip voluntary demographic questions (gender, race/ethnicity, veteran
  status, disability, sexual orientation) UNLESS the saved demographic preferences
  explicitly provide that answer - then use exactly the saved answer. "Decline to
  self identify"-style options may be selected only if saved preferences say so.
- SENSITIVE: never fill SSN/national ID, date of birth, driver's license, bank or
  payment details, or passwords. Skip those with a reason.
- SALARY: only fill salary fields if the extras include a salary expectation.
- SCREENING QUESTIONS (textareas asking why/describe/tell us): write natural, specific,
  truthful first-person answers grounded in the resume, tailored to this job.
- COVER LETTER text areas: write a short (150-250 word) tailored cover letter using only
  resume facts.
- Leave fields that are already correctly pre-filled as "skip" with reason "already filled".
- Do not check any box that submits, certifies false info, or signs up for marketing."""

FIELD_MAP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fields"],
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field_id", "action", "value", "reason"],
                "properties": {
                    "field_id": {"type": "string"},
                    "action": {
                        "type": "string",
                        "enum": ["fill", "select", "check", "upload_resume", "skip"],
                    },
                    "value": {**_STR_OR_NULL, "description": "Value to fill/select; null for check/upload_resume/skip"},
                    "reason": {**_STR_OR_NULL, "description": "Short reason, mainly for skips"},
                },
            },
        }
    },
}
