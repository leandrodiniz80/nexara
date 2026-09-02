import { MoreVertical } from "lucide-react";
import type { MouseEvent } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { DropdownMenu, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import type { Lead, LeadStatus } from "@/lib/api/leads";
import { cn } from "@/lib/utils/cn";

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

/** Native browser tooltip (no tooltip component in this UI kit yet, and one
 * factor list on hover doesn't warrant building one) — one line per factor,
 * signed impact so positive/negative reads at a glance. */
function scoreTitle(breakdown: Lead["scoreBreakdown"]): string {
  if (breakdown.length === 0) return "No score adjustments";
  return breakdown
    .map((item) => `${item.reason} (${item.impact > 0 ? "+" : ""}${item.impact})`)
    .join("\n");
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
        <Badge variant={getScoreVariant(lead.score)} title={scoreTitle(lead.scoreBreakdown)}>
          Score {lead.score}
        </Badge>
        {lead.nextAction && <Badge variant="outline">{lead.nextAction}</Badge>}
      </div>
    </div>
  );
}
