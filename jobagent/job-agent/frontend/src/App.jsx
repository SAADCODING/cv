import { useEffect, useState } from "react";
import { api } from "./api.js";
import ProfileView from "./components/ProfileView.jsx";
import ScanView from "./components/ScanView.jsx";
import DashboardView from "./components/DashboardView.jsx";
import JobDetail from "./components/JobDetail.jsx";
import ApplicationView from "./components/ApplicationView.jsx";

export default function App() {
  const [tab, setTab] = useState("profile");
  const [profile, setProfile] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [applicationId, setApplicationId] = useState(null);

  useEffect(() => {
    api
      .getProfile()
      .then((res) => {
        if (res.exists) {
          setProfile(res.profile);
          setTab("scan");
        }
      })
      .catch(() => {});
  }, []);

  const openJob = (jobId) => {
    setSelectedJobId(jobId);
    setTab("job");
  };

  const openApplication = (appId) => {
    setApplicationId(appId);
    setTab("application");
  };

  return (
    <div className="app">
      <header>
        <h1>Job Application Agent</h1>
        <nav>
          <button className={tab === "profile" ? "active" : ""} onClick={() => setTab("profile")}>
            1. Resume
          </button>
          <button
            className={tab === "scan" ? "active" : ""}
            onClick={() => setTab("scan")}
            disabled={!profile}
          >
            2. Scan careers pages
          </button>
          <button
            className={tab === "dashboard" ? "active" : ""}
            onClick={() => setTab("dashboard")}
            disabled={!profile}
          >
            3. Job matches
          </button>
          {selectedJobId && (
            <button className={tab === "job" ? "active" : ""} onClick={() => setTab("job")}>
              Job detail
            </button>
          )}
          {applicationId && (
            <button
              className={tab === "application" ? "active" : ""}
              onClick={() => setTab("application")}
            >
              Application
            </button>
          )}
        </nav>
      </header>

      <main>
        {tab === "profile" && <ProfileView profile={profile} onProfile={setProfile} />}
        {tab === "scan" && <ScanView onDone={() => setTab("dashboard")} />}
        {tab === "dashboard" && <DashboardView onOpenJob={openJob} />}
        {tab === "job" && selectedJobId && (
          <JobDetail jobId={selectedJobId} onApplicationStarted={openApplication} />
        )}
        {tab === "application" && applicationId && (
          <ApplicationView applicationId={applicationId} />
        )}
      </main>

      <footer>
        <p>
          This assistant never submits an application without your explicit confirmation. It does
          not scan LinkedIn, does not mass-apply, and respects robots.txt.
        </p>
      </footer>
    </div>
  );
}
