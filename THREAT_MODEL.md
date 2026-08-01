# Threat Model

## OAuth token theft

Mitigations: encrypted server-side storage, Keychain-backed key, redaction, least privilege, no frontend exposure, reconnect on refresh failure, localhost callbacks.

## Malicious media

Mitigations: size and extension limits, safe names, path containment, ffprobe validation, subprocess argument arrays, quarantine state, optional malware scanner interface.

## Prompt injection from captions or transcripts

Mitigations: platform text is serialized as untrusted evidence, never concatenated as system instructions, tool invocation is not exposed to source data, and generated interpretations carry assumptions and confidence.

## Poisoned trend data

Mitigations: source attribution, raw-response retention, confidence penalties, metric plausibility checks, cross-source deduplication, manual review, and no fabricated missing values.

## Compromised provider

Mitigations: provider isolation, timeouts, schema validation, cost limits, policy gates, circuit state, audit events, and replaceable adapters.

## Unauthorized local access

Mitigations: localhost-only binding, password authentication, secure cookies, launchd user scope, restricted secret files, and audit events.

## Accidental public exposure

Mitigations: host validation rejects nonlocal binding, Compose publishes only localhost ports, frame embedding is denied, and docs prohibit tunnels without review.

## Duplicate publishing

Mitigations: unique idempotency keys, platform post IDs, preflight duplicate status, persistent job records, and retry-safe polling.

## Data exfiltration

Mitigations: no source-controlled secrets, local-only defaults, provider allowlists, SSRF boundary checks, redaction, and limited notification content.

## Supply-chain attack

Mitigations: pinned major dependencies, image provenance review, SBOM, dependency audit commands, secret scanning, and isolated build stages.
