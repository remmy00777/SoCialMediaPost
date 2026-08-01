"use client";

import { FormEvent, useState } from "react";
import { api } from "@/lib/api";

export default function Onboarding() {
  const [email, setEmail] = useState("admin@localhost");
  const [password, setPassword] = useState("ChangeThisBeforeUse123!");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function initialize() {
    setError("");
    try { const result = await api<{ email: string }>("/api/auth/bootstrap", { method: "POST" }); setMessage(`Initialized ${result.email}. Change the default password in .env before non-demo use.`); }
    catch (e) { setError(e instanceof Error ? e.message : "Initialization failed"); }
  }
  async function login(event: FormEvent) {
    event.preventDefault(); setError("");
    try { await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }); setMessage("Signed in. The portal can now access protected local APIs."); }
    catch (e) { setError(e instanceof Error ? e.message : "Login failed"); }
  }
  return <section><div className="page-heading"><div><p className="eyebrow">First-run setup</p><h1>Onboarding</h1><p>Initialize the local administrator, sign in, approve a brand profile, configure providers, and connect eligible platform accounts.</p></div></div>{message && <div className="notice">{message}</div>}{error && <div className="error">{error}</div>}<div className="grid"><div className="card wide"><h2>Initialize local application</h2><p className="muted">This action works only once. Credentials come from the local environment file.</p><button className="button primary" onClick={initialize}>Initialize Application</button></div><div className="card wide"><h2>Sign in</h2><form className="form-grid" onSubmit={login}><div className="field"><label>Email</label><input value={email} onChange={(e) => setEmail(e.target.value)} /></div><div className="field"><label>Password</label><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></div><div className="field full"><button className="button" type="submit">Sign In</button></div></form></div><div className="card full"><h2>Connection order</h2><p className="muted">1. Approve the brand profile. 2. Verify FFmpeg and API health. 3. Add OAuth credentials. 4. Connect each account. 5. Run a private test upload. 6. Enable controlled automation only after all gates pass.</p></div></div></section>;
}
