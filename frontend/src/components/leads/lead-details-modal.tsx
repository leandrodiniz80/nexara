"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Lead, LeadStatus } from "@/lib/api/leads";
import { formatDate } from "@/lib/utils/format";

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

export function LeadDetailsModal({
  lead,
  onClose,
  onMove,
}: {
  lead: Lead | null;
  onClose: () => void;
  onMove: (status: LeadStatus) => void;
}) {
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

        <div className="mt-5 flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
