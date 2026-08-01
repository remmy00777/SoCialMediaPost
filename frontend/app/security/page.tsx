import { DataPage } from "@/components/DataPage";
export default function Page() { return <DataPage title="Security" description="Verify localhost binding, authentication, CSRF, CSP, encrypted OAuth storage, Keychain integration, prompt-injection isolation, and the emergency pause control." endpoint="/api/security/status" />; }
