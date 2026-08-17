import { cn } from "@/lib/utils/cn";

/** Simple wordmark — a small gradient mark plus the Nexara name, no imagery. */
export function NexaraLogo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="h-6 w-6 rounded-md bg-nexara-gradient" aria-hidden="true" />
      <span className="text-lg font-semibold tracking-tight text-foreground">Nexara</span>
    </div>
  );
}
