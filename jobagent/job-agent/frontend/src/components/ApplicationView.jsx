import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const ACTIVE_STATUSES = ["filling"];

export default function ApplicationView({ applicationId }) {
  const [app, setApp] = useState(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null); // field_id being edited
  const [editValue, setEditValue] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [screenshotKey, setScreenshotKey] = useState(0);
  const timerRef = useRef(null);

  const refresh = async () => {
    try {
      const a = await api.getApplication(applicationId);
      setApp(a);
      setScreenshotKey((k) => k + 1);
      if (!ACTIVE_STATUSES.includes(a.status) && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => {
    setApp(null);
    setConfirming(false);
    refresh();
    timerRef.current = setInterval(refresh, 3000);
    return () => timerRef.current && clearInterval(timerRef.current);
  }, [applicationId]);

  if (error && !app) return <div className="panel"><p className="error">{error}</p></div>;
  if (!app) return <div className="panel"><p>Loading…</p></div>;

  const saveEdit = async (field_id) => {
    setBusy(true);
    setError("");
    try {
      const updated = await api.editField(applicationId, field_id, editValue);
      setApp(updated);
      setEditing(null);
      setScreenshotKey((k) => k + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const updated = await api.confirmSubmission(applicationId);
      setApp(updated);
      setConfirming(false);
      setScreenshotKey((k) => k + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    setBusy(true);
    try {
      const updated = await api.cancelApplication(applicationId);
      setApp(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <h2>Application</h2>
      <p>
        <span className={`status status-${app.status}`}>{app.status.replaceAll("_", " ")}</span>{" "}
        <span className="hint">{app.message}</span>
      </p>

      {app.status === "filling" && <p>Filling the form… this can take a minute or two.</p>}

      {app.fields?.length > 0 && (
        <>
          <h3>Filled form fields</h3>
          <table>
            <thead>
              <tr><th>Field</th><th>Action</th><th>Value</th><th></th></tr>
            </thead>
            <tbody>
              {app.fields.map((f) => (
                <tr key={f.field_id} className={f.status === "error" ? "row-error" : ""}>
                  <td>{f.label}</td>
                  <td>
                    <span className={`rec rec-${f.action === "skip" ? "skip" : "apply"}`}>
                      {f.action}
                    </span>
                    {f.reason && <div className="hint">{f.reason}</div>}
                  </td>
                  <td className="value-cell">
                    {editing === f.field_id ? (
                      <textarea
                        rows={f.type === "textarea" ? 5 : 1}
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                      />
                    ) : (
                      <span>{f.value ?? "—"}</span>
                    )}
                  </td>
                  <td>
                    {app.status === "ready_for_review" &&
                      (f.action === "fill" || f.action === "select" || f.action === "skip") &&
                      f.kind !== "input" && null}
                    {app.status === "ready_for_review" && f.action !== "upload_resume" && f.type !== "checkbox" && f.type !== "radio" && (
                      editing === f.field_id ? (
                        <>
                          <button onClick={() => saveEdit(f.field_id)} disabled={busy}>Save</button>{" "}
                          <button onClick={() => setEditing(null)}>Cancel</button>
                        </>
                      ) : (
                        <button
                          onClick={() => {
                            setEditing(f.field_id);
                            setEditValue(typeof f.value === "string" ? f.value : "");
                          }}
                        >
                          Edit
                        </button>
                      )
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {app.has_screenshot && (
        <>
          <h3>Form preview (live screenshot)</h3>
          <img
            key={screenshotKey}
            className="screenshot"
            src={api.screenshotUrl(applicationId)}
            alt="Application form screenshot"
          />
        </>
      )}

      {app.status === "ready_for_review" && !confirming && (
        <div className="confirm-bar">
          <button className="primary big" onClick={() => setConfirming(true)}>
            Continue to submission…
          </button>
          <button onClick={cancel} disabled={busy}>Cancel application</button>
        </div>
      )}

      {app.status === "ready_for_review" && confirming && (
        <div className="confirm-modal">
          <h3>Final confirmation</h3>
          <p>
            <strong>
              Your application has been filled out. Please review all information carefully before
              submitting. Do you want to submit this application?
            </strong>
          </p>
          <div className="confirm-actions">
            <button
              onClick={() => {
                setConfirming(false);
                document.querySelector(".screenshot")?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              Review application
            </button>
            <button onClick={() => setConfirming(false)}>Edit answers</button>
            <button className="danger" onClick={submit} disabled={busy}>
              {busy ? "Submitting…" : "Submit application"}
            </button>
          </div>
        </div>
      )}

      {app.status === "submitted" && (
        <p className="ok">✓ Application submitted. Check the screenshot above and your email for confirmation.</p>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  );
}
