"use client";

import { Bell } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DropdownMenu, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import {
  getNotifications,
  markNotificationRead,
  type AppNotification,
} from "@/lib/api/notifications";
import { formatRelativeTime } from "@/lib/utils/format";

export function NotificationBell() {
  const router = useRouter();
  const queryClient = useQueryClient();

  // 30s poll — same lightweight "no websocket yet" refresh the dashboard's
  // priority/activity feeds use, so the badge count and the toast-replacing
  // list both stay close to real time without any new infra.
  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: getNotifications,
    refetchInterval: 30000,
  });

  const markRead = useMutation({
    mutationFn: (id: string) => markNotificationRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const notifications = data?.notifications ?? [];
  const unreadCount = data?.unreadCount ?? 0;

  function handleSelect(notification: AppNotification) {
    if (!notification.read) markRead.mutate(notification.id);
    if (notification.leadId) router.push(`/leads?lead=${notification.leadId}`);
  }

  return (
    <DropdownMenu
      align="end"
      panelClassName="w-80"
      trigger={
        <span className="relative flex h-9 w-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-semibold text-destructive-foreground">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </span>
      }
    >
      {notifications.length === 0 ? (
        <p className="px-2 py-3 text-center text-sm text-muted-foreground">No notifications</p>
      ) : (
        notifications.map((notification) => (
          <DropdownMenuItem
            key={notification.id}
            onClick={() => handleSelect(notification)}
            className="flex-col items-start gap-0.5 whitespace-normal py-2"
          >
            <span className={notification.read ? "text-muted-foreground" : "font-medium"}>
              {notification.message}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatRelativeTime(notification.createdAt)}
            </span>
          </DropdownMenuItem>
        ))
      )}
    </DropdownMenu>
  );
}
