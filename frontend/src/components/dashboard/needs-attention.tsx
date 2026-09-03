import type { MouseEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Lead, LeadStatus } from "@/lib/api/leads";
import { formatRelativeTime } from "@/lib/utils/format";

/** Stops the "Marcar como feito" click from also triggering the row's own
 * onOpenDetails — same pattern LeadCard uses for its "⋮" menu. */
function stopRowClick(event: MouseEvent) {
  event.stopPropagation();
}

const STATUS_LABEL: Record<LeadStatus, string> = {
  new: "New",
  contacted: "Contacted",
  converted: "Converted",
};

const STATUS_BADGE: Record<LeadStatus, "secondary" | "warning" | "success"> = {
  new: "secondary",
  contacted: "warning",
  converted: "success",
};

export function NeedsAttention({
  leads,
  onOpenDetails,
  onCompleteTask,
  completingLeadId,
}: {
  leads: Lead[];
  onOpenDetails?: (lead: Lead) => void;
  onCompleteTask?: (lead: Lead) => void;
  completingLeadId?: string;
}) {
  const visible = leads.slice(0, 5);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-foreground">Leads Needing Attention</CardTitle>
      </CardHeader>
      <CardContent>
        {visible.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing stale — every active lead has been touched recently.
          </p>
        ) : (
          <ul className="space-y-3">
            {visible.map((lead) => (
              <li key={lead.id}>
                <div
                  onClick={() => onOpenDetails?.(lead)}
                  className="flex w-full cursor-pointer items-center justify-between gap-4 text-left text-sm hover:opacity-80"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-foreground">{lead.name}</span>
                    <Badge variant={lead.isOverdue ? "destructive" : STATUS_BADGE[lead.status]}>
                      {lead.isOverdue ? `Overdue ${lead.daysOverdue}d` : STATUS_LABEL[lead.status]}
                    </Badge>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      Idle since {formatRelativeTime(lead.updatedAt)}
                    </span>
                    {lead.nextAction && onCompleteTask && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={completingLeadId === lead.id}
                        onClick={(event) => {
                          stopRowClick(event);
                          onCompleteTask(lead);
                        }}
                      >
                        Marcar como feito
                      </Button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
