import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

/**
 * "lost" exists on the backend enum (backend/app/models/leads/lead.py) but
 * nothing in this UI produces it yet (no Kanban column, no dropdown option)
 * — kept out of this type on purpose so Table/Kanban/Card's exhaustive
 * Record<LeadStatus, ...> maps don't need a 4th case for a status the UI
 * never sets.
 */
export type LeadStatus = "new" | "contacted" | "converted";

export interface Lead {
  id: string;
  name: string;
  email: string;
  phone: string;
  status: LeadStatus;
  score: number;
  createdAt: string;
  updatedAt: string;
}

/** Wire shape from GET/POST/PATCH /leads — snake_case, matches every other
 * response in this API (see LeadResponse in backend/app/schemas/leads/lead.py). */
interface LeadDto {
  id: string;
  organization_id: string;
  name: string;
  email: string;
  phone: string;
  status: LeadStatus;
  score: number;
  created_at: string;
  updated_at: string;
}

function toLead(dto: LeadDto): Lead {
  return {
    id: dto.id,
    name: dto.name,
    email: dto.email,
    phone: dto.phone,
    status: dto.status,
    score: dto.score,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

/** GET /api/v1/leads */
export async function getLeads(): Promise<Lead[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadDto[]>>("/leads");
    return (data.data ?? []).map(toLead);
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface LeadCreateResult {
  lead: Lead;
  notifications: string[];
}

/** POST /api/v1/leads — can now also fire a "lead_created" notify
 * automation, so the response carries the same {lead, notifications} shape
 * as updateLeadStatus() below. */
export async function createLead(body: {
  name: string;
  email: string;
  phone: string;
}): Promise<LeadCreateResult> {
  try {
    const { data } = await apiClient.post<
      ApiResponse<{ lead: LeadDto; notifications: string[] }>
    >("/leads", body);
    if (!data.data) {
      throw new Error("Lead creation succeeded but returned no data");
    }
    return { lead: toLead(data.data.lead), notifications: data.data.notifications };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface LeadMetrics {
  total: number;
  by_status: {
    new: number;
    contacted: number;
    converted: number;
  };
  conversion_rate: number;
  avg_score: number;
}

/** GET /api/v1/leads/metrics */
export async function getLeadMetrics(): Promise<LeadMetrics> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadMetrics>>("/leads/metrics");
    if (!data.data) {
      throw new Error("Metrics request succeeded but returned no data");
    }
    return data.data;
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface LeadStatusUpdateResult {
  lead: Lead;
  notifications: string[];
}

/** PATCH /api/v1/leads/{id}/status */
export async function updateLeadStatus(
  id: string,
  status: LeadStatus
): Promise<LeadStatusUpdateResult> {
  try {
    const { data } = await apiClient.patch<
      ApiResponse<{ lead: LeadDto; notifications: string[] }>
    >(`/leads/${id}/status`, { status });
    if (!data.data) {
      throw new Error("Status update succeeded but returned no data");
    }
    return { lead: toLead(data.data.lead), notifications: data.data.notifications };
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** GET /api/v1/leads/attention — leads still active (not converted) with no
 * status change (or any other edit) in at least 3 days, oldest-touched
 * first. Backend default for stale_after_days/limit, no params needed. */
export async function getLeadsNeedingAttention(): Promise<Lead[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadDto[]>>("/leads/attention");
    return (data.data ?? []).map(toLead);
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface LeadTimelineEntry {
  type: "status_changed";
  from: string | null;
  to: string;
  createdAt: string;
}

/** Wire shape from GET /leads/{id}/timeline — see LeadTimelineEntry in
 * backend/app/schemas/leads/lead.py. */
interface LeadTimelineEntryDto {
  type: "status_changed";
  from: string | null;
  to: string;
  created_at: string;
}

/** GET /api/v1/leads/{id}/timeline */
export async function getLeadTimeline(id: string): Promise<LeadTimelineEntry[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadTimelineEntryDto[]>>(
      `/leads/${id}/timeline`
    );
    return (data.data ?? []).map((entry) => ({
      type: entry.type,
      from: entry.from,
      to: entry.to,
      createdAt: entry.created_at,
    }));
  } catch (error) {
    throw toApiClientError(error);
  }
}
