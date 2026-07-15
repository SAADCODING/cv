import { useState } from "react";
import { api } from "../api.js";

export default function ProfileView({ profile, onProfile }) {
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [extras, setExtras] = useState({
    linkedin_url: profile?.linkedin_url || "",
    portfolio_url: profile?.portfolio_url || "",
    salary_expectation: profile?.salary_expectation || "",
    work_authorization: profile?.work_authorization || "",
    availability: profile?.availability || "",
  });
  const [savedMsg, setSavedMsg] = useState("");

  const upload = async () => {
    setBusy(true);
    setError("");
    try {
      const res = file ? await api.uploadResumeFile(file) : await api.uploadResumeText(text);
      onProfile(res.profile);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const saveExtras = async () => {
    setBusy(true);
    setError("");
    setSavedMsg("");
    try {
      const res = await api.updateProfile(extras);
      onProfile(res.profile);
      setSavedMsg("Saved.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const data = profile?.data;

  return (
    <div className="panel">
      <h2>Upload your resume</h2>
      <p className="hint">
        PDF, DOCX, or plain text. The agent extracts your experience once and reuses it for every
        job match and application.
      </p>

      <div className="upload-row">
        <input
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <span className="hint">or paste the text below</span>
      </div>
      <textarea
        rows={6}
        placeholder="Paste your resume text here (optional if you chose a file)..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button className="primary" onClick={upload} disabled={busy || (!file && !text.trim())}>
        {busy ? "Parsing..." : "Parse resume"}
      </button>
      {error && <p className="error">{error}</p>}

      {data && (
        <>
          <h2>Parsed profile</h2>
          <div className="profile-grid">
            <div><strong>Name</strong> {data.full_name || "—"}</div>
            <div><strong>Email</strong> {data.email || "—"}</div>
            <div><strong>Phone</strong> {data.phone || "—"}</div>
            <div><strong>Location</strong> {data.location || "—"}</div>
            <div><strong>Experience</strong> {data.years_of_experience != null ? `~${data.years_of_experience} years` : "—"}</div>
          </div>
          {data.summary && <p>{data.summary}</p>}
          <TagList label="Skills" items={data.skills} />
          <TagList label="Tools & technologies" items={data.tools_technologies} />
          <TagList label="Job titles" items={data.job_titles} />
          <TagList label="Certifications" items={data.certifications} />
          <TagList label="Industries" items={data.industries} />
          {data.work_experience?.length > 0 && (
            <>
              <h3>Work experience</h3>
              <ul>
                {data.work_experience.map((w, i) => (
                  <li key={i}>
                    <strong>{w.title}</strong> at {w.company} ({w.dates}) — {w.summary}
                  </li>
                ))}
              </ul>
            </>
          )}
          {data.education?.length > 0 && (
            <>
              <h3>Education</h3>
              <ul>
                {data.education.map((e, i) => (
                  <li key={i}>
                    {e.degree} {e.field ? `in ${e.field}` : ""}, {e.institution} ({e.dates})
                  </li>
                ))}
              </ul>
            </>
          )}

          <h2>Application extras</h2>
          <p className="hint">
            Optional details used when filling application forms. Demographic questions are always
            skipped — the agent never guesses those.
          </p>
          <div className="extras-grid">
            {[
              ["linkedin_url", "LinkedIn URL"],
              ["portfolio_url", "Portfolio / GitHub URL"],
              ["salary_expectation", "Salary expectation"],
              ["work_authorization", "Work authorization (e.g. 'US citizen', 'Needs sponsorship')"],
              ["availability", "Availability / start date"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  value={extras[key]}
                  onChange={(e) => setExtras({ ...extras, [key]: e.target.value })}
                />
              </label>
            ))}
          </div>
          <button onClick={saveExtras} disabled={busy}>Save extras</button>
          {savedMsg && <span className="ok"> {savedMsg}</span>}
        </>
      )}
    </div>
  );
}

function TagList({ label, items }) {
  if (!items?.length) return null;
  return (
    <div className="tags-block">
      <strong>{label}:</strong>{" "}
      {items.map((s, i) => (
        <span className="tag" key={i}>{s}</span>
      ))}
    </div>
  );
}
