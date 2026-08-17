import {
  AlertTriangle,
  CreditCard,
  HeartPulse,
  LayoutDashboard,
  Sparkles,
  Tag,
  Zap,
} from "lucide-react";

import { NexaraLogo } from "@/components/nexara-logo";
import { cn } from "@/lib/utils/cn";

const NAV_ITEMS = [
  { label: "Business Overview", icon: LayoutDashboard, active: true },
  { label: "Revenue Activation", icon: Sparkles, active: false },
  { label: "Sales Playbook", icon: Zap, active: false },
  { label: "Customer Health", icon: HeartPulse, active: false },
  { label: "Pricing Insights", icon: Tag, active: false },
  { label: "Auto Actions", icon: AlertTriangle, active: false },
  { label: "Billing / Stripe Portal", icon: CreditCard, active: false },
];

export function DashboardSidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-border bg-card/40 md:flex md:flex-col">
      <div className="flex h-16 items-center border-b border-border px-6">
        <NexaraLogo />
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {NAV_ITEMS.map((item) => (
          <div
            key={item.label}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
              item.active
                ? "bg-primary/10 text-primary"
                : "cursor-default text-muted-foreground/60"
            )}
          >
            <item.icon className="h-4 w-4" />
            <span>{item.label}</span>
            {!item.active && (
              <span className="ml-auto rounded-full border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground/60">
                Soon
              </span>
            )}
          </div>
        ))}
      </nav>
    </aside>
  );
}
