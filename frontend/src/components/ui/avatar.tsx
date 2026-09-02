import { cn } from "@/lib/utils/cn";

/** No photo source anywhere in the platform yet (MeResponse has no name/avatar
 * field) — derives two initials from the user's email as a stable placeholder. */
function initialsFromLabel(label: string): string {
  const parts = label.split(/[@.\s]+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function Avatar({ label, className }: { label: string; className?: string }) {
  return (
    <div
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary",
        className
      )}
      aria-hidden="true"
    >
      {initialsFromLabel(label) || "?"}
    </div>
  );
}
