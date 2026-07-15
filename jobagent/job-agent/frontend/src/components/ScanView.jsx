import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

export default function ScanView({ onDone }) {
  const [urlsText, setUrlsText] = useState("");
  const [scans, setScans] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const timerRef = useRef(null);

  const refresh = async () => {
    try {
      const res = await api.listScans();
      setScans(res.scans);
      const active = res.scans.some((s) => s.status === "pending" || s.status === "running");
      if (!active && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    refresh();
    return () => timerRef.current && clearInterval(timerRef.current);
  }, []);

  const startScan = async () => {
    const urls = urlsText
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (!urls.length) return;
    if (urls.some((u) => u.toLowerCase().includes("linkedin.com"))) {
      setError("LinkedIn URLs are not supported. Use the company's own careers page.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.createScans(urls);
      setUrlsText("");
      await refresh();
      if (!timerRef.current) timerRef.current = setInterval(refresh, 3000);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const anyRunning = scans.some((s) => s.status === "pending" || s.status === "running");

  return (
    <div className="panel">
      <h2>Scan company career pages</h2>
      <p className="hint">
        Paste one or more company career page URLs (one per line). Greenhouse, Lever, Ashby and
        Workable boards work best; other pages are scanned generically. LinkedIn is not supported.
      </p>
      <textarea
        rows={4}
        placeholder={"https://boards.greenhouse.io/company\nhttps://jobs.lever.co/company\nhttps://company.com/careers"}
        value={urlsText}
        onChange={(e) => setUrlsText(e.target.value)}
      />
      <button className="primary" onClick={startScan} disabled={busy || !urlsText.trim()}>
        {busy ? "Starting..." : "Scan for jobs"}
      </button>
      {error && <p className="error">{error}</p>}

      {scans.length > 0 && (
        <>
          <h3>Scans</h3>
          <table>
            <thead>
              <tr>
                <th>Career page</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {scans.map((s) => (
                <tr key={s.id}>
                  <td className="mono">{s.url}</td>
                  <td>
                    <span className={`status status-${s.status}`}>{s.status}</span>
                  </td>
                  <td>
                    {s.jobs_found > 0
                      ? `${s.jobs_processed}/${s.jobs_found} jobs`
                      : s.status === "running"
                        ? "finding jobs..."
                        : "—"}
                  </td>
                  <td className="hint">{s.message || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!anyRunning && scans.some((s) => s.status === "completed") && (
            <button className="primary" onClick={onDone}>
              View job matches →
            </button>
          )}
        </>
      )}
    </div>
  );
}
