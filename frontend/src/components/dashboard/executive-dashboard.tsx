"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { RevenueForecast } from "@/lib/api/revenue";
import type { WorkdayPerformance, WorkdayTarget } from "@/lib/api/workday";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

/** Autonomous-sales-OS round's "Executive Dashboard Mode" — the four
 * headline financial numbers, large-typography and color-coded, meant to
 * read at a glance before anything else on the page. Renders nothing
 * until at least one of its three sources has loaded (all optional —
 * this sits above the rest of the dashboard, which shouldn't wait on it). */
export function ExecutiveDashboard({
  forecast,
  target,
  performance,
}: {
  forecast?: RevenueForecast;
  target?: WorkdayTarget;
  performance?: WorkdayPerformance;
}) {
  if (!forecast && !target && !performance) return null;

  const gap = target?.gap ?? 0;
  // Behind target reads as a positive gap (target - current); ahead or on
  // pace is <= 0 — same sign convention the backend's own gap field uses.
  const isAheadOfTarget = gap <= 0;
  const criticalDeals = performance?.criticalDeals ?? 0;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Card className="border-success/30 bg-success/5">
        <CardContent className="p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Receita esperada hoje
          </p>
          <p className="mt-1 text-3xl font-bold text-success">
            R$ {formatBRL(forecast?.todayExpected ?? 0)}
          </p>
        </CardContent>
      </Card>

      <Card
        className={
          isAheadOfTarget ? "border-success/30 bg-success/5" : "border-destructive/30 bg-destructive/5"
        }
      >
        <CardContent className="p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Gap para meta
          </p>
          <p
            className={`mt-1 text-3xl font-bold ${
              isAheadOfTarget ? "text-success" : "text-destructive"
            }`}
          >
            {isAheadOfTarget ? "+" : "-"}R$ {formatBRL(Math.abs(gap))}
          </p>
        </CardContent>
      </Card>

      <Card className="border-primary/30 bg-primary/5">
        <CardContent className="p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Forecast semanal
          </p>
          <p className="mt-1 text-3xl font-bold text-primary">
            R$ {formatBRL(forecast?.weekExpected ?? 0)}
          </p>
        </CardContent>
      </Card>

      <Card
        className={
          criticalDeals > 0 ? "border-destructive/30 bg-destructive/5" : "border-success/30 bg-success/5"
        }
      >
        <CardContent className="p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Deals críticos
          </p>
          <p
            className={`mt-1 text-3xl font-bold ${
              criticalDeals > 0 ? "text-destructive" : "text-success"
            }`}
          >
            {criticalDeals}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
