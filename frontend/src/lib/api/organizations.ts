import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

export interface OrgMember {
  email: string;
}

/** GET /api/v1/org/members — backs the lead-owner assignment dropdown. */
export async function getOrgMembers(): Promise<OrgMember[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<OrgMember[]>>("/org/members");
    return data.data ?? [];
  } catch (error) {
    throw toApiClientError(error);
  }
}
