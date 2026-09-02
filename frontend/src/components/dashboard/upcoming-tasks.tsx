import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Lead } from "@/lib/api/leads";
import { formatDate } from "@/lib/utils/format";

export function UpcomingTasks({ leads }: { leads: Lead[] }) {
  const now = Date.now();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-foreground">Upcoming Tasks</CardTitle>
      </CardHeader>
      <CardContent>
        {leads.length === 0 ? (
          <p className="text-sm text-muted-foreground">No next actions scheduled.</p>
        ) : (
          <ul className="space-y-3">
            {leads.map((lead) => {
              const isOverdue = Boolean(
                lead.nextActionDueAt && new Date(lead.nextActionDueAt).getTime() < now
              );

              return (
                <li key={lead.id} className="flex items-center justify-between gap-4 text-sm">
                  <div className="min-w-0">
                    <p className="truncate text-foreground">
                      <span className="font-medium">{lead.name}</span>
                      {lead.nextAction && (
                        <span className="text-muted-foreground"> — {lead.nextAction}</span>
                      )}
                    </p>
                  </div>
                  {lead.nextActionDueAt && (
                    <span
                      className={`shrink-0 text-xs ${isOverdue ? "font-medium text-destructive" : "text-muted-foreground"}`}
                    >
                      {isOverdue ? "Overdue — " : "Due "}
                      {formatDate(lead.nextActionDueAt)}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
