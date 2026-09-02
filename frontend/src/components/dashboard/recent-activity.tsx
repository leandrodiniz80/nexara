import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeadActivityFeedEntry } from "@/lib/api/leads";
import { formatRelativeTime } from "@/lib/utils/format";

export function RecentActivity({ entries }: { entries: LeadActivityFeedEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-foreground">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No activity yet.</p>
        ) : (
          <ul className="space-y-3">
            {entries.map((entry, index) => (
              <li
                key={`${entry.leadId}-${entry.createdAt}-${index}`}
                className="flex items-start justify-between gap-4 text-sm"
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
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
