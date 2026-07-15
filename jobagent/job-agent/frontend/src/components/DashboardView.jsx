import { useEffect, useState } from "react";
import { api } from "../api.js";
import FitBadge, { categoryLabel } from "./FitBadge.jsx";

const REC_LABEL = { apply: "Apply", maybe: "Maybe", skip: "Skip" };

export default function DashboardView({ onOpenJob }) {
  const [jobs, setJobs] = useState([]);
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .listJobs(category ? { category } : {})
      .then((res) => setJobs(res.jobs))
      .catch((e) => setError(e.message));
  }, [category]);

  return (
    <div className="panel">
      <h2>Job matches</h2>
      <div className="filter-row">
        <label>
          Filter:{" "}
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All jobs</option>
            <option value="strong">Strong fit (0.85–1.00)</option>
            <option value="good">Good fit (0.70–0.84)</option>
            <option value="maybe">Maybe fit (0.55–0.69)</option>
            <option value="weak">Weak fit (&lt;0.55)</option>
          </select>
        </label>
        <span className="hint">{jobs.length} jobs, sorted by fit score</span>
      </div>
      {error && <p className="error">{error}</p>}

      <table className="jobs-table">
        <thead>
          <tr>
            <th>Fit</th>
            <th>Category</th>
            <th>Company</th>
            <th>Job title</th>
            <th>Location</th>
            <th>Work type</th>
            <th>Recommendation</th>
            <th>Matching skills</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="job-row" onClick={() => onOpenJob(job.id)}>
              <td><FitBadge score={job.fit_score} category={job.fit_category} /></td>
              <td>{categoryLabel(job.fit_category)}</td>
              <td>{job.company || "—"}</td>
              <td className="job-title">{job.title || "—"}</td>
              <td>{job.location || "—"}</td>
              <td>{job.work_mode || "—"}</td>
              <td>
                <span className={`rec rec-${job.recommendation}`}>
                  {REC_LABEL[job.recommendation] || "—"}
                </span>
              </td>
              <td className="skills-cell">
                {(job.matching_skills || []).slice(0, 4).map((s, i) => (
                  <span className="tag" key={i}>{s}</span>
                ))}
              </td>
              <td>
                <a href={job.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                  posting ↗
                </a>
              </td>
            </tr>
          ))}
          {jobs.length === 0 && (
            <tr>
              <td colSpan={9} className="hint">
                No jobs yet — run a scan first.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
