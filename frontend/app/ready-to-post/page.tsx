"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type Platform = "youtube" | "tiktok" | "instagram";
type Variant = { platform: Platform; status: string; media_path: string };
type Package = { id: string; title: string; status: string; storage_bytes: number; variants: Variant[] };
type Account = { id: string; display_name?: string; external_account_id?: string };
type AccountGroup = { platform: Platform; accounts: Account[] };

function bytes(value: number) {
  const units = ["B", "KB", "MB", "GB"];
  let size = value || 0;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index += 1; }
  return `${size.toFixed(index ? 1 : 0)} ${units[index]}`;
}

export default function ReadyToPost() {
  const [items, setItems] = useState<Package[]>([]);
  const [groups, setGroups] = useState<AccountGroup[]>([]);
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  async function load() {
    try {
      const [packages, accounts] = await Promise.all([
        api<Package[]>("/api/content-packages"),
        api<AccountGroup[]>("/api/accounts"),
      ]);
      setItems(packages.filter((item) => item.status === "ready_to_post"));
      setGroups(accounts);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load library");
    }
  }

  useEffect(() => { void load(); }, []);
  const accountMap = useMemo(() => Object.fromEntries(groups.map((group) => [group.platform, group.accounts])), [groups]);

  async function publish(id: string, platform: Platform, simulate: boolean) {
    try {
      await api(`/api/content-packages/${id}/publish`, {
        method: "POST",
        body: JSON.stringify({ platform, platform_account_id: selected[`${id}:${platform}`] || null, simulate }),
      });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Publishing failed");
    }
  }

  async function remove(id: string) {
    if (window.prompt("Type DELETE to permanently remove this package and all local media files.") !== "DELETE") return;
    try {
      await api(`/api/content-packages/${id}/permanent`, {
        method: "DELETE",
        body: JSON.stringify({ confirmation: "DELETE" }),
      });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Permanent deletion failed");
    }
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Manual and controlled publishing</p>
          <h1>Ready-to-Post Library</h1>
          <p>Select a destination account for each platform, or permanently delete a package to recover storage.</p>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="grid">
        {items.map((item) => (
          <article className="card full" key={item.id}>
            <div className="page-heading">
              <div><h2>{item.title}</h2><p className="muted">Storage: {bytes(item.storage_bytes)}</p></div>
              <button className="button danger" onClick={() => remove(item.id)}>Delete permanently</button>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Platform</th><th>Status</th><th>Destination account</th><th>Action</th></tr></thead>
                <tbody>
                  {item.variants.map((variant) => (
                    <tr key={variant.platform}>
                      <td>{variant.platform}</td><td>{variant.status}</td>
                      <td>
                        <select value={selected[`${item.id}:${variant.platform}`] ?? ""} onChange={(event) => setSelected((current) => ({ ...current, [`${item.id}:${variant.platform}`]: event.target.value }))}>
                          <option value="">Default connected account</option>
                          {(accountMap[variant.platform] ?? []).map((account) => <option key={account.id} value={account.id}>{account.display_name ?? account.external_account_id ?? account.id}</option>)}
                        </select>
                      </td>
                      <td className="action-row">
                        <button className="button" onClick={() => publish(item.id, variant.platform, true)}>Simulate</button>
                        <button className="button primary" onClick={() => publish(item.id, variant.platform, false)}>Publish</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
