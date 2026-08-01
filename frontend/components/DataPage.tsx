"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { JsonView } from "@/components/JsonView";

type Action = { label: string; path: string; method?: string; body?: unknown; confirm?: string };

export function DataPage({ title, description, endpoint, actions = [] }: { title: string; description: string; endpoint: string; actions?: Action[] }) {
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try { setData(await api(endpoint)); } catch (err) { setError(err instanceof Error ? err.message : "Unable to load data"); }
  }
  useEffect(() => { void load(); }, [endpoint]);

  async function run(action: Action) {
    if (action.confirm && !window.confirm(action.confirm)) return;
    setBusy(true); setError("");
    try {
      await api(action.path, { method: action.method ?? "POST", body: action.body ? JSON.stringify(action.body) : undefined });
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Action failed"); }
    finally { setBusy(false); }
  }

  return (
    <section>
      <div className="page-heading"><div><p className="eyebrow">SoCialMediaPost</p><h1>{title}</h1><p>{description}</p></div><div className="action-row">{actions.map((action) => <button className="button" disabled={busy} onClick={() => run(action)} key={action.label}>{action.label}</button>)}<button className="button secondary" onClick={load}>Refresh</button></div></div>
      {error && <div className="error" role="alert">{error}</div>}
      <div className="panel"><JsonView value={data ?? { status: "loading" }} /></div>
    </section>
  );
}
