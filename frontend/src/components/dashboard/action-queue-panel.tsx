"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ActionQueueItem } from "@/lib/api/workday";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

// Same three-tier treatment LeadCard's own RISK_BADGE_STYLE uses
// (dealRiskLevel) — kept as its own copy here rather than a shared import
// since this panel's rows aren't full Lead objects and "low"/null render no
// badge at all here too, same "quiet default" rule.
const RISK_BADGE_STYLE: Record<"critical" | "high" | "medium", { className: string; label: string }> = {
  critical: {
    className: "border-transparent bg-destructive/15 text-destructive",
    label: "🔥 Crítico",
  },
  high: {
    className: "border-transparent bg-orange-500/15 text-orange-600 dark:text-orange-400",
    label: "Alto",
  },
  medium: {
    className: "border-transparent bg-warning/15 text-warning",
    label: "Médio",
  },
};

/** Execution-engine round — Task 7's "Fila de execução (Top 10)": the
 * action queue GET /workday/action-queue returns (build_action_queue(),
 * backend), rendered as a short, scannable list. Each row's "Botão direto"
 * calls onOpenLead with just the leadId — the caller resolves that against
 * whatever full Lead objects it already has cached to open the details
 * modal (this panel never fetches full leads itself). */
export function ActionQueuePanel({
  items,
  onOpenLead,
}: {
  items: ActionQueueItem[];
  onOpenLead: (leadId: string) => void;
}) {
  if (items.length === 0) return null;

  return (
    <Card className="border-primary/30">
      <CardHeader>
        <CardTitle className="text-foreground">Fila de execução (Top 10)</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {items.map((item, index) => (
            <li key={item.leadId} className="flex items-center justify-between gap-4 text-sm">
              <div className="min-w-0">
                <p className="truncate font-medium text-foreground">
                  #{index + 1} {item.name}
                </p>
                {item.nextBestAction && (
                  <p className="truncate text-xs font-medium text-primary">
                    👉 {item.nextBestAction}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {item.dealRiskLevel && item.dealRiskLevel !== "low" && (
                  <Badge
                    variant="outline"
                    className={
                      RISK_BADGE_STYLE[item.dealRiskLevel as "critical" | "high" | "medium"]
                        ?.className
                    }
                  >
                    {RISK_BADGE_STYLE[item.dealRiskLevel as "critical" | "high" | "medium"]?.label}
                  </Badge>
                )}
                {item.expectedValue > 0 && (
                  <Badge variant="outline">💰 R$ {formatBRL(item.expectedValue)}</Badge>
                )}
                <Button size="sm" variant="outline" onClick={() => onOpenLead(item.leadId)}>
                  Abrir
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
