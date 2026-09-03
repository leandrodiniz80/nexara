import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

/** Named AppNotification, not Notification — the latter is the DOM's own
 * global Web Notifications API type. */
export interface AppNotification {
  id: string;
  leadId: string | null;
  message: string;
  read: boolean;
  createdAt: string;
}

export interface NotificationList {
  notifications: AppNotification[];
  unreadCount: number;
}

interface NotificationDto {
  id: string;
  lead_id: string | null;
  message: string;
  read: boolean;
  created_at: string;
}

interface NotificationListDto {
  data: NotificationDto[];
  unread_count: number;
}

function toNotification(dto: NotificationDto): AppNotification {
  return {
    id: dto.id,
    leadId: dto.lead_id,
    message: dto.message,
    read: dto.read,
    createdAt: dto.created_at,
  };
}

/** GET /api/v1/notifications — persistent counterpart to the ephemeral
 * toasts automations have always fired; "notify" firings for a lead with
 * an assigned owner also land here. */
export async function getNotifications(): Promise<NotificationList> {
  try {
    const { data } = await apiClient.get<ApiResponse<NotificationListDto>>("/notifications");
    if (!data.data) {
      throw new Error("Notifications request succeeded but returned no data");
    }
    return {
      notifications: data.data.data.map(toNotification),
      unreadCount: data.data.unread_count,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** PATCH /api/v1/notifications/{id}/read */
export async function markNotificationRead(id: string): Promise<AppNotification> {
  try {
    const { data } = await apiClient.patch<ApiResponse<NotificationDto>>(
      `/notifications/${id}/read`
    );
    if (!data.data) {
      throw new Error("Mark-as-read succeeded but returned no data");
    }
    return toNotification(data.data);
  } catch (error) {
    throw toApiClientError(error);
  }
}
