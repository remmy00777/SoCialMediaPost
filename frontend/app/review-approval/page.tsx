"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Package = { id: string; title: string; status: string; quality_score: number; variants: Array<{ platform: string; status: string }> };
export default function ReviewApproval() {
  const [items, setItems] = useState<Package[]>([]); const [error, setError] = useState("");
  async function load() { try { setItems(await api<Package[]>("/api/content-packages")); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Unable to load review queue"); } }
  useEffect(() => { void load(); }, []);
  async function act(id: string, action: "approve" | "reject") { if (action === "reject" && !window.confirm("Reject and archive this package?")) return; try { await api(`/api/content-packages/${id}/${action}`, { method: "POST", body: JSON.stringify({ reason: action === "approve" ? "Reviewed in portal" : "Rejected in portal" }) }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Review action failed"); } }
  return <section><div className="page-heading"><div><p className="eyebrow">Human control</p><h1>Review and Approval</h1><p>Automatic publishing remains blocked until authorization, eligibility, media, policy, originality, disclosure, quota, timing, and user settings pass a fresh validation.</p></div></div>{error && <div className="error">{error}</div>}<div className="grid">{items.map((item) => <article className="card wide" key={item.id}><span className="pill">{item.status}</span><h2>{item.title}</h2><p className="muted">Quality score: {item.quality_score}. Variants: {item.variants.map((v) => `${v.platform} ${v.status}`).join(", ")}.</p><div className="action-row"><button className="button primary" onClick={() => act(item.id, "approve")}>Approve</button><button className="button danger" onClick={() => act(item.id, "reject")}>Reject</button></div></article>)}</div></section>;
}
