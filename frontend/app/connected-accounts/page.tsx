"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Account = { platform: string; health: { status: string; configured: boolean; limitations: string[] }; account?: { authorization_status: string; display_name?: string; token_health: string; granted_permissions: string[]; publishing_eligible: boolean } };

export default function ConnectedAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([]); const [error, setError] = useState("");
  async function load() { try { setAccounts(await api<Account[]>("/api/accounts")); setError(""); } catch (e) { setError(e instanceof Error ? e.message : "Unable to load accounts"); } }
  useEffect(() => { void load(); }, []);
  async function connect(platform: string) { try { const result = await api<{ authorization_url: string }>(`/api/accounts/${platform}/connect`, { method: "POST" }); window.location.assign(result.authorization_url); } catch (e) { setError(e instanceof Error ? e.message : "Connection failed"); } }
  async function action(platform: string, verb: "test" | "disconnect") { try { await api(`/api/accounts/${platform}/${verb}`, { method: "POST" }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); } }
  return <section><div className="page-heading"><div><p className="eyebrow">Official authorization only</p><h1>Connected Accounts</h1><p>No passwords are stored. OAuth tokens are encrypted locally, refreshed when supported, and never exposed to the browser.</p></div><button className="button secondary" onClick={load}>Refresh</button></div>{error && <div className="error">{error}</div>}<div className="grid">{accounts.map((item) => <article className="card wide" key={item.platform}><span className="pill">{item.health.status}</span><h2>{item.platform.toUpperCase()}</h2><p>{item.account?.display_name ?? "Not connected"}</p><p className="muted">Authorization: {item.account?.authorization_status ?? "disconnected"}. Token: {item.account?.token_health ?? "unknown"}. Publishing eligible: {String(item.account?.publishing_eligible ?? false)}.</p><ul className="muted">{item.health.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul><div className="action-row"><button className="button primary" onClick={() => connect(item.platform)}>Connect or Reconnect</button>{item.account && <><button className="button" onClick={() => action(item.platform, "test")}>Test Connection</button><button className="button danger" onClick={() => action(item.platform, "disconnect")}>Disconnect</button></>}</div></article>)}</div></section>;
}
