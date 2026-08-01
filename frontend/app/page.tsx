"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Overview = {
  system_status: string;
  internet_status: string;
  scheduler_status: string;
  pending_approvals: number;
  scheduled_posts: number;
  publishing_failures: number;
  latest_trends: Array<{ id: string; platform: string; title?: string; score: number; confidence: number }>;
  storage_usage: { used_bytes: number; disk_free_bytes: number };
  demo_mode: boolean;
  last_successful_workflow?: { workflow_type: string; status: string; started_at: string };
};

export default function Dashboard() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() { try { setData(await api<Overview>("/api/system/overview")); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Unable to load dashboard"); } }
  useEffect(() => { void load(); }, []);
  async function runDemo() { setBusy(true); try { await api("/api/workflows/demo", { method: "POST" }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Demo workflow failed"); } finally { setBusy(false); } }
  return (
    <section>
      <div className="page-heading"><div><p className="eyebrow">Operations overview</p><h1>Build original content from measurable signals.</h1><p>Discover lawful trend signals, create distinct platform adaptations, review every decision, and publish only after all gates pass.</p></div><div className="action-row"><button className="button primary" onClick={runDemo} disabled={busy}>{busy ? "Running..." : "Run Demonstration Workflow"}</button><button className="button secondary" onClick={load}>Refresh</button></div></div>
      {error && <div className="error">{error} <Link href="/onboarding">Open onboarding</Link></div>}
      <div className="grid">
        <div className="card"><span className="pill">System</span><div className="metric">{data?.system_status ?? "..."}</div><span className="muted">Automation state</span></div>
        <div className="card"><span className="pill">Internet</span><div className="metric">{data?.internet_status ?? "..."}</div><span className="muted">Connectivity check</span></div>
        <div className="card"><span className="pill">Approvals</span><div className="metric">{data?.pending_approvals ?? 0}</div><span className="muted">Waiting for review</span></div>
        <div className="card"><span className="pill">Failures</span><div className="metric">{data?.publishing_failures ?? 0}</div><span className="muted">Publishing queue</span></div>
        <div className="card wide"><h2>Latest trend opportunities</h2>{data?.latest_trends?.length ? <div className="table-wrap"><table><thead><tr><th>Platform</th><th>Trend</th><th>Score</th></tr></thead><tbody>{data.latest_trends.map((trend) => <tr key={trend.id}><td>{trend.platform}</td><td>{trend.title}</td><td>{trend.score.toFixed(1)} <span className="muted">({Math.round(trend.confidence * 100)}% confidence)</span></td></tr>)}</tbody></table></div> : <p className="muted">Run trend discovery or the demonstration workflow to populate this view.</p>}</div>
        <div className="card wide"><h2>System footprint</h2><p className="metric">{data ? (data.storage_usage.used_bytes / 1024 / 1024).toFixed(1) : "0"} MB</p><p className="muted">Local content storage. Scheduler: {data?.scheduler_status ?? "unknown"}.</p><p className="muted">{data?.demo_mode ? "Demonstration mode is enabled. Simulated publications are never presented as real posts." : "Live mode is enabled."}</p></div>
      </div>
    </section>
  );
}
