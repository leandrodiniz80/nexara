"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { NotificationBell } from "@/components/dashboard/notification-bell";
import { Avatar } from "@/components/ui/avatar";
import { DropdownMenu, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth/auth-context";

export function DashboardHeader() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  async function handleLogout() {
    setIsLoggingOut(true);
    try {
      await logout();
    } finally {
      router.replace("/login");
    }
  }

  return (
    <header className="flex h-16 items-center justify-end gap-3 border-b border-border px-6">
      {user && <NotificationBell />}
      {user && (
        <DropdownMenu
          trigger={
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-sm font-medium text-foreground">{user.email}</p>
                {user.role && (
                  <p className="text-xs capitalize text-muted-foreground">{user.role}</p>
                )}
              </div>
              <Avatar label={user.email} />
            </div>
          }
        >
          <DropdownMenuItem onClick={() => router.push("/settings")}>Profile</DropdownMenuItem>
          <DropdownMenuItem onClick={handleLogout} disabled={isLoggingOut}>
            {isLoggingOut ? "Signing out…" : "Log out"}
          </DropdownMenuItem>
        </DropdownMenu>
      )}
    </header>
  );
}
