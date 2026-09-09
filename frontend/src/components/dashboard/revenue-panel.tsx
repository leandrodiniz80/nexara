import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RevenueSummary, RevenueTrendDay } from "@/lib/api/revenue";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

function formatDayLabel(isoDate: string): string {
  const [, month, day] = isoDate.split("-");
  return `${day}/${month}`;
}

// Revenue-loop round — "breakdown por ação"'s own labels, same three
// channels the execution engine already recommends (call_now/send_message/
// schedule_meeting), just under the plain nouns revenueByAction's own keys
// use.
const ACTION_BREAKDOWN_LABELS: Record<"call" | "message" | "meeting", string> = {
  call: "📞 Ligações",
  message: "✉️ Mensagens",
  meeting: "🤝 Reuniões",
};

export function RevenuePanel({
  summary,
  trend,
}: {
  summary: RevenueSummary;
  trend: RevenueTrendDay[];
}) {
  // At least 1 so a quiet week (every value 0) still renders empty bars
  // instead of dividing by zero.
  const maxValue = Math.max(1, ...trend.flatMap((day) => [day.created, day.converted, day.lost]));

  const actionBreakdownEntries = (["call", "message", "meeting"] as const).map((action) => ({
    action,
    value: summary.revenueByAction[action],
  }));
  const hasActionBreakdown = actionBreakdownEntries.some((entry) => entry.value > 0);
  // At least 1 so an all-zero breakdown still renders empty bars instead
  // of dividing by zero — same guard maxValue above already uses.
  const maxActionValue = Math.max(1, ...actionBreakdownEntries.map((entry) => entry.value));

  return (
    <Card className="border-primary/40 bg-primary/5">
      <CardHeader>
        <CardTitle className="text-foreground">Revenue Intelligence</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-5">
          <div>
            <p className="text-lg font-semibold text-foreground">
              R$ {formatBRL(summary.potentialRevenue)}
            </p>
            <p className="text-xs text-muted-foreground">Potencial</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-primary">
              R$ {formatBRL(summary.expectedPipelineRevenue)}
            </p>
            <p className="text-xs text-muted-foreground">Esperado (ponderado)</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-success">
              R$ {formatBRL(summary.convertedRevenue)}
            </p>
            <p className="text-xs text-muted-foreground">Convertido</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-destructive">
              R$ {formatBRL(summary.atRiskRevenue)}
            </p>
            <p className="text-xs text-muted-foreground">Em risco</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">
              {(summary.conversionRate * 100).toFixed(0)}%
            </p>
            <p className="text-xs text-muted-foreground">Conversão</p>
          </div>
        </div>

        {trend.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Últimos 7 dias
            </p>
            <div className="flex items-end gap-2">
              {trend.map((day) => (
                <div key={day.date} className="flex flex-1 flex-col items-center gap-1">
                  <div className="flex h-24 items-end gap-0.5">
                    <div
                      className="w-2 rounded-t bg-primary/70"
                      style={{ height: `${(day.created / maxValue) * 100}%` }}
                      title={`Criado: R$ ${formatBRL(day.created)}`}
                    />
                    <div
                      className="w-2 rounded-t bg-success"
                      style={{ height: `${(day.converted / maxValue) * 100}%` }}
                      title={`Convertido: R$ ${formatBRL(day.converted)}`}
                    />
                    <div
                      className="w-2 rounded-t bg-destructive"
                      style={{ height: `${(day.lost / maxValue) * 100}%` }}
                      title={`Perdido: R$ ${formatBRL(day.lost)}`}
                    />
                  </div>
                  <span className="text-[10px] text-muted-foreground">
                    {formatDayLabel(day.date)}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center justify-center gap-4 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-primary/70" /> Criado
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-success" /> Convertido
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-destructive" /> Perdido
              </span>
            </div>
          </div>
        )}

        {/* Revenue-loop round — "breakdown por ação": which channel
            (call/message/meeting) actually generated the closed revenue
            above, not just which one's recommended most often. Omitted
            entirely (not just shown as all-zero bars) until at least one
            conversion has real attributed revenue behind it. */}
        {hasActionBreakdown && (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Receita por ação
            </p>
            <div className="space-y-1.5">
              {actionBreakdownEntries.map((entry) => (
                <div key={entry.action} className="flex items-center gap-2 text-xs">
                  <span className="w-20 shrink-0 text-muted-foreground">
                    {ACTION_BREAKDOWN_LABELS[entry.action]}
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${(entry.value / maxActionValue) * 100}%` }}
                    />
                  </div>
                  <span className="w-20 shrink-0 text-right font-medium text-foreground">
                    R$ {formatBRL(entry.value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
