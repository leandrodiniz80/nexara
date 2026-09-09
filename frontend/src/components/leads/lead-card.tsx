"use client";

import { MoreVertical } from "lucide-react";
import type { MouseEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { useToast } from "@/components/ui/toast";
import { executeLeadAction, type Lead, type LeadStatus } from "@/lib/api/leads";
import { cn } from "@/lib/utils/cn";
import { copyToClipboard } from "@/lib/utils/clipboard";

const STATUS_OPTIONS: { label: string; value: LeadStatus }[] = [
  { label: "Move to New", value: "new" },
  { label: "Move to Contacted", value: "contacted" },
  { label: "Move to Converted", value: "converted" },
];

function getScoreVariant(score: number): "destructive" | "warning" | "success" {
  if (score >= 71) return "success";
  if (score >= 31) return "warning";
  return "destructive";
}

/** win_probability color bands (revenue-intelligence round) — >=70 green,
 * 40-69 yellow, <40 red. Deliberately its own thresholds, not reused from
 * getScoreVariant's 71/31 split: score and win_probability are different
 * numbers with different meanings, even though the bands look similar. */
function getWinProbabilityVariant(probability: number): "destructive" | "warning" | "success" {
  if (probability >= 70) return "success";
  if (probability >= 40) return "warning";
  return "destructive";
}

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

/** AI Deal Coach round — dealRiskLevel's visual treatment. "low" and null
 * are deliberately absent (no entry, no badge rendered): a quiet lead
 * competing for attention against real risk badges would defeat the point.
 * critical/high/medium all use Badge's "outline" base (border-border,
 * text-foreground) with these classes layered on top via cn()'s
 * twMerge — last one wins for the same-category utility, so this fully
 * overrides the outline look rather than fighting it. high gets its own
 * orange rather than reusing warning's yellow (already spoken for by
 * medium), since the prompt calls for three visually distinct tiers, not
 * two. */
const RISK_BADGE_STYLE: Record<"critical" | "high" | "medium", { className: string; label: string }> = {
  critical: {
    className: "border-transparent bg-destructive/15 text-destructive",
    label: "🔥 Risco crítico",
  },
  high: {
    className: "border-transparent bg-orange-500/15 text-orange-600 dark:text-orange-400",
    label: "Risco alto",
  },
  medium: {
    className: "border-transparent bg-warning/15 text-warning",
    label: "Risco médio",
  },
};

/** Feedback-loop-of-outcomes round — leadResponseState's visual treatment.
 * "no_response" is deliberately absent (no badge): it's the default,
 * nothing-happened-yet state for most leads, and badging every card with
 * it would be pure noise. "responded" gets its own blue rather than
 * reusing an existing variant — Badge has no built-in blue, so this
 * layers custom classes over "outline" the same way RISK_BADGE_STYLE's
 * "high" tier already does. */
const RESPONSE_BADGE_STYLE: Record<
  "responded" | "interested" | "not_interested",
  { className: string; label: string }
> = {
  responded: {
    className: "border-transparent bg-blue-500/15 text-blue-600 dark:text-blue-400",
    label: "💬 Respondeu",
  },
  interested: {
    className: "border-transparent bg-success/15 text-success",
    label: "✅ Interessado",
  },
  not_interested: {
    className: "border-transparent bg-destructive/15 text-destructive",
    label: "❌ Sem interesse",
  },
};

/** Sales-operating-system round — hasPendingResponse's visual treatment.
 * No badge under an hour (still well within a normal reply window, same
 * "quiet default gets nothing" precedent RISK_BADGE_STYLE/
 * RESPONSE_BADGE_STYLE above already follow) — yellow past that, red past
 * 24h, matching the same severity split compute_lead_score's own
 * pending-response penalty uses (scoring.py). */
function pendingResponseBadgeVariant(delayMinutes: number): "warning" | "destructive" | null {
  if (delayMinutes > 24 * 60) return "destructive";
  if (delayMinutes > 60) return "warning";
  return null;
}

function formatDelay(minutes: number): string {
  if (minutes < 60) return `${minutes}min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/** Native browser tooltip (no tooltip component in this UI kit yet, and one
 * factor list on hover doesn't warrant building one) — one line per factor,
 * signed impact so positive/negative reads at a glance. */
function scoreTitle(breakdown: Lead["scoreBreakdown"]): string {
  if (breakdown.length === 0) return "No score adjustments";
  return breakdown
    .map((item) => `${item.reason} (${item.impact > 0 ? "+" : ""}${item.impact})`)
    .join("\n");
}

/** Urgency badge for the next-action deadline. Overdue comes straight from
 * the backend's isOverdue (score_leads), so it always agrees with how
 * Today's Focus/Needs Attention are ranked; "due today" has no backend
 * field of its own, so it's the one thing derived from nextActionDueAt
 * here, against the browser's own clock. */
function nextActionVariant(lead: Lead): "destructive" | "warning" | "outline" {
  if (lead.isOverdue) return "destructive";
  if (lead.nextActionDueAt && new Date(lead.nextActionDueAt).toDateString() === new Date().toDateString()) {
    return "warning";
  }
  return "outline";
}

/** Stops the event from reaching the card's own drag/details handlers —
 * used so the "⋮" menu is its own hit target, not a drag handle. */
function stopCardGesture(event: MouseEvent) {
  event.stopPropagation();
}

export function LeadCard({
  lead,
  isDragging,
  isHighlighted,
  onDragStart,
  onMove,
  onOpenDetails,
}: {
  lead: Lead;
  isDragging: boolean;
  isHighlighted?: boolean;
  onDragStart: () => void;
  onMove: (status: LeadStatus) => void;
  onOpenDetails: () => void;
}) {
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  async function handleCopyMessage() {
    if (!lead.suggestedMessage) return;
    if (await copyToClipboard(lead.suggestedMessage)) {
      showToast("Mensagem copiada");
    }
  }

  /** AI Deal Coach's "Ligar agora" — a plain tel: handoff to the device's
   * own dialer, no in-app calling infrastructure to build. */
  function handleCallNow(event: MouseEvent) {
    stopCardGesture(event);
    if (lead.phone) window.location.href = `tel:${lead.phone}`;
  }

  // Execution-assistance round's "Enviar agora" — same self-contained
  // mutation + cache-patch pattern LeadIntelligence (lead-details-modal.tsx)
  // already uses for enrich/generate-message, since LeadCard (only ever
  // rendered from LeadsKanban) has no mutation plumbing of its own passed
  // down from its parent the way onMove does for status changes.
  const executeAction = useMutation({
    mutationFn: () => executeLeadAction(lead.id, "send_message"),
    onSuccess: (updated) => {
      queryClient.setQueryData<Lead[]>(["leads"], (prev) =>
        (prev ?? []).map((item) => (item.id === updated.id ? updated : item))
      );
      queryClient.invalidateQueries({ queryKey: ["leads-metrics"] });
      showToast("Mensagem enviada");
    },
  });

  function handleSendNow(event: MouseEvent) {
    stopCardGesture(event);
    executeAction.mutate();
  }

  const pendingBadgeVariant =
    lead.hasPendingResponse && lead.responseDelayMinutes !== null
      ? pendingResponseBadgeVariant(lead.responseDelayMinutes)
      : null;

  return (
    <div
      onMouseDown={onDragStart}
      onClick={onOpenDetails}
      // Inline duration only while highlighted: it outranks the utility
      // class's 200ms (normal hover/drag speed) so the fade-out specifically
      // is slow, without needing two different transition-duration values
      // fighting over the same "transition-all" property list.
      style={isHighlighted ? { transitionDuration: "2000ms" } : undefined}
      className={cn(
        "cursor-pointer rounded-md border border-border bg-card p-3 text-left shadow-sm transition-all duration-200 hover:bg-accent/40",
        isDragging && "scale-105 opacity-50",
        isHighlighted && "bg-primary/20"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          {lead.ownerEmail && (
            <Avatar label={lead.ownerEmail} className="mt-0.5 h-6 w-6 text-[10px]" />
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">{lead.name}</p>
            <p className="truncate text-xs text-muted-foreground">{lead.email}</p>
            <p className="text-xs text-muted-foreground/70">{lead.phone}</p>
            {lead.nextBestAction && (
              <p className="mt-1 truncate text-xs font-medium text-primary">
                👉 {lead.nextBestAction}
              </p>
            )}
          </div>
        </div>

        <div onMouseDown={stopCardGesture} onClick={stopCardGesture}>
          <DropdownMenu
            trigger={
              <span className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
                <MoreVertical className="h-4 w-4" />
              </span>
            }
          >
            {STATUS_OPTIONS.map((option) => (
              <DropdownMenuItem
                key={option.value}
                disabled={option.value === lead.status}
                onClick={() => onMove(option.value)}
              >
                {option.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenu>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {lead.dealRiskLevel && lead.dealRiskLevel !== "low" && (
          <Badge
            variant="outline"
            className={RISK_BADGE_STYLE[lead.dealRiskLevel].className}
            title={lead.dealRiskReason ?? undefined}
          >
            {RISK_BADGE_STYLE[lead.dealRiskLevel].label}
          </Badge>
        )}
        {lead.leadResponseState !== "no_response" && (
          <Badge
            variant="outline"
            className={RESPONSE_BADGE_STYLE[lead.leadResponseState].className}
            title={
              lead.responseTimeMinutes !== null
                ? `Respondeu em ${lead.responseTimeMinutes} minutos`
                : undefined
            }
          >
            {RESPONSE_BADGE_STYLE[lead.leadResponseState].label}
          </Badge>
        )}
        {pendingBadgeVariant && (
          <Badge
            variant={pendingBadgeVariant}
            title={`Mensagem enviada há ${formatDelay(lead.responseDelayMinutes ?? 0)}, sem resposta`}
          >
            ⏱ {formatDelay(lead.responseDelayMinutes ?? 0)}
          </Badge>
        )}
        <Badge variant={getScoreVariant(lead.score)} title={scoreTitle(lead.scoreBreakdown)}>
          Score {lead.score}
        </Badge>
        {lead.expectedValue > 0 && (
          <Badge variant="outline">💰 R$ {formatBRL(lead.expectedValue)}</Badge>
        )}
        {(lead.status === "new" || lead.status === "contacted") && (
          <Badge variant={getWinProbabilityVariant(lead.winProbability)}>
            🎯 {lead.winProbability}%
          </Badge>
        )}
        {lead.nextAction && (
          <Badge variant={nextActionVariant(lead)}>
            {lead.isOverdue && lead.daysOverdue
              ? `${lead.nextAction} (${lead.daysOverdue}d overdue)`
              : lead.nextAction}
          </Badge>
        )}
        {lead.nextBestActionType === "call_now" && lead.phone && (
          <Button size="sm" variant="destructive" onMouseDown={stopCardGesture} onClick={handleCallNow}>
            📞 Ligar agora
          </Button>
        )}
        {lead.autoActionAvailable ? (
          <Button
            size="sm"
            variant="default"
            disabled={executeAction.isPending}
            onMouseDown={stopCardGesture}
            onClick={handleSendNow}
          >
            {executeAction.isPending ? "Enviando…" : "✅ Enviar agora"}
          </Button>
        ) : (
          lead.suggestedMessage && (
            <Button
              size="sm"
              variant="outline"
              onMouseDown={stopCardGesture}
              onClick={(event) => {
                stopCardGesture(event);
                handleCopyMessage();
              }}
            >
              {lead.nextBestActionType === "send_message" ? "Enviar mensagem" : "Copiar mensagem"}
            </Button>
          )
        )}
      </div>
    </div>
  );
}
