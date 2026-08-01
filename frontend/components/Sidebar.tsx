"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const sections = [
  ["Operate", [["Dashboard", "/"], ["Trend Explorer", "/trend-explorer"], ["Content Studio", "/content-studio"], ["Review & Approval", "/review-approval"], ["Publishing Calendar", "/publishing-calendar"], ["Ready to Post", "/ready-to-post"], ["Published Content", "/published-content"]]],
  ["Learn", [["Analytics", "/analytics"], ["Cross-Platform", "/cross-platform"], ["Experiments", "/experiments"], ["Content Concepts", "/content-concepts"], ["Video Preview", "/video-preview"]]],
  ["Configure", [["Onboarding", "/onboarding"], ["Connected Accounts", "/connected-accounts"], ["Brand Profile", "/brand-profile"], ["Content Rules", "/content-rules"], ["Schedules", "/schedules"], ["Providers", "/provider-configuration"], ["Settings", "/settings"]]],
  ["System", [["API Health", "/api-health"], ["Job History", "/job-history"], ["Logs", "/logs"], ["Notifications", "/notifications"], ["Security", "/security"], ["Backup & Restore", "/backup-restore"]]]
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand-mark"><span>S</span><div><strong>SoCialMediaPost</strong><small>Local content operations</small></div></div>
      <nav>
        {sections.map(([section, links]) => (
          <div className="nav-section" key={section}>
            <p>{section}</p>
            {links.map(([label, href]) => (
              <Link className={pathname === href ? "active" : ""} href={href} key={href}>{label}</Link>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
