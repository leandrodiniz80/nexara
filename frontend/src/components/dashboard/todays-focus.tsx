import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Lead } from "@/lib/api/leads";

export function TodaysFocus({
  leads,
  onOpenDetails,
}: {
  leads: Lead[];
  onOpenDetails: (lead: Lead) => void;
}) {
  const focusLeads = leads.slice(0, 5);

  return (
    <Card className="border-primary/30">
      <CardHeader>
        <CardTitle className="text-foreground">Leads that need you today</CardTitle>
      </CardHeader>
      <CardContent>
        {focusLeads.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing urgent — you&apos;re all caught up.</p>
        ) : (
          <ul className="space-y-3">
            {focusLeads.map((lead) => (
              <li key={lead.id} className="flex items-center justify-between gap-4 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium text-foreground">{lead.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {lead.nextAction ?? `Score ${lead.score}`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge variant={lead.score < 31 ? "destructive" : "warning"}>
                    Score {lead.score}
                  </Badge>
                  <Button size="sm" variant="outline" onClick={() => onOpenDetails(lead)}>
                    View
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
