"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRightLeft, Sparkles, Zap, type LucideIcon } from "lucide-react";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils/cn";
import {
  completeLeadTask,
  enrichLead,
  generateLeadMessage,
  getLeadTimeline,
  recordLeadResponse,
  updateLeadDetails,
  updateLeadOwner,
  type Lead,
  type LeadResponseOutcome,
  type LeadStatus,
} from "@/lib/api/leads";
import { getOrgMembers } from "@/lib/api/organizations";
import { formatDate, formatRelativeTime } from "@/lib/utils/format";

/** <input type="date"> needs a "YYYY-MM-DD" value; the wire format is a
 * full ISO datetime. Empty string clears the field (and, on save, the due
 * date) rather than showing "Invalid Date". */
function toDateInputValue(value: string | null): string {
  if (!value) return "";
  return value.slice(0, 10);
}

const STATUS_LABEL: Record<LeadStatus, string> = {
  new: "New",
  contacted: "Contacted",
  converted: "Converted",
  lost: "Lost",
};

const STATUS_BADGE: Record<LeadStatus, "secondary" | "warning" | "success" | "destructive"> = {
  new: "secondary",
  contacted: "warning",
  converted: "success",
  lost: "destructive",
};

// "lost" deliberately excluded — moving a lead there always goes through
// LeadLossAction below (reason required), never this one-click "Move to"
// row.
const STATUS_OPTIONS: LeadStatus[] = ["new", "contacted", "converted"];

/** LeadLossAction's fixed set of reasons — matches PATCH /leads/{id}/status's
 * `reason` docs (backend/app/schemas/leads/lead.py) exactly, though the
 * field itself stays a plain string there so a future reason doesn't need a
 * schema change. */
const LOSS_REASONS = ["Preço alto", "Sem resposta", "Sem interesse", "Timing"] as const;

/** "Mark as lost" — deliberately its own dedicated block, not a
 * STATUS_OPTIONS entry: losing a lead always requires picking a reason
 * first (feedback-loop round's loss-intelligence signal depends on it),
 * so it can't be a casual one-click action the way New/Contacted/Converted
 * are. */
