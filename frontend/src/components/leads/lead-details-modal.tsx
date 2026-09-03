"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils/cn";
import {
  completeLeadTask,
  enrichLead,
  generateLeadMessage,
  getLeadTimeline,
  updateLeadDetails,
  updateLeadOwner,
  type Lead,
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
};

const STATUS_BADGE: Record<LeadStatus, "secondary" | "warning" | "success"> = {
  new: "secondary",
  contacted: "warning",
  converted: "success",
};

const STATUS_OPTIONS: LeadStatus[] = ["new", "contacted", "converted"];

type ModalTab = "details" | "activity";

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
      {entries.map((entry, index) => (
        <li key={`${entry.createdAt}-${index}`} className="relative flex gap-3 pl-1">
          <div className="flex flex-col items-center">
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />
            {index < entries.length - 1 && <span className="w-px flex-1 bg-border" />}
          </div>
          <div className="pb-4">
            <p className="text-sm text-foreground">
              {entry.type === "status_changed" ? (
                entry.from ? (
                  <>
                    Status changed from <span className="font-medium">{entry.from}</span> to{" "}
                    <span className="font-medium">{entry.to}</span>
                  </>
                ) : (
                  <>
                    Status set to <span className="font-medium">{entry.to}</span>
                  </>
                )
              ) : (
                entry.message
              )}
            </p>
            <p className="text-xs text-muted-foreground">{formatRelativeTime(entry.createdAt)}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function LeadNotesAndTasks({
  lead,
  onTaskCompleted,
}: {
  lead: Lead;
  onTaskCompleted?: () => void;
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
    },
  });

  const completeTask = useMutation({
    mutationFn: () => completeLeadTask(lead.id),
    onSuccess: ({ lead: updated }) => {
      setNextAction("");
      setDueDate("");
      queryClient.setQueryData<Lead[]>(["leads"], (prev) =>
        (prev ?? []).map((item) => (item.id === updated.id ? updated : item))
      );
      queryClient.invalidateQueries({ queryKey: ["leads-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      queryClient.invalidateQueries({ queryKey: ["lead-timeline", lead.id] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
      onTaskCompleted?.();
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

function LeadIntelligence({ lead }: { lead: Lead }) {
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

function LeadOwnerAssignment({ lead }: { lead: Lead }) {
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

export function LeadDetailsModal({
  lead,
  onClose,
  onMove,
  onTaskCompleted,
  workdayStats,
}: {
  lead: Lead | null;
  onClose: () => void;
  onMove: (status: LeadStatus) => void;
  /** Set only when this modal is being driven by workday mode ("Começar meu
   * dia") — completing this lead's task calls back into the dashboard to
   * fetch and open the next one, instead of just refreshing in place. */
  onTaskCompleted?: () => void;
  workdayStats?: { tasksCompletedToday: number; streakDays: number };
}) {
  const [tab, setTab] = useState<ModalTab>("details");

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

            <LeadOwnerAssignment lead={lead} />

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
            </div>

            <LeadNotesAndTasks lead={lead} onTaskCompleted={onTaskCompleted} />

            <LeadIntelligence lead={lead} />
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
