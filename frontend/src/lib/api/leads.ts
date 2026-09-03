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

export interface ScoreBreakdownItem {
  reason: string;
  impact: number;
}

export interface Lead {
  id: string;
  name: string;
  email: string;
  phone: string;
  status: LeadStatus;
  /** Computed dynamically by the backend at read time (not a stored,
   * manually-set value) — see scoreBreakdown for why it's whatever it is. */
  score: number;
  scoreBreakdown: ScoreBreakdownItem[];
  notes: string | null;
  nextAction: string | null;
  nextActionDueAt: string | null;
  ownerEmail: string | null;
  /** Workday mode's execution lock — true while this lead is someone's
   * (not necessarily the current user's) active focus session. */
  inFocus: boolean;
  createdAt: string;
  updatedAt: string;
}

/** Wire shape from GET/POST/PATCH /leads — snake_case, matches every other
 * response in this API (see LeadResponse in backend/app/schemas/leads/lead.py).
 * Exported for lib/api/workday.ts, which returns this same shape. */
export interface LeadDto {
  id: string;
  organization_id: string;
  name: string;
  email: string;
  phone: string;
  status: LeadStatus;
  score: number;
  score_breakdown: ScoreBreakdownItem[];
  notes: string | null;
  next_action: string | null;
  next_action_due_at: string | null;
  owner_email: string | null;
  in_focus: boolean;
  created_at: string;
  updated_at: string;
}

export function toLead(dto: LeadDto): Lead {
  return {
    id: dto.id,
    name: dto.name,
    email: dto.email,
    phone: dto.phone,
    status: dto.status,
    score: dto.score,
    scoreBreakdown: dto.score_breakdown,
    notes: dto.notes,
    nextAction: dto.next_action,
    nextActionDueAt: dto.next_action_due_at,
    ownerEmail: dto.owner_email,
    inFocus: dto.in_focus,
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

export type LeadTimelineEntryType =
  | "status_changed"
  | "automation_fired"
  | "owner_changed"
  | "details_updated"
  | "task_completed";

export interface LeadTimelineEntry {
  type: LeadTimelineEntryType;
  from: string | null;
  to: string | null;
  message: string | null;
  createdAt: string;
}

/** Wire shape from GET /leads/{id}/timeline — see LeadTimelineEntry in
 * backend/app/schemas/leads/lead.py. Only "status_changed" carries from/to;
 * every other type carries message instead. */
interface LeadTimelineEntryDto {
  type: LeadTimelineEntryType;
  from: string | null;
  to: string | null;
  message: string | null;
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
      message: entry.message,
      createdAt: entry.created_at,
    }));
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** PATCH /api/v1/leads/{id}/details — every field optional; only the ones
 * passed are sent, so a single-field autosave never clobbers the others. */
export async function updateLeadDetails(
  id: string,
  patch: { notes?: string; nextAction?: string; nextActionDueAt?: string | null }
): Promise<Lead> {
  try {
    const body: Record<string, string | null> = {};
    if (patch.notes !== undefined) body.notes = patch.notes;
    if (patch.nextAction !== undefined) body.next_action = patch.nextAction;
    if (patch.nextActionDueAt !== undefined) body.next_action_due_at = patch.nextActionDueAt;

    const { data } = await apiClient.patch<ApiResponse<LeadDto>>(`/leads/${id}/details`, body);
    if (!data.data) {
      throw new Error("Lead details update succeeded but returned no data");
    }
    return toLead(data.data);
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** GET /api/v1/leads/tasks — leads with a next_action set, soonest due
 * first. Backs the dashboard's Upcoming Tasks card. */
export async function getLeadTasks(): Promise<Lead[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadDto[]>>("/leads/tasks");
    return (data.data ?? []).map(toLead);
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** PATCH /api/v1/leads/{id}/owner — ownerEmail null unassigns; any other
 * value must be an existing member of the caller's own organization (the
 * backend 400s otherwise). */
export async function updateLeadOwner(id: string, ownerEmail: string | null): Promise<Lead> {
  try {
    const { data } = await apiClient.patch<ApiResponse<LeadDto>>(`/leads/${id}/owner`, {
      owner_email: ownerEmail,
    });
    if (!data.data) {
      throw new Error("Owner update succeeded but returned no data");
    }
    return toLead(data.data);
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** POST /api/v1/leads/{id}/complete-task — marks the lead's current
 * next_action done and clears it (+ its due date). Same {lead,
 * notifications} shape as createLead/updateLeadStatus, though notifications
 * is always empty today (no automation fires on this event yet). */
export async function completeLeadTask(id: string): Promise<LeadStatusUpdateResult> {
  try {
    const { data } = await apiClient.post<
      ApiResponse<{ lead: LeadDto; notifications: string[] }>
    >(`/leads/${id}/complete-task`, {});
    if (!data.data) {
      throw new Error("Task completion succeeded but returned no data");
    }
    return { lead: toLead(data.data.lead), notifications: data.data.notifications };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface LeadActivityFeedEntry {
  leadId: string;
  leadName: string;
  type: LeadTimelineEntryType;
  message: string;
  createdAt: string;
}

/** Wire shape from GET /leads/activity — see LeadActivityFeedEntry in
 * backend/app/schemas/leads/lead.py. */
interface LeadActivityFeedEntryDto {
  lead_id: string;
  lead_name: string;
  type: LeadTimelineEntryType;
  message: string;
  created_at: string;
}

/** GET /api/v1/leads/activity — org-wide activity feed (status changes,
 * automation firings, owner/notes/task-completion events across every
 * lead), soonest-first. Backs the dashboard's Recent Activity card. */
export async function getLeadsActivityFeed(): Promise<LeadActivityFeedEntry[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadActivityFeedEntryDto[]>>(
      "/leads/activity"
    );
    return (data.data ?? []).map((entry) => ({
      leadId: entry.lead_id,
      leadName: entry.lead_name,
      type: entry.type,
      message: entry.message,
      createdAt: entry.created_at,
    }));
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** GET /api/v1/leads/priority — "foco do dia": leads in the worst shape
 * right now (soonest overdue/due task first, then lowest score), backend
 * default limit. Backs the dashboard's Today's Focus card. */
export async function getLeadsPriority(): Promise<Lead[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadDto[]>>("/leads/priority");
    return (data.data ?? []).map(toLead);
  } catch (error) {
    throw toApiClientError(error);
  }
}
