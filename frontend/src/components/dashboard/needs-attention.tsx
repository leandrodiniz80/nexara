import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Lead, LeadStatus } from "@/lib/api/leads";
import { formatRelativeTime } from "@/lib/utils/format";

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

export function NeedsAttention({ leads }: { leads: Lead[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-foreground">Leads Needing Attention</CardTitle>
      </CardHeader>
      <CardContent>
        {leads.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing stale — every active lead has been touched recently.
          </p>
        ) : (
          <ul className="space-y-3">
            {leads.map((lead) => (
              <li key={lead.id} className="flex items-center justify-between gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-foreground">{lead.name}</span>
                  <Badge variant={STATUS_BADGE[lead.status]}>{STATUS_LABEL[lead.status]}</Badge>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  Idle since {formatRelativeTime(lead.updatedAt)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
