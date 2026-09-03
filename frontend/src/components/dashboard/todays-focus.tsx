"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import type { Lead } from "@/lib/api/leads";
import { copyToClipboard } from "@/lib/utils/clipboard";

export function TodaysFocus({
  leads,
  onOpenDetails,
  onCompleteTask,
  completingLeadId,
}: {
  leads: Lead[];
  onOpenDetails: (lead: Lead) => void;
  onCompleteTask?: (lead: Lead) => void;
  completingLeadId?: string;
}) {
  const focusLeads = leads.slice(0, 5);
  const { showToast } = useToast();

  async function handleCopyApproach(lead: Lead) {
    if (!lead.suggestedMessage) return;
    if (await copyToClipboard(lead.suggestedMessage)) {
      showToast("Mensagem copiada");
    }
  }

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
                  {lead.nextBestAction && (
                    <p className="truncate text-xs font-medium text-primary">
                      👉 {lead.nextBestAction}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge variant={lead.isOverdue ? "destructive" : lead.score < 31 ? "destructive" : "warning"}>
                    {lead.isOverdue ? `Overdue ${lead.daysOverdue}d` : `Score ${lead.score}`}
                  </Badge>
                  {lead.suggestedMessage && (
                    <Button size="sm" variant="outline" onClick={() => handleCopyApproach(lead)}>
                      Copiar abordagem
                    </Button>
                  )}
                  {lead.nextAction && onCompleteTask && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={completingLeadId === lead.id}
                      onClick={() => onCompleteTask(lead)}
                    >
                      Marcar como feito
                    </Button>
                  )}
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
