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

// Revenue-loop round — topRevenueAction's own plain-noun values ("call"/
// "message"/"meeting", same vocabulary RevenuePanel's revenueByAction keys
// use) translated for display; topRevenueIndustry/topRevenueCompanySize
// are shown as the backend's own raw enrichment_data strings, same
// no-translation convention the Learning Panel's bestIndustry already
// follows.
const ACTION_LABELS_PT: Record<string, string> = {
  call: "Ligações",
  message: "Mensagens",
  meeting: "Reuniões",
};

// Adaptive Intelligence round (Task 8) — turns one adaptiveWeights key
// (GET /intelligence/adaptive-weights, e.g. "industry:healthcare" or
// "action:call_now") into the friendly segment/action label the "🤖
// Sistema sugere focar em" line shows.
const ADAPTIVE_ACTION_LABELS_PT: Record<string, string> = {
  call_now: "ligações",
  send_message: "mensagens",
  schedule_meeting: "reuniões",
};

function formatAdaptiveWeightKey(key: string): string {
  if (key.startsWith("industry:")) return `setor ${key.slice("industry:".length)}`;
  if (key.startsWith("company_size:")) return `empresas de porte ${key.slice("company_size:".length)}`;
  if (key.startsWith("action:")) {
    const action = key.slice("action:".length);
    return ADAPTIVE_ACTION_LABELS_PT[action] ?? action;
  }
  if (key === "fast_response") return "respostas rápidas";
  if (key === "high_risk") return "negociações de risco";
  return key;
}

/** Adaptive Intelligence round (Task 8) — the single highest-weighted
 * signal (GET /intelligence/adaptive-weights), only when it's actually a
 * positive lift (> 1.0 — a weight at or below 1.0 has nothing worth
 * suggesting). null when there's no real weight data yet, same "omit,
 * don't show a misleading default" convention every other conditional
 * line in this card already follows. */
function topAdaptiveWeightLabel(adaptiveWeights: Record<string, number> | undefined): string | null {
  if (!adaptiveWeights) return null;
  const entries = Object.entries(adaptiveWeights).filter(([, weight]) => weight > 1.0);
  if (entries.length === 0) return null;
  const [topKey] = entries.reduce((best, entry) => (entry[1] > best[1] ? entry : best));
  return formatAdaptiveWeightKey(topKey);
}

export function CommandCenter({
  summary,
  performance,
  tasksCompletedToday,
  onStart,
  isStarting,
  onOpenMandatoryLead,
  execInsight,
  adaptiveWeights,
  hasRecentReassignments,
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
  /** Execution-engine round — "Próxima ação obrigatória"'s own button:
   * opens summary.nextMandatoryLeadId's lead modal directly. Optional/
   * omittable (no button rendered) when the caller hasn't resolved that id
   * against a full Lead yet. */
  onOpenMandatoryLead?: (leadId: string) => void;
  /** Adaptive Intelligence round (Task 8) — GET /intelligence/exec-insight's
   * own ready-to-render sentence, backing "📈 Receita potencial não
   * capturada." Optional/omittable while that endpoint hasn't loaded yet. */
  execInsight?: string;
  /** GET /intelligence/adaptive-weights, backing "🤖 Sistema sugere focar
   * em: [segment/action]" (topAdaptiveWeightLabel() picks the highest one
   * worth suggesting). */
  adaptiveWeights?: Record<string, number>;
  /** True when GET /leads/activity shows a recent "lead_reassigned" entry
   * — the Lead Reassignment Engine (Task 4) ran and actually moved
   * something. Backs "⚠️ Leads redistribuídos automaticamente." */
  hasRecentReassignments?: boolean;
}) {
  const suggestedFocusLabel = topAdaptiveWeightLabel(adaptiveWeights);
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

        {/* Execution-engine round — the queue's own mandatory pick
            (get_next_mandatory_lead(), backend): a critical-risk lead or one
            with a pending response over 60min, always forced to the front
            regardless of anything else in the queue. */}
        {summary.nextMandatoryLeadId && onOpenMandatoryLead && (
          <div className="flex items-center justify-between gap-3 rounded-md border border-destructive/40 bg-destructive/10 p-3">
            <p className="text-sm font-semibold text-destructive">
              🚨 Próxima ação obrigatória
            </p>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => onOpenMandatoryLead(summary.nextMandatoryLeadId!)}
            >
              Abrir agora
            </Button>
          </div>
        )}

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

        {/* Feedback-loop-of-outcomes round — omitted entirely (not just
            shown as 0%) until there's been at least one message sent in
            the last 30 days, so a brand-new org never sees a misleading
            "0% respondem" headline. */}
        {summary.responseRate > 0 && (
          <p className="text-sm font-semibold text-primary">
            {summary.responseRate.toFixed(0)}% das suas mensagens recebem resposta
          </p>
        )}

        {/* Revenue-loop round — "O que mais gera dinheiro hoje": each line
            omitted individually until that dimension has a real winner
            (at least one conversion with attributed revenue behind it),
            and the whole block omitted if none of the three do. */}
        {(summary.topRevenueAction || summary.topRevenueIndustry || summary.topRevenueCompanySize) && (
          <div className="rounded-md border border-success/30 bg-success/5 p-3 text-sm">
            <p className="font-semibold text-success">💡 O que mais gera dinheiro hoje:</p>
            <ul className="mt-1 space-y-0.5 text-foreground">
              {summary.topRevenueAction && (
                <li>
                  Ação: <span className="font-medium">{ACTION_LABELS_PT[summary.topRevenueAction] ?? summary.topRevenueAction}</span>
                </li>
              )}
              {summary.topRevenueIndustry && (
                <li>
                  Segmento: <span className="font-medium">{summary.topRevenueIndustry}</span>
                </li>
              )}
              {summary.topRevenueCompanySize && (
                <li>
                  Porte: <span className="font-medium">{summary.topRevenueCompanySize}</span>
                </li>
              )}
            </ul>
          </div>
        )}

        {/* Adaptive Intelligence round (Task 8) — the three new Command
            Center notices, each omitted until its own backend data says
            there's something real to show. */}
        {execInsight && (
          <p className="text-sm font-semibold text-success">📈 {execInsight}</p>
        )}
        {suggestedFocusLabel && (
          <p className="text-sm font-semibold text-primary">
            🤖 Sistema sugere focar em: {suggestedFocusLabel}
          </p>
        )}
        {hasRecentReassignments && (
          <p className="text-sm font-semibold text-warning">
            ⚠️ Leads redistribuídos automaticamente
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
          <div>
            <p className="text-lg font-semibold text-success">
              {summary.autoActionsExecutedToday}
            </p>
            <p className="text-xs text-muted-foreground">Ações automáticas hoje</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-warning">
              {summary.pendingResponsesCount}
            </p>
            <p className="text-xs text-muted-foreground">Leads aguardando resposta</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">
              R$ {formatBRL(summary.pipelineExpectedValue)}
            </p>
            <p className="text-xs text-muted-foreground">Pipeline esperado hoje</p>
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
