import { memo } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatBRL } from "@/components/console/format-brl";
import { cn } from "@/lib/utils/cn";
import type { ConsoleTopPriority } from "@/lib/api/system";

const URGENCY_VARIANT: Record<string, "destructive" | "warning" | "secondary"> = {
  high: "destructive",
  medium: "warning",
  low: "secondary",
};

// The backend's urgency values (next_best_action_urgency, scoring.py) are
// raw English tokens — translated here only for display, same spirit as
// URGENCY_VARIANT above. An unrecognized value (none exist today — always
// "high"/"medium"/"low" or the "low" default) falls back to "Média" rather
// than echoing the raw token, so no English can ever reach the screen.
const URGENCY_LABEL: Record<string, string> = {
  high: "Alta",
  medium: "Média",
  low: "Baixa",
};

function urgencyLabel(urgency: string): string {
  return URGENCY_LABEL[urgency] ?? "Média";
}

export const LeadCard = memo(function LeadCard({
  priority,
  isExecuting = false,
  isPrimaryTarget = false,
}: {
  priority: ConsoleTopPriority;
  isExecuting?: boolean;
  /** True for the one lead EXECUTAR AGORA actually acts on (topPriorityLeadId,
   * console/page.tsx) — a persistent left accent, not just the transient
   * isExecuting tint, so it's never ambiguous which of the 3 cards below
   * is the one the button above refers to. */
  isPrimaryTarget?: boolean;
}) {
  return (
    <Card
      className={cn(
        "border-l-4 transition-all duration-150",
        isPrimaryTarget ? "border-l-primary" : "border-l-transparent",
        isExecuting
          ? "border-primary/50 bg-primary/5"
          : "hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md"
      )}
    >
      <CardContent className="flex items-center justify-between gap-4 py-6">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium text-foreground">{priority.name}</p>
            <Badge
              variant={URGENCY_VARIANT[priority.urgency] ?? "secondary"}
              className="font-bold uppercase tracking-wide"
            >
              {urgencyLabel(priority.urgency)}
            </Badge>
            {isExecuting && (
              <span className="flex items-center gap-1 text-xs font-medium text-primary">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary motion-reduce:animate-none" />
                Executando…
              </span>
            )}
          </div>
          {priority.action && (
            <p className="mt-2 truncate text-xs text-muted-foreground">{priority.action}</p>
          )}
        </div>
        <p className="shrink-0 text-2xl font-bold tabular-nums text-foreground">
          {formatBRL(priority.value)}
        </p>
      </CardContent>
    </Card>
  );
});
