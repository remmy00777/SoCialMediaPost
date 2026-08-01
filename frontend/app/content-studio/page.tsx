"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Package = { id: string; title: string; status: string; quality_score: number; predicted_performance: Record<string, unknown>; variants: Array<{ id: string; platform: string; status: string; media_path: string }> };
export default function ContentStudio() {
  const [packages, setPackages] = useState<Package[]>([]); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function load() { try { setPackages(await api<Package[]>("/api/content-packages")); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Unable to load packages"); } }
  useEffect(() => { void load(); }, []);
  async function generate() { setBusy(true); try { await api("/api/workflows/content?max_items=10", { method: "POST" }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Generation failed"); } finally { setBusy(false); } }
  return <section><div className="page-heading"><div><p className="eyebrow">Original production pipeline</p><h1>Content Studio</h1><p>Generate internally scored concepts, original scripts, platform adaptations, videos, captions, thumbnails, compliance reports, and editable content packages.</p></div><button className="button primary" disabled={busy} onClick={generate}>{busy ? "Generating..." : "Generate Selected Trends"}</button></div>{error && <div className="error">{error}</div>}<div className="grid">{packages.map((item) => <article className="card wide" key={item.id}><span className="pill">{item.status}</span><h2>{item.title}</h2><p className="metric">{item.quality_score.toFixed(1)}</p><p className="muted">Quality score. Performance forecast is a heuristic, never a virality promise.</p><div className="action-row">{item.variants.map((v) => <span className="pill" key={v.id}>{v.platform}: {v.status}</span>)}</div></article>)}</div></section>;
}
