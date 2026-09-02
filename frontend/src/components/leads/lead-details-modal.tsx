"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { getLeadTimeline, type Lead, type LeadStatus } from "@/lib/api/leads";
import { formatDate, formatRelativeTime } from "@/lib/utils/format";

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
              {entry.from ? (
                <>
                  Status changed from <span className="font-medium">{entry.from}</span> to{" "}
                  <span className="font-medium">{entry.to}</span>
                </>
              ) : (
                <>
                  Status set to <span className="font-medium">{entry.to}</span>
                </>
              )}
            </p>
            <p className="text-xs text-muted-foreground">{formatRelativeTime(entry.createdAt)}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function LeadDetailsModal({
  lead,
  onClose,
  onMove,
}: {
  lead: Lead | null;
  onClose: () => void;
  onMove: (status: LeadStatus) => void;
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
        className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <h2 id="lead-details-title" className="text-base font-semibold text-foreground">
            {lead.name}
          </h2>
          <Badge variant={STATUS_BADGE[lead.status]}>{STATUS_LABEL[lead.status]}</Badge>
        </div>

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
