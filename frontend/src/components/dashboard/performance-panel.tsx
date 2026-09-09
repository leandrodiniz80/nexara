import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FailureState, WorkdayPerformance } from "@/lib/api/workday";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

// Same red/yellow/green mapping the Command Center uses for failureState —
// section 7's "reforço psicológico" applied consistently in both places.
const STATE_STYLES: Record<FailureState, { border: string; bg: string; text: string }> = {
  failing: { border: "border-destructive/40", bg: "bg-destructive/10", text: "text-destructive" },
  at_risk: { border: "border-warning/40", bg: "bg-warning/10", text: "text-warning" },
  on_track: { border: "border-success/40", bg: "bg-success/10", text: "text-success" },
};

export function PerformancePanel({ performance }: { performance: WorkdayPerformance }) {
  const style = STATE_STYLES[performance.failureState];
  const completionPct = Math.min(performance.completionRate * 100, 100);

  return (
    <Card className={`${style.border} ${style.bg}`}>
      <CardHeader>
        <CardTitle className="text-foreground">Sua performance</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className={`text-sm font-semibold ${style.text}`}>
          {performance.accountabilityMessage}
        </p>

        <div>
          <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
            <span>Taxa de conclusão</span>
            <span>{(performance.completionRate * 100).toFixed(0)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                performance.failureState === "failing"
                  ? "bg-destructive"
                  : performance.failureState === "at_risk"
                    ? "bg-warning"
                    : "bg-success"
              }`}
              style={{ width: `${completionPct}%` }}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
          <div>
            <p className="text-lg font-semibold text-foreground">{performance.streakDays}</p>
            <p className="text-xs text-muted-foreground">Dias seguidos</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-destructive">{performance.overdueTasks}</p>
            <p className="text-xs text-muted-foreground">Atrasadas</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">
              {performance.leadsIgnoredYesterday}
            </p>
            <p className="text-xs text-muted-foreground">Ignorados ontem</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">
              R$ {formatBRL(performance.estimatedRevenueLost)}
            </p>
            <p className="text-xs text-muted-foreground">Em risco</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
