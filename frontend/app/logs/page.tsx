import { DataPage } from "@/components/DataPage";
export default function Page() { return <DataPage title="Logs and Audit" description="Review redacted audit events. Structured runtime logs are also written to the configured log destination without secrets or OAuth tokens." endpoint="/api/audit-events" />; }
