import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

export interface Automation {
  id: string;
  name: string;
  active: boolean;
  trigger_type: string;
  trigger_from: string | null;
  trigger_to: string | null;
  action_type: "notify" | "log";
}

/** GET /api/v1/automations */
export async function getAutomations(): Promise<Automation[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<Automation[]>>("/automations");
    return data.data ?? [];
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** PATCH /api/v1/automations/{id} */
export async function toggleAutomation(id: string, active: boolean): Promise<Automation> {
  try {
    const { data } = await apiClient.patch<ApiResponse<Automation>>(`/automations/${id}`, {
      active,
    });
    if (!data.data) {
      throw new Error("Automation update succeeded but returned no data");
    }
    return data.data;
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface AutomationActivityEntry {
  leadId: string;
  leadName: string;
  automationName: string;
  actionType: "notify" | "log";
  message: string;
  createdAt: string;
}

/** Wire shape from GET /automations/activity — see AutomationActivityEntry in
 * backend/app/schemas/leads/lead_automation.py. */
interface AutomationActivityEntryDto {
  lead_id: string;
  lead_name: string;
  automation_name: string;
  action_type: "notify" | "log";
  message: string;
  created_at: string;
}

/** GET /api/v1/automations/activity */
export async function getAutomationsActivity(): Promise<AutomationActivityEntry[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<AutomationActivityEntryDto[]>>(
      "/automations/activity"
    );
    return (data.data ?? []).map((entry) => ({
      leadId: entry.lead_id,
      leadName: entry.lead_name,
      automationName: entry.automation_name,
      actionType: entry.action_type,
      message: entry.message,
      createdAt: entry.created_at,
    }));
  } catch (error) {
    throw toApiClientError(error);
  }
}
