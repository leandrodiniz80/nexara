"use client";

import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeadActivityFeedEntry } from "@/lib/api/leads";
import { formatRelativeTime } from "@/lib/utils/format";

export function RecentActivity({ entries }: { entries: LeadActivityFeedEntry[] }) {
  const router = useRouter();
  const visible = entries.slice(0, 10);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-foreground">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {visible.length === 0 ? (
          <p className="text-sm text-muted-foreground">No activity yet.</p>
        ) : (
          <ul className="space-y-3">
            {visible.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => router.push(`/leads?lead=${entry.leadId}`)}
                  className="flex w-full items-start justify-between gap-4 text-left text-sm hover:opacity-80"
                >
                  <div>
                    <p className="text-foreground">
                      <span className="font-medium">{entry.leadName}</span>
                    </p>
                    <p className="text-xs text-muted-foreground">{entry.message}</p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatRelativeTime(entry.createdAt)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
