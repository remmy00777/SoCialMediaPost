import { DataPage } from "@/components/DataPage";
export default function Page() { return <DataPage title="Backup and Restore" description="Create local database and content archives. The command-line restore utility validates paths and requires an explicit archive." endpoint="/api/security/status" actions={[{ label: "Create Backup", path: "/api/backup" }]} />; }
