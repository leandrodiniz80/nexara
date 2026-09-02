"use client";

import { LayoutDashboard, Megaphone, Settings, Users, Zap, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { NexaraLogo } from "@/components/nexara-logo";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/utils/cn";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Omitted = visible to every role. No item sets this yet — the filter
   * below exists so a future role-gated item is a one-line addition instead
   * of a new mechanism. */
  roles?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Leads", href: "/leads", icon: Users },
  { label: "Campanhas", href: "/campaigns", icon: Megaphone },
  { label: "Automações", href: "/automations", icon: Zap },
  { label: "Configurações", href: "/settings", icon: Settings },
];

export function DashboardSidebar() {
  const pathname = usePathname();
  const { user } = useAuth();

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (user?.role != null && item.roles.includes(user.role))
  );

  return (
    <aside className="hidden w-64 shrink-0 border-r border-border bg-card/40 md:flex md:flex-col">
      <div className="flex h-16 items-center border-b border-border px-6">
        <NexaraLogo />
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {visibleItems.map((item) => {
          // Prefix match (not just equality) so a future nested route like
          // /dashboard/reports still highlights the parent "Dashboard" item.
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md border-l-2 px-3 py-2 text-sm font-medium transition-all",
                isActive
                  ? "border-primary bg-primary/10 text-primary hover:bg-primary/15"
                  : "border-transparent text-muted-foreground hover:scale-[1.01] hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