function LeadLossAction({
  status,
  onConfirm,
}: {
  status: LeadStatus;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState<string>(LOSS_REASONS[0]);

  if (status === "lost") return null;

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
      <Select
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        className="w-auto"
      >
        {LOSS_REASONS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </Select>
      <Button size="sm" variant="destructive" onClick={() => onConfirm(reason)}>
        Marcar como perdido
      </Button>
    </div>
  );
}

type ModalTab = "details" | "activity";

const CATEGORY_ICON: Record<"status_change" | "automation" | "activity", LucideIcon> = {
  status_change: ArrowRightLeft,
  automation: Zap,
  activity: Sparkles,
};

function LeadActivityTimeline({ leadId }: { leadId: string }) {
  const { data: entries, isLoading } = useQuery({
    queryKey: ["lead-timeline", leadId],
    queryFn: () => getLeadTimeline(leadId),
  });

  if (isLoading) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Loading activity…</p>;
  }

  if (!entries || entries.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">No activity yet.</p>;
  }

  return (
    <ol className="mt-4 space-y-4">
      {entries.map((entry, index) => {
        const Icon = CATEGORY_ICON[entry.category];
        return (
          <li key={entry.id} className="relative flex gap-3 pl-1">
            <div className="flex flex-col items-center">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                <Icon className="h-3.5 w-3.5" />
              </span>
              {index < entries.length - 1 && <span className="w-px flex-1 bg-border" />}
            </div>
            <div className="pb-4">
              <p className="text-sm text-foreground">{entry.message}</p>
              <p className="text-xs text-muted-foreground">{formatRelativeTime(entry.createdAt)}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function LeadNotesAndTasks({
  lead,
  onTaskCompleted,
  completeTaskOverride,
  onLeadUpdate,
}: {
  lead: Lead;
  onTaskCompleted?: (nextLead?: Lead | null) => void;
  /** Command Center's continuous flow supplies this to complete the task
   * AND fetch the next actionable lead in one request (POST
   * /workday/complete-and-next) instead of this component's default plain
   * completeLeadTask() call. Omitted everywhere else — behavior for the
   * Leads page's modal and the existing "Começar meu dia" flow is
   * unchanged. */
  completeTaskOverride?: (leadId: string) => Promise<{ lead: Lead; nextLead?: Lead | null }>;
  /** Keeps the currently-open modal's own display in sync with this
   * mutation's result — the `lead` prop is a snapshot the parent page
   * only refreshes by closing/reopening the modal, so without this the
   * Score/notes/next-action shown here would lag one action behind what
   * just happened. See LeadDetailsModal's own liveLead state. */
  onLeadUpdate?: (lead: Lead) => void;
}) {
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState(lead.notes ?? "");
  const [nextAction, setNextAction] = useState(lead.nextAction ?? "");
  const [dueDate, setDueDate] = useState(toDateInputValue(lead.nextActionDueAt));

  // The lead prop is a snapshot taken when the modal opened, not a live
  // subscription — resync local state whenever a *different* lead is shown
  // (switching leads doesn't remount this component).
  useEffect(() => {
    setNotes(lead.notes ?? "");
    setNextAction(lead.nextAction ?? "");
    setDueDate(toDateInputValue(lead.nextActionDueAt));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id]);

  const saveDetails = useMutation({
    mutationFn: (patch: { notes?: string; nextAction?: string; nextActionDueAt?: string | null }) =>
      updateLeadDetails(lead.id, patch),
    onSuccess: (updated) => {
      queryClient.setQueryData<Lead[]>(["leads"], (prev) =>
        (prev ?? []).map((item) => (item.id === updated.id ? updated : item))
      );
      queryClient.invalidateQueries({ queryKey: ["leads-attention"] });
      queryClient.invalidateQueries({ queryKey: ["leads-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["lead-timeline", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
      onLeadUpdate?.(updated);
    },
  });

  const completeTask = useMutation({
    mutationFn: (): Promise<{ lead: Lead; nextLead?: Lead | null }> =>
      completeTaskOverride
        ? completeTaskOverride(lead.id)
        : completeLeadTask(lead.id).then((result) => ({ lead: result.lead })),
    onSuccess: ({ lead: updated, nextLead }) => {
      setNextAction("");
      setDueDate("");
      queryClient.setQueryData<Lead[]>(["leads"], (prev) =>
        (prev ?? []).map((item) => (item.id === updated.id ? updated : item))
      );
      queryClient.invalidateQueries({ queryKey: ["leads-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      queryClient.invalidateQueries({ queryKey: ["lead-timeline", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
      queryClient.invalidateQueries({ queryKey: ["workday-summary"] });
      queryClient.invalidateQueries({ queryKey: ["workday-performance"] });
      queryClient.invalidateQueries({ queryKey: ["revenue-summary"] });
      onLeadUpdate?.(updated);
      onTaskCompleted?.(nextLead);
    },
  });

  return (
    <div className="mt-5 space-y-4">
      <div className="space-y-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Notes
        </p>
        <Textarea
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          onBlur={() => {
            if (notes !== (lead.notes ?? "")) saveDetails.mutate({ notes });
          }}
          placeholder="Add notes about this lead…"
          rows={3}
        />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Next Action
          </p>
          {lead.nextAction && (
            <button
              type="button"
              onClick={() => completeTask.mutate()}
              disabled={completeTask.isPending}
              className="text-xs font-medium text-primary hover:underline disabled:opacity-50"
            >
              Complete task
            </button>
          )}
        </div>
        <Input
          value={nextAction}
          onChange={(event) => setNextAction(event.target.value)}
          onBlur={() => {
            if (nextAction !== (lead.nextAction ?? "")) saveDetails.mutate({ nextAction });
          }}
          placeholder="e.g. Follow-up call"
        />
      </div>

      <div className="space-y-1.5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Due Date
        </p>
        <Input
          type="date"
          value={dueDate}
          onChange={(event) => {
            const value = event.target.value;
            setDueDate(value);
            saveDetails.mutate({
              nextActionDueAt: value ? new Date(value).toISOString() : null,
            });
          }}
        />
      </div>
    </div>
  );
}

function LeadIntelligence({
  lead,
  onLeadUpdate,
}: {
  lead: Lead;
  /** See LeadNotesAndTasks's own doc — same "keep the open modal's snapshot
   * current" purpose. */
  onLeadUpdate?: (lead: Lead) => void;
}) {
  const queryClient = useQueryClient();
  const [generatedMessage, setGeneratedMessage] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Same rationale as LeadNotesAndTasks — a generated message belongs to
  // whichever lead was showing when it was generated, not whatever lead
  // this component happens to be re-rendered with next.
  useEffect(() => {
    setGeneratedMessage(null);
    setCopied(false);
  }, [lead.id]);

  const enrich = useMutation({
    mutationFn: () => enrichLead(lead.id),
    onSuccess: (updated) => {
      queryClient.setQueryData<Lead[]>(["leads"], (prev) =>
        (prev ?? []).map((item) => (item.id === updated.id ? updated : item))
      );
      queryClient.invalidateQueries({ queryKey: ["lead-timeline", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
      onLeadUpdate?.(updated);
    },
  });

  const generateMessage = useMutation({
    mutationFn: () => generateLeadMessage(lead.id),
    onSuccess: (message) => {
      setGeneratedMessage(message);
      setCopied(false);
      queryClient.invalidateQueries({ queryKey: ["lead-timeline", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
    },
  });

  async function handleCopy() {
    if (!generatedMessage) return;
    try {
      await navigator.clipboard.writeText(generatedMessage);
      setCopied(true);
    } catch {
      // Clipboard API can be unavailable (permissions, non-HTTPS context) —
      // the text is still right there in the textarea to copy by hand.
    }
  }

  return (
    <div className="mt-5 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Lead Intelligence
        </p>
        <button
          type="button"
          onClick={() => enrich.mutate()}
          disabled={enrich.isPending}
          className="text-xs font-medium text-primary hover:underline disabled:opacity-50"
        >
          {enrich.isPending ? "Updating…" : "Atualizar dados"}
        </button>
      </div>

      {lead.enrichmentData ? (
        <dl className="space-y-1.5 rounded-md border border-border bg-muted/30 p-3 text-sm">
          {lead.companyName && (
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Company</dt>
              <dd className="text-foreground">{lead.companyName}</dd>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Sector</dt>
            <dd className="text-foreground">{lead.enrichmentData.industry}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Size</dt>
            <dd className="text-foreground">{lead.enrichmentData.companySize} employees</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Location</dt>
            <dd className="text-foreground">{lead.enrichmentData.city}</dd>
          </div>
          <p className="pt-1 text-xs text-muted-foreground">{lead.enrichmentData.description}</p>
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">
          No profile yet — click &quot;Atualizar dados&quot; to build one.
        </p>
      )}

      <div className="space-y-1.5">
        <Button
          size="sm"
          variant="outline"
          onClick={() => generateMessage.mutate()}
          disabled={generateMessage.isPending}
        >
          {generateMessage.isPending ? "Gerando…" : "Gerar Mensagem"}
        </Button>

        {generatedMessage && (
          <div className="space-y-1.5">
            <Textarea value={generatedMessage} readOnly rows={6} className="text-xs" />
            <Button size="sm" variant="outline" onClick={handleCopy}>
              {copied ? "Copiado!" : "Copiar"}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function LeadOwnerAssignment({
  lead,
  onLeadUpdate,
}: {
  lead: Lead;
  /** See LeadNotesAndTasks's own doc — same "keep the open modal's snapshot
   * current" purpose. */
  onLeadUpdate?: (lead: Lead) => void;
}) {
  const queryClient = useQueryClient();
  const { data: members } = useQuery({
    queryKey: ["org-members"],
    queryFn: getOrgMembers,
  });

  const assignOwner = useMutation({
    mutationFn: (ownerEmail: string | null) => updateLeadOwner(lead.id, ownerEmail),
    onSuccess: (updated) => {
      queryClient.setQueryData<Lead[]>(["leads"], (prev) =>
        (prev ?? []).map((item) => (item.id === updated.id ? updated : item))
      );
      queryClient.invalidateQueries({ queryKey: ["lead-timeline", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
      onLeadUpdate?.(updated);
    },
  });

  return (
    <div className="mt-5 space-y-1.5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Owner</p>
      <div className="flex items-center gap-2">
        {lead.ownerEmail && <Avatar label={lead.ownerEmail} className="h-8 w-8 text-xs" />}
        <Select
          className="flex-1"
          value={lead.ownerEmail ?? ""}
          disabled={assignOwner.isPending}
          onChange={(event) => assignOwner.mutate(event.target.value || null)}
        >
          <option value="">Unassigned</option>
          {members?.map((member) => (
            <option key={member.email} value={member.email}>
              {member.email}
            </option>
          ))}
        </Select>
      </div>
    </div>
  );
}

/** Feedback-loop-of-outcomes round's visual language for leadResponseState —
 * duplicated from lead-card.tsx's own RESPONSE_BADGE_STYLE rather than
 * shared/exported, same "small lookup map, copy it" precedent formatBRL
 * already sets across this codebase's dashboard components. "no_response"
 * has no entry on purpose: LeadResponseAction below never renders a badge
 * for it, only the three buttons. */
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

/** "Resposta do lead" — feedback-loop-of-outcomes round's UI trigger for
 * POST /leads/{id}/record-response. Rendered only when there's something
 * useful to do here: nothing recorded yet (no_response), or the system is
 * specifically recommending a message right now (nextBestActionType ===
 * "send_message") — not on every lead, every time, which would just be
 * noise. Once a response IS recorded the buttons are gone for good (this
 * round's own edge case): recording an outcome is a one-time teaching
 * moment per lead, not a toggle you can flip back and forth. */
function LeadResponseAction({
  lead,
  onLeadUpdate,
}: {
  lead: Lead;
  onLeadUpdate?: (lead: Lead) => void;
}) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const recordResponse = useMutation({
    mutationFn: (responseOutcome: LeadResponseOutcome) =>
      recordLeadResponse(lead.id, responseOutcome),
    onSuccess: (updated) => {
      queryClient.setQueryData<Lead[]>(["leads"], (prev) =>
        (prev ?? []).map((item) => (item.id === updated.id ? updated : item))
      );
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      queryClient.invalidateQueries({ queryKey: ["workday-summary"] });
      queryClient.invalidateQueries({ queryKey: ["workday-performance"] });
      queryClient.invalidateQueries({ queryKey: ["lead-timeline", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
      onLeadUpdate?.(updated);
      showToast("Resposta registrada");
    },
  });

  if (lead.leadResponseState === "no_response" && lead.nextBestActionType !== "send_message") {
    return null;
  }

  return (
    <div className="mt-5 space-y-1.5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Resposta do lead
      </p>
      {lead.leadResponseState === "no_response" ? (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={recordResponse.isPending}
            onClick={() => recordResponse.mutate("responded")}
          >
            Respondeu
          </Button>
          <Button
            size="sm"
            variant="default"
            disabled={recordResponse.isPending}
            onClick={() => recordResponse.mutate("interested")}
          >
            Interessado
          </Button>
          <Button
            size="sm"
            variant="destructive"
            disabled={recordResponse.isPending}
            onClick={() => recordResponse.mutate("not_interested")}
          >
            Sem interesse
          </Button>
        </div>
      ) : (
        <Badge
          variant="outline"
          className={RESPONSE_BADGE_STYLE[lead.leadResponseState].className}
        >
          {RESPONSE_BADGE_STYLE[lead.leadResponseState].label}
        </Badge>
      )}
    </div>
  );
}

export function LeadDetailsModal({
  lead: leadProp,
  onClose,
  onMove,
  onTaskCompleted,
  workdayStats,
  completeTaskOverride,
}: {
  lead: Lead | null;
  onClose: () => void;
  onMove: (status: LeadStatus, reason?: string) => void;
  /** Set when this modal is being driven by workday mode ("Começar meu
   * dia") or the Command Center — completing this lead's task calls back
   * into the dashboard to fetch and open the next one, instead of just
   * refreshing in place. The Command Center's nextLead (when
   * completeTaskOverride is also set) arrives here instead of the caller
   * needing a separate round-trip. */
  onTaskCompleted?: (nextLead?: Lead | null) => void;
  workdayStats?: { tasksCompletedToday: number; streakDays: number };
  /** Command Center only — see LeadNotesAndTasks's own prop doc. */
  completeTaskOverride?: (leadId: string) => Promise<{ lead: Lead; nextLead?: Lead | null }>;
}) {
  const [tab, setTab] = useState<ModalTab>("details");
  // The `lead` prop is a snapshot the parent page only refreshes by
  // closing/reopening the modal (its own detailsLead state isn't wired to
  // the "leads" query cache) — so this modal keeps its own live copy,
  // updated by every child mutation's onLeadUpdate, and resynced whenever
  // a *different* lead opens (or the modal closes).
  const [lead, setLead] = useState<Lead | null>(leadProp);

  useEffect(() => {
    setLead(leadProp);
  }, [leadProp]);

  if (!lead) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="lead-details-title"
        className="max-h-[85vh] w-full max-w-sm overflow-y-auto rounded-lg border border-border bg-card p-6 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <h2 id="lead-details-title" className="text-base font-semibold text-foreground">
            {lead.name}
          </h2>
          <Badge variant={STATUS_BADGE[lead.status]}>{STATUS_LABEL[lead.status]}</Badge>
        </div>

        {workdayStats && (
          <p className="mt-1 text-xs text-muted-foreground">
            {workdayStats.tasksCompletedToday} leads resolved today
            {workdayStats.streakDays > 1 ? ` · ${workdayStats.streakDays}-day streak` : ""}
          </p>
        )}

        <div className="mt-4 flex gap-4 border-b border-border text-sm">
          {(["details", "activity"] as ModalTab[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setTab(value)}
              className={cn(
                "-mb-px border-b-2 px-1 pb-2 font-medium capitalize transition-colors",
                tab === value
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {value}
            </button>
          ))}
        </div>

        {tab === "details" ? (
          <>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="text-foreground">{lead.email}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Phone</dt>
                <dd className="text-foreground">{lead.phone}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Score</dt>
                <dd className="text-foreground">{lead.score}/100</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Created</dt>
                <dd className="text-foreground">{formatDate(lead.createdAt)}</dd>
              </div>
            </dl>

            {lead.priorityReason && (
              <p className="mt-3 rounded-md border border-primary/30 bg-primary/5 p-2.5 text-xs text-foreground">
                <span className="font-medium text-primary">Por que este lead? </span>
                {lead.priorityReason}
              </p>
            )}

            <LeadOwnerAssignment lead={lead} onLeadUpdate={setLead} />

            <div className="mt-5 space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Move to
              </p>
              <div className="flex gap-2">
                {STATUS_OPTIONS.map((status) => (
                  <Button
                    key={status}
                    variant={status === lead.status ? "default" : "outline"}
                    size="sm"
                    disabled={status === lead.status}
                    onClick={() => onMove(status)}
                  >
                    {STATUS_LABEL[status]}
                  </Button>
                ))}
              </div>
              <LeadLossAction status={lead.status} onConfirm={(reason) => onMove("lost", reason)} />
            </div>

            <LeadNotesAndTasks
              lead={lead}
              onTaskCompleted={onTaskCompleted}
              completeTaskOverride={completeTaskOverride}
              onLeadUpdate={setLead}
            />

            <LeadIntelligence lead={lead} onLeadUpdate={setLead} />

            <LeadResponseAction lead={lead} onLeadUpdate={setLead} />
          </>
        ) : (
          <LeadActivityTimeline leadId={lead.id} />
        )}

        <div className="mt-5 flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
