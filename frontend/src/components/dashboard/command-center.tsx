import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FailureState, WorkdayPerformance, WorkdaySummary } from "@/lib/api/workday";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

// Section 7's "reforço psicológico" — same red/yellow/green mapping the
// Performance Panel uses, so a "failing" state reads the same way in both
// places.
const STATE_STYLES: Record<FailureState, { border: string; bg: string; text: string }> = {
  failing: { border: "border-destructive/40", bg: "bg-destructive/10", text: "text-destructive" },
  at_risk: { border: "border-warning/40", bg: "bg-warning/10", text: "text-warning" },
  on_track: { border: "border-success/40", bg: "bg-success/10", text: "text-success" },
};

export function CommandCenter({
  summary,
  performance,
  tasksCompletedToday,
  onStart,
  isStarting,
}: {
  summary: WorkdaySummary;
  /** Optional so the card still renders (with its default look) before
   * GET /workday/performance has loaded — accountability is a layer on top
   * of the existing Command Center, not a hard dependency of it. */
  performance?: WorkdayPerformance;
  /** Leads resolved today, from the same workday-stats counter GET
   * /workday/next already reports — the progress bar's numerator. */
  tasksCompletedToday: number;
  onStart: () => void;
  isStarting: boolean;
}) {
  const remaining = summary.overdueTasks + summary.todayTasks;
  const total = tasksCompletedToday + remaining;
  const progressPct = total > 0 ? (tasksCompletedToday / total) * 100 : 100;
  const stateStyle = performance ? STATE_STYLES[performance.failureState] : null;

  return (
    <Card
      className={
        stateStyle ? `${stateStyle.border} ${stateStyle.bg}` : "border-primary/40 bg-primary/5"
      }
    >
      <CardHeader>
        <CardTitle className="text-foreground">Command Center</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm font-medium text-foreground">{summary.focusMessage}</p>

        {performance && (
          <p className={`text-sm font-semibold ${stateStyle?.text}`}>
            {performance.accountabilityMessage}
          </p>
        )}

        {summary.todayPotentialRevenue > 0 && (
          <p className="text-sm font-semibold text-success">
            Hoje você pode gerar R$ {formatBRL(summary.todayPotentialRevenue)}
          </p>
        )}

        {/* AI Deal Coach round — same >5000 threshold HIGH_VALUE_LEAD_THRESHOLD
            uses backend-side, kept in sync only by convention (this is a
            display-only highlight, not a value the backend needs to send). */}
        {summary.moneyAtRiskToday > 0 && (
          <p
            className={`text-sm font-semibold ${
              summary.moneyAtRiskToday > 5000 ? "text-destructive" : "text-warning"
            }`}
          >
            Você tem R$ {formatBRL(summary.moneyAtRiskToday)} em risco agora
          </p>
        )}

        <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
          <div>
            <p className="text-lg font-semibold text-foreground">{summary.todayTasks}</p>
            <p className="text-xs text-muted-foreground">Tarefas hoje</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-destructive">{summary.overdueTasks}</p>
            <p className="text-xs text-muted-foreground">Atrasadas</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">
              R$ {formatBRL(summary.estimatedRevenueAtRisk)}
            </p>
            <p className="text-xs text-muted-foreground">Em risco</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">
              R$ {formatBRL(summary.revenueAtRisk)}
            </p>
            <p className="text-xs text-muted-foreground">Em risco (ponderado)</p>
          </div>
        </div>

        {total > 0 && (
          <div>
            <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {tasksCompletedToday} de {total} ações concluídas
              </span>
              <span>{progressPct.toFixed(0)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {remaining > 0
                ? `Faltam ${remaining} ações para zerar seu dia`
                : "Dia zerado — nenhuma ação pendente."}
            </p>
          </div>
        )}

        <Button size="lg" className="w-full" onClick={onStart} disabled={isStarting}>
          {isStarting ? "Buscando próximo lead…" : "Começar agora"}
        </Button>
      </CardContent>
    </Card>
  );
}
