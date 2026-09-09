"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { RevenueForecast } from "@/lib/api/revenue";
import type { WorkdayPerformance, WorkdaySummary, WorkdayTarget } from "@/lib/api/workday";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

/** Autonomous-sales-OS round's "Executive Dashboard Mode", extended by the
 * revenue-maximization round's own Task 6 — six headline financial
 * numbers, large-typography and color-coded, meant to read at a glance
 * before anything else on the page, plus (Task 3) a red "Modo Aceleração"
 * banner when the org is meaningfully behind its daily revenue target.
 * Renders nothing until at least one of its four sources has loaded (all
 * optional — this sits above the rest of the dashboard, which shouldn't
 * wait on it). */
export function ExecutiveDashboard({
  forecast,
  target,
  performance,
  summary,
}: {
  forecast?: RevenueForecast;
  target?: WorkdayTarget;
  performance?: WorkdayPerformance;
  summary?: WorkdaySummary;
}) {
  if (!forecast && !target && !performance && !summary) return null;

  const gap = target?.gap ?? 0;
  // Behind target reads as a positive gap (target - current); ahead or on
  // pace is <= 0 — same sign convention the backend's own gap field uses.
  const isAheadOfTarget = gap <= 0;
  const criticalDeals = performance?.criticalDeals ?? 0;
  const lostOpportunityToday = summary?.lostOpportunityToday ?? 0;

  return (
    <div className="space-y-3">
      {/* Revenue Acceleration Mode (Task 3) — the prompt's own literal
          banner copy, shown only while target.accelerationMode is true
          (gap > R$5,000). */}
      {target?.accelerationMode && (
        <div className="rounded-lg border border-destructive bg-destructive/15 p-3 text-center text-sm font-bold text-destructive">
          🚨 Modo Aceleração Ativado — Foco total em receita
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
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

        {/* Revenue-maximization round (Task 6) — sum of opportunityCost
            across leads not touched today; red whenever there's real
            upside being left on the table. */}
        <Card
          className={
            lostOpportunityToday > 0
              ? "border-destructive/30 bg-destructive/5"
              : "border-success/30 bg-success/5"
          }
        >
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Oportunidade perdida hoje
            </p>
            <p
              className={`mt-1 text-3xl font-bold ${
                lostOpportunityToday > 0 ? "text-destructive" : "text-success"
              }`}
            >
              R$ {formatBRL(lostOpportunityToday)}
            </p>
          </CardContent>
        </Card>

        {/* "Top padrão de receita" — compute_revenue_attribution()'s own
            top_combination (Task 4/6): the single "action | industry |
            company_size" pattern generating the most real revenue
            org-wide. Text-sized down from the other cards' own big
            number, since this is a string, not an amount. */}
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Top padrão de receita
            </p>
            <p className="mt-1 text-lg font-bold text-primary">
              {summary?.topRevenueCombination ?? "—"}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
