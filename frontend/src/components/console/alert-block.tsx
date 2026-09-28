import { AlertTriangle, Info } from "lucide-react";
import { memo } from "react";

import { cn } from "@/lib/utils/cn";

const VARIANT_STYLES = {
  critical: {
    container: "border-2 border-destructive/60 bg-destructive/10 shadow-sm",
    icon: "text-destructive",
    text: "text-destructive",
    Icon: AlertTriangle,
  },
  warning: {
    container: "border-warning/40 bg-warning/10",
    icon: "text-warning",
    text: "text-warning",
    Icon: Info,
  },
} as const;

/** Shown for execution_blocked ("critical") and consistency_warning
 * ("warning") — the console never silently masks either signal. */
export const AlertBlock = memo(function AlertBlock({
  message,
  variant = "critical",
}: {
  message: string;
  variant?: keyof typeof VARIANT_STYLES;
}) {
  const { container, icon, text, Icon } = VARIANT_STYLES[variant];
  return (
    <div
      role="alert"
      className={cn("flex items-center gap-2 rounded-lg border px-6 py-4", container)}
    >
      <Icon className={cn("h-6 w-6 shrink-0", icon)} />
      <p className={cn("text-base font-semibold", text)}>{message}</p>
    </div>
  );
});
