import { useEffect, useState } from "react";
import { api } from "../api.js";
import FitBadge, { categoryLabel } from "./FitBadge.jsx";

export default function JobDetail({ jobId, onApplicationStarted }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [answersBusy, setAnswersBusy] = useState(false);
  const [showDescription, setShowDescription] = useState(false);

  const load = () => api.getJob(jobId).then(setJob).catch((e) => setError(e.message));

  useEffect(() => {
    setJob(null);
    load();
  }, [jobId]);

  if (error) return <div className="panel"><p className="error">{error}</p></div>;
  if (!job) return <div className="panel"><p>Loading…</p></div>;

  const details = job.details || {};
  const canApply = job.fit_category === "strong" || job.fit_category === "good";

  const apply = async () => {
    setBusy(true);
    setError("");
    try {
      const app = await api.startApplication(job.id);
      onApplicationStarted(app.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const generateAnswers = async () => {
    setAnswersBusy(true);
    setError("");
    try {
      await api.generateAnswers(job.id, details.application_questions?.length ? details.application_questions : null);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setAnswersBusy(false);
    }
  };

  return (
    <div className="panel">
      <div className="job-header">
        <div>
          <h2>{job.title}</h2>
          <p className="hint">
            {job.company} · {job.location || "location unspecified"} · {job.work_mode}
            {job.employment_type ? ` · ${job.employment_type}` : ""} ·{" "}
            <a href={job.url} target="_blank" rel="noreferrer">open posting ↗</a>
          </p>
        </div>
        <div className="fit-box">
          <FitBadge score={job.fit_score} category={job.fit_category} />
          <div>{categoryLabel(job.fit_category)}</div>
        </div>
      </div>

      <div className="two-col">
        <div className="match-box match-yes">
          <h3>Why this job matches</h3>
          <p>{job.why_match || "—"}</p>
          <strong>Matching skills</strong>
          <div>{(job.matching_skills || []).map((s, i) => <span className="tag" key={i}>{s}</span>)}</div>
        </div>
        <div className="match-box match-no">
          <h3>Why it may not match</h3>
          <p>{job.why_not_match || "—"}</p>
          <strong>Missing skills</strong>
          <div>{(job.missing_skills || []).map((s, i) => <span className="tag tag-missing" key={i}>{s}</span>)}</div>
        </div>
      </div>

      <h3>Requirements</h3>
      <div className="two-col">
        <div>
          <strong>Required</strong>
          <ul>{(details.required_qualifications || []).map((q, i) => <li key={i}>{q}</li>)}</ul>
          <p className="hint">
            Experience: {details.years_experience_required || "unspecified"} · Education:{" "}
            {details.education_requirements || "unspecified"}
          </p>
        </div>
        <div>
          <strong>Preferred</strong>
          <ul>{(details.preferred_qualifications || []).map((q, i) => <li key={i}>{q}</li>)}</ul>
        </div>
      </div>

      <button onClick={() => setShowDescription(!showDescription)}>
        {showDescription ? "Hide" : "Show"} full job description
      </button>
      {showDescription && <pre className="description">{job.description}</pre>}

      <h3>Application questions & tailored answers</h3>
      {details.application_questions?.length > 0 ? (
        <ul>{details.application_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
      ) : (
        <p className="hint">No questions listed in the posting. You can still generate answers to common ones.</p>
      )}
      <button onClick={generateAnswers} disabled={answersBusy}>
        {answersBusy ? "Writing answers…" : "Generate tailored answers"}
      </button>
      {(details.generated_answers || []).map((a, i) => (
        <div className="answer-box" key={i}>
          <strong>{a.question}</strong>
          <p>{a.answer}</p>
        </div>
      ))}

      <hr />
      {canApply ? (
        <>
          <button className="primary big" onClick={apply} disabled={busy}>
            {busy ? "Opening application…" : "Apply — autofill this application"}
          </button>
          <p className="hint">
            The agent opens the application form, fills it from your resume, and then stops for
            your review. Nothing is submitted without your confirmation.
          </p>
        </>
      ) : (
        <p className="hint">
          Autofill is only offered for strong/good fits ({categoryLabel(job.fit_category)} here).
          You can always apply manually via the posting link above.
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
