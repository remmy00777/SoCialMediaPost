"use client";

import { ReactNode, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<{ system_status: string }>("/api/system/overview")
      .then((data) => setPaused(data.system_status === "paused"))
      .catch(() => undefined);
  }, []);

  async function togglePause() {
    setBusy(true);
    setMessage("");
    try {
      await api(paused ? "/api/system/resume" : "/api/system/pause", { method: "POST" });
      setPaused(!paused);
      setMessage(paused ? "Automation resumed." : "All automation paused.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update automation state.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <header className="topbar">
          <div><strong>Control Center</strong><span className={paused ? "status paused" : "status live"}>{paused ? "Paused" : "Operational"}</span></div>
          <button className={paused ? "button primary" : "button danger"} onClick={togglePause} disabled={busy}>{paused ? "Resume Automation" : "Pause All Automation"}</button>
        </header>
        {message && <div className="notice" role="status">{message}</div>}
        {children}
      </main>
    </div>
  );
}
