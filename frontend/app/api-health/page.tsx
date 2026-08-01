import { DataPage } from "@/components/DataPage";
export default function Page() { return <DataPage title="API Health" description="Check database, storage, FFmpeg, provider configuration, platform limitations, publishing eligibility, and analytics eligibility." endpoint="/api/health/readiness" />; }
