"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type PlatformAccount = {
  id: string;
  authorization_status: string;
  display_name?: string;
  external_account_id?: string;
  account_type?: string;
  token_health: string;
  granted_permissions: string[];
  publishing_eligible: boolean;
};

type AccountGroup = {
  platform: string;
  health: { status: string; configured: boolean; limitations: string[] };
  accounts: PlatformAccount[];
  multiple_accounts_supported: boolean;
};

export default function ConnectedAccounts() {
  const [groups, setGroups] = useState<AccountGroup[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setGroups(await api<AccountGroup[]>("/api/accounts"));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load accounts");
    }
  }

  useEffect(() => { void load(); }, []);

  async function connect(platform: string) {
    try {
      const result = await api<{ authorization_url: string }>(`/api/accounts/${platform}/connect`, { method: "POST" });
      window.location.assign(result.authorization_url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Connection failed");
    }
  }

  async function accountAction(accountId: string, verb: "test" | "disconnect") {
    try {
      await api(`/api/platform-accounts/${accountId}/${verb}`, { method: "POST" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Account action failed");
    }
  }

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Official authorization only</p>
          <h1>Connected Accounts</h1>
          <p>One application login can connect several accounts per platform. Each OAuth credential is encrypted and managed separately.</p>
        </div>
        <button className="button secondary" onClick={load}>Refresh</button>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="grid">
        {groups.map((group) => (
          <article className="card wide" key={group.platform}>
            <span className="pill">{group.health.status}</span>
            <h2>{group.platform.toUpperCase()}</h2>
            {group.accounts.length === 0 && <p className="muted">No account connected.</p>}
            {group.accounts.map((account) => (
              <div className="list-item" key={account.id}>
                <div>
                  <strong>{account.display_name ?? account.external_account_id ?? group.platform}</strong>
                  <p className="muted">{account.account_type ?? "account"} · {account.authorization_status} · token {account.token_health}</p>
                </div>
                <div className="action-row">
                  <button className="button" onClick={() => accountAction(account.id, "test")}>Test</button>
                  <button className="button danger" onClick={() => accountAction(account.id, "disconnect")}>Disconnect</button>
                </div>
              </div>
            ))}
            <ul className="muted">{group.health.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>
            <button className="button primary" onClick={() => connect(group.platform)}>Connect another account</button>
          </article>
        ))}
      </div>
    </section>
  );
}
