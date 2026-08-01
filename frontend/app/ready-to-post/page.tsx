"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Package = { id: string; title: string; status: string; variants: Array<{ platform: "youtube" | "tiktok" | "instagram"; status: string; media_path: string }> };
export default function ReadyToPost() {
  const [items, setItems] = useState<Package[]>([]); const [error, setError] = useState("");
  async function load() { try { setItems((await api<Package[]>("/api/content-packages")).filter((p) => p.status === "ready_to_post")); } catch (e) { setError(e instanceof Error ? e.message : "Unable to load library"); } }
  useEffect(() => { void load(); }, []);
  async function simulate(id: string, platform: string) { try { await api(`/api/content-packages/${id}/publish`, { method: "POST", body: JSON.stringify({ platform, simulate: true }) }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Publishing simulation failed"); } }
  return <section><div className="page-heading"><div><p className="eyebrow">Manual and controlled publishing</p><h1>Ready-to-Post Library</h1><p>Approved packages are mirrored into plain folders for TikTok, Instagram, and YouTube. Simulation proves queue behavior without contacting a platform.</p></div></div>{error && <div className="error">{error}</div>}<div className="grid">{items.map((item) => <article className="card full" key={item.id}><h2>{item.title}</h2><div className="table-wrap"><table><thead><tr><th>Platform</th><th>Status</th><th>Media</th><th>Action</th></tr></thead><tbody>{item.variants.map((v) => <tr key={v.platform}><td>{v.platform}</td><td>{v.status}</td><td>{v.media_path}</td><td><button className="button" onClick={() => simulate(item.id, v.platform)}>Simulate Publish</button></td></tr>)}</tbody></table></div></article>)}</div></section>;
}
