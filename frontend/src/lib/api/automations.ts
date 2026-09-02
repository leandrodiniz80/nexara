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
