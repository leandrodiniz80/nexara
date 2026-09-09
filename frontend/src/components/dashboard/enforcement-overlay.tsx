"use client";

import { Button } from "@/components/ui/button";
import type { EnforcementState } from "@/lib/api/workday";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

// Autonomous-sales-OS round — requiredAction's own button label. Falls
// back to a generic "Executar ação" for any value outside this map, same
// defensive fallback the backend's own required_action already guarantees
// never actually happens (see EnforcementStateResponse's own docstring),
// kept here only so a future backend change can't silently render a blank
// button.
const REQUIRED_ACTION_LABEL: Record<string, string> = {
  send_message: "Enviar mensagem agora",
  call_now: "Confirmar ligação",
  schedule_meeting: "Agendar reunião",
};

/** Autonomous-sales-OS round's hard-enforcement gate — a fullscreen,
 * undismissable overlay (fixed inset-0, high z-index, opaque backdrop)
 * rendered whenever GET /workday/enforcement-state reports blocked=true.
 * There is no close button by design: the only way out is executing
 * requiredAction (onExecute) — "Abrir lead" opens the full details modal
 * for the rare case the automatic execution can't apply (e.g. no
 * suggested_message yet), it does not dismiss the block on its own. */
export function EnforcementOverlay({
  state,
  onExecute,
  onOpenLead,
  isExecuting,
}: {
  state: EnforcementState;
  onExecute: () => void;
  onOpenLead: () => void;
  isExecuting: boolean;
}) {
  if (!state.blocked || !state.leadId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/95 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-destructive/40 bg-card p-6 shadow-2xl">
        <p className="text-xs font-semibold uppercase tracking-wide text-destructive">
          🚨 Ação obrigatória
        </p>
        <p className="mt-1 text-sm font-medium text-foreground">{state.reason}</p>

        <div className="mt-4 space-y-1 rounded-md border border-border bg-muted/30 p-3">
          <p className="text-base font-semibold text-foreground">{state.name}</p>
          {state.companyName && (
            <p className="text-sm text-muted-foreground">{state.companyName}</p>
          )}
          {state.phone && <p className="text-sm text-muted-foreground">{state.phone}</p>}
          {state.expectedValue !== null && state.expectedValue > 0 && (
            <p className="text-sm font-medium text-success">
              💰 R$ {formatBRL(state.expectedValue)}
            </p>
          )}
          {state.nextBestAction && (
            <p className="mt-1 text-sm font-medium text-primary">👉 {state.nextBestAction}</p>
          )}
        </div>

        <div className="mt-5 flex flex-col gap-2">
          <Button size="lg" variant="destructive" onClick={onExecute} disabled={isExecuting}>
            {isExecuting
              ? "Executando…"
              : (state.requiredAction && REQUIRED_ACTION_LABEL[state.requiredAction]) ??
                "Executar ação"}
          </Button>
          <Button size="sm" variant="outline" onClick={onOpenLead} disabled={isExecuting}>
            Abrir lead
          </Button>
        </div>
      </div>
    </div>
  );
}
