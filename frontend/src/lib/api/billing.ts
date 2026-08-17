import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse, BusinessOverview } from "@/lib/api/types";

/** GET /api/v1/billing/overview — backend/app/api/routers/billing.py, admin-only */
export async function getBusinessOverview(): Promise<BusinessOverview> {
  try {
    const { data } = await apiClient.get<ApiResponse<BusinessOverview>>("/billing/overview");
    if (!data.data) {
      throw new Error("Business overview request succeeded but returned no data");
    }
    return data.data;
  } catch (error) {
    throw toApiClientError(error);
  }
}
