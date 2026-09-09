import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RevenueSummary, RevenueTrendDay } from "@/lib/api/revenue";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

function formatDayLabel(isoDate: string): string {
  const [, month, day] = isoDate.split("-");
  return `${day}/${month}`;
}

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
      </CardContent>
    </Card>
  );
}
