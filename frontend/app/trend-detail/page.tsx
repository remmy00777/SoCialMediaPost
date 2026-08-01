"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { JsonView } from "@/components/JsonView";

type Trend = { candidate_id: string; title?: string; platform: string };
type SourceMedia = { id: string; original_filename: string; rights_status: string; rights_owner: string; size_bytes: number };

export default function TrendDetail() {
  const [trends, setTrends] = useState<Trend[]>([]);
  const [candidateId, setCandidateId] = useState("");
  const [detail, setDetail] = useState<unknown>(null);
  const [sourceMedia, setSourceMedia] = useState<SourceMedia | null>(null);
  const [error, setError] = useState("");

  async function loadTrends() {
    try {
      const rows = await api<Trend[]>("/api/trends");
      setTrends(rows);
      if (!candidateId && rows[0]) setCandidateId(rows[0].candidate_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load trends");
    }
  }

  async function loadDetail(id = candidateId) {
    if (!id) return;
    try {
      const [record, media] = await Promise.all([
        api(`/api/trends/${id}`),
        api<{ source_media: SourceMedia | null }>(`/api/trends/${id}/source-media`),
      ]);
      setDetail(record);
      setSourceMedia(media.source_media);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load trend detail");
    }
  }

  useEffect(() => { void loadTrends(); }, []);
  useEffect(() => { void loadDetail(candidateId); }, [candidateId]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await api(`/api/trends/${candidateId}/source-media`, { method: "POST", body: new FormData(event.currentTarget) });
      await loadDetail();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed");
    }
  }

  async function remove() {
    if (window.prompt("Type DELETE to permanently remove the uploaded source clip.") !== "DELETE") return;
    try {
      await api(`/api/trends/${candidateId}/source-media`, { method: "DELETE", body: JSON.stringify({ confirmation: "DELETE" }) });
      await loadDetail();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Deletion failed");
    }
  }

  return (
    <section>
      <div className="page-heading"><div><p className="eyebrow">Evidence and authorized media</p><h1>Trend Detail</h1><p>Inspect a trend, then optionally upload a clip you own or are licensed to reuse.</p></div></div>
      {error && <div className="error">{error}</div>}
      <div className="panel">
        <label>Trend candidate <select value={candidateId} onChange={(event) => setCandidateId(event.target.value)}>{trends.map((trend) => <option key={trend.candidate_id} value={trend.candidate_id}>{trend.platform}: {trend.title ?? trend.candidate_id}</option>)}</select></label>
      </div>
      <div className="panel">
        <h2>Authorized clip remix</h2>
        {sourceMedia && <><JsonView value={sourceMedia} /><button className="button danger" onClick={remove}>Delete source clip</button></>}
        <form onSubmit={upload} className="form-grid">
          <label>Video file<input type="file" name="file" accept="video/mp4,video/quicktime,video/webm,video/x-m4v" required /></label>
          <label>Rights status<select name="rights_status" defaultValue="user_owned"><option value="user_owned">I own it</option><option value="licensed">Licensed</option><option value="explicit_permission">Explicit permission</option><option value="public_domain">Public domain</option></select></label>
          <label>Rights owner<input name="rights_owner" required /></label>
          <label>License or permission reference<input name="license_reference" /></label>
          <label><input type="checkbox" name="allow_full_reuse" value="true" required /> I confirm full reuse and publication are permitted.</label>
          <button className="button primary" type="submit">Upload authorized clip</button>
        </form>
      </div>
      <div className="panel"><JsonView value={detail ?? { status: "Select a trend" }} /></div>
    </section>
  );
}
