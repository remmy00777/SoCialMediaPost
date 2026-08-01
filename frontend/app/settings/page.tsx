import { DataPage } from "@/components/DataPage";
export default function Page() { return <DataPage title="Settings" description="Review operating state, storage, platform connections, configured limits, scheduler state, and whether demonstration or automatic publishing modes are enabled." endpoint="/api/system/overview" />; }
