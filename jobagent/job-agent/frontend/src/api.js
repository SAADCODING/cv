const BASE = "";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* not json */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  getProfile: () => request("/api/resume"),
  uploadResumeFile: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/resume", { method: "POST", body: form });
  },
  uploadResumeText: (text) => {
    const form = new FormData();
    form.append("text", text);
    return request("/api/resume", { method: "POST", body: form });
  },
  updateProfile: (update) =>
    request("/api/resume", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    }),

  createScans: (urls) =>
    request("/api/scans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    }),
  listScans: () => request("/api/scans"),

  listJobs: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    return request("/api/jobs" + (qs ? `?${qs}` : ""));
  },
  getJob: (id) => request(`/api/jobs/${id}`),
  generateAnswers: (jobId, questions) =>
    request(`/api/jobs/${jobId}/answers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions }),
    }),

  startApplication: (jobId) => request(`/api/jobs/${jobId}/apply`, { method: "POST" }),
  getApplication: (id) => request(`/api/applications/${id}`),
  editField: (id, field_id, value) =>
    request(`/api/applications/${id}/fields`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ field_id, value }),
    }),
  confirmSubmission: (id) =>
    request(`/api/applications/${id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    }),
  cancelApplication: (id) => request(`/api/applications/${id}/cancel`, { method: "POST" }),
  screenshotUrl: (id) => `/api/applications/${id}/screenshot?t=${Date.now()}`,
};
