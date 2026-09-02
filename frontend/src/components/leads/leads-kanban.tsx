"use client";

import { useEffect, useState } from "react";

import { LeadCard } from "@/components/leads/lead-card";
import type { Lead, LeadStatus } from "@/lib/api/leads";
import { cn } from "@/lib/utils/cn";

const COLUMNS: { label: string; status: LeadStatus }[] = [
  { label: "New", status: "new" },
  { label: "Contacted", status: "contacted" },
  { label: "Converted", status: "converted" },
];

export function LeadsKanban({
  leads,
  onMove,
  onOpenDetails,
  highlightedLeadId,
}: {
  leads: Lead[];
  onMove: (leadId: string, status: LeadStatus) => void;
  onOpenDetails: (lead: Lead) => void;
  highlightedLeadId?: string | null;
}) {
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<LeadStatus | null>(null);

  // A window-level mouseup (not one scoped to a card/column) is what makes
  // this work without the HTML5 drag API: the pointer can be released
  // anywhere — over a card, a gap, whatever — and the drop still resolves
  // to whichever column was last entered.
  useEffect(() => {
    if (draggingId === null) return;

    function handleMouseUp() {
      if (draggingId && dragOverStatus) {
        onMove(draggingId, dragOverStatus);
      }
      setDraggingId(null);
      setDragOverStatus(null);
    }

    window.addEventListener("mouseup", handleMouseUp);
    return () => window.removeEventListener("mouseup", handleMouseUp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draggingId, dragOverStatus]);

  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {COLUMNS.map((column) => {
        const columnLeads = leads
          .filter((lead) => lead.status === column.status)
          .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
        const isDropTarget = draggingId !== null && dragOverStatus === column.status;

        return (
          <div
            key={column.status}
            onMouseEnter={() => {
              if (draggingId) setDragOverStatus(column.status);
            }}
            className={cn(
              "w-72 shrink-0 rounded-lg border p-3 transition-colors duration-200",
              isDropTarget ? "border-primary bg-primary/5" : "border-border bg-card/40"
            )}
          >
            <div className="mb-3 flex items-center justify-between px-1">
              <h3 className="text-sm font-semibold text-foreground">{column.label}</h3>
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                {columnLeads.length}
              </span>
            </div>
            <div className="space-y-2">
              {columnLeads.length === 0 ? (
                <p className="px-1 py-6 text-center text-xs text-muted-foreground">
                  No leads here.
                </p>
              ) : (
                columnLeads.map((lead) => (
                  <LeadCard
                    key={lead.id}
                    lead={lead}
                    isDragging={draggingId === lead.id}
                    isHighlighted={lead.id === highlightedLeadId}
                    onDragStart={() => setDraggingId(lead.id)}
                    onMove={(status) => onMove(lead.id, status)}
                    onOpenDetails={() => onOpenDetails(lead)}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
