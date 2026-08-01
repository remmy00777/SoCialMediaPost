"use client";

import { useEffect, useState } from "react";
import { API_BASE, api } from "@/lib/api";

type Variant = { id: string; platform: string; media_path: string; thumbnail_path: string; metadata_json: { title?: string; caption?: string } };
type Package = { id: string; title: string; variants: Variant[] };
export default function VideoPreview() {
  const [packages, setPackages] = useState<Package[]>([]); const [selected, setSelected] = useState<Variant | null>(null); const [error, setError] = useState("");
  useEffect(() => { api<Package[]>("/api/content-packages").then((data) => { setPackages(data); setSelected(data[0]?.variants[0] ?? null); }).catch((e) => setError(e.message)); }, []);
  return <section><div className="page-heading"><div><p className="eyebrow">Rendered media validation</p><h1>Video Preview</h1><p>Preview the actual generated MP4, review the platform metadata, and confirm captions and safe-area layout before approval.</p></div></div>{error && <div className="error">{error}</div>}<div className="grid"><div className="card wide"><div className="field"><label>Variant</label><select value={selected?.id ?? ""} onChange={(e) => setSelected(packages.flatMap((p) => p.variants).find((v) => v.id === e.target.value) ?? null)}>{packages.flatMap((p) => p.variants).map((v) => <option value={v.id} key={v.id}>{v.platform}: {v.metadata_json.title}</option>)}</select></div>{selected && <video controls crossOrigin="use-credentials" src={`${API_BASE}/api/files?path=${encodeURIComponent(selected.media_path)}`} />}</div><div className="card wide"><h2>{selected?.metadata_json.title ?? "No rendered package"}</h2><p className="muted">{selected?.metadata_json.caption}</p><p className="muted">Platform: {selected?.platform}</p></div></div></section>;
}
