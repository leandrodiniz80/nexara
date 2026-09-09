import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

/**
 * "lost" exists on the backend enum (backend/app/models/leads/lead.py) and,
 * as of the feedback-loop round, is reachable from the UI too — but only
 * through LeadDetailsModal's dedicated "Mark as lost" flow (a reason is
 * required there), never from the casual Kanban drag or dropdown "Move to"
 * actions: losing a lead is deliberately kept out of a one-click action.
 * Table/Kanban/Card's exhaustive Record<LeadStatus, ...> maps (where they
 * have one) do need a 4th case now.
 */
export type LeadStatus = "new" | "contacted" | "converted" | "lost";

export interface ScoreBreakdownItem {
  reason: string;
  impact: number;
}

export interface EnrichmentData {
  industry: string;
  companySize: string;
  city: string;
  description: string;
  enrichedAt: string;
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
  /** Derived from nextActionDueAt at read time by the backend (score_leads)
   * — never compute "overdue" from nextActionDueAt on the client, since the
   * backend's `now` is the source of truth here. daysOverdue is null
   * whenever isOverdue is false. */
  isOverdue: boolean;
  daysOverdue: number | null;
  /** Rule-based (no LLM), backend-computed — see compute_next_best_action()
   * in scoring.py. Null for converted/lost leads. */
  nextBestAction: string | null;
  /** Only set when nextBestAction is set AND the backend's AI feature flag
   * is on — same template POST /leads/{id}/generate-message uses. */
  suggestedMessage: string | null;
  /** 0-100 estimated likelihood this lead converts — backend-computed
   * (compute_win_probability, scoring.py), no ML/LLM. */
  winProbability: number;
  /** Simulated deal size (R$), from enrichment_data's company_size — 0
   * until enriched. Always a whole number. */
  estimatedValue: number;
  /** estimatedValue * winProbability / 100 — the probability-weighted
   * forecast this lead is actually worth right now. */
  expectedValue: number;
  /** "Why this lead?" — one ready-to-render sentence built by the backend
   * (build_priority_reason, scoring.py) from the same score/winProbability/
   * estimatedValue/activity signals already on this object. Never empty —
   * a quiet lead still gets a neutral sentence. */
  priorityReason: string;
  /** AI Deal Coach round — deterministic, no external AI calls: a coarse
   * "how worried should I be" bucket (compute_deal_risk, scoring.py) from
   * money/probability/activity recency, plus a short reason sentence. Null
   * only if this Lead somehow bypassed score_leads(), which no real caller
   * does. */
  dealRiskLevel: "low" | "medium" | "high" | "critical" | null;
  dealRiskReason: string | null;
  /** Machine-readable action recommendation driven by dealRiskLevel
   * (compute_action_type_and_urgency, scoring.py) — distinct from
   * nextBestAction above (a full sentence from a separate, older rule
   * table). Null for a converted lead (nothing left to do). */
  nextBestActionType: "call_now" | "send_message" | "schedule_meeting" | "drop_lead" | "monitor" | null;
  nextBestActionUrgency: "immediate" | "high" | "medium" | "low" | null;
  /** Execution-assistance round — non-null only when nextBestActionType ===
   * "send_message" AND suggestedMessage is actually populated: the same
   * text as suggestedMessage, just under the name the "Enviar agora" flow
   * reads (LeadCard, executeLeadAction below). autoActionAvailable is that
   * same gate as a plain boolean, for a truthy-check without also caring
   * about the message's content. */
  readyToSendMessage: string | null;
  autoActionAvailable: boolean;
  /** Feedback-loop-of-outcomes round — derived from LeadActivityLog's
   * "lead_responded"/"lead_interested"/"lead_rejected" entries (see
   * recordLeadResponse below), not a stored column. "no_response" is a
   * real, always-present value — not a stand-in for null — for a lead
   * with no response recorded yet. */
  leadResponseState: "no_response" | "responded" | "interested" | "not_interested";
  /** Minutes between this lead's most recent "message_sent" activity and
   * its response — null until a response is actually recorded. */
  responseTimeMinutes: number | null;
  /** Sales-operating-system round — true whenever a "message_sent" exists
   * with no reply after it yet (stays true across a stale old response and
   * a newer unanswered message — see backend's own docstring,
   * scoring.py). responseDelayMinutes is minutes since that lead's most
   * recent message_sent, populated whenever one exists at all (pending or
   * not) — distinct from responseTimeMinutes above, which is only ever set
   * once a response actually landed. */
  hasPendingResponse: boolean;
  responseDelayMinutes: number | null;
  /** Days since this lead's most recent LeadActivityLog entry of any
   * kind — not the same as isOverdue/daysOverdue above (those track
   * next_action_due_at); some activity (e.g. recording a response) logs to
   * the timeline without otherwise touching the lead. */
  daysSinceLastActivity: number;
  /** Workday mode's execution lock — true while this lead is someone's
   * (not necessarily the current user's) active focus session. */
  inFocus: boolean;
  companyName: string | null;
  website: string | null;
  enrichmentData: EnrichmentData | null;
  createdAt: string;
  updatedAt: string;
  /** Revenue-maximization round — this org's single highest expectedValue
   * among the batch this lead was last scored alongside, minus this
   * lead's own expectedValue. Always >= 0. Powers LeadCard's own "⚠️
   * Perdendo R$ X" badge. */
  opportunityCost: number;
}

interface EnrichmentDataDto {
  industry: string;
  company_size: string;
  city: string;
  description: string;
  enriched_at: string;
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
  is_overdue: boolean;
  days_overdue: number | null;
  next_best_action: string | null;
  suggested_message: string | null;
  win_probability: number;
  estimated_value: number;
  expected_value: number;
  priority_reason: string;
  deal_risk_level: "low" | "medium" | "high" | "critical" | null;
  deal_risk_reason: string | null;
  next_best_action_type: "call_now" | "send_message" | "schedule_meeting" | "drop_lead" | "monitor" | null;
  next_best_action_urgency: "immediate" | "high" | "medium" | "low" | null;
  ready_to_send_message: string | null;
  auto_action_available: boolean;
  lead_response_state: "no_response" | "responded" | "interested" | "not_interested";
  response_time_minutes: number | null;
  has_pending_response: boolean;
  response_delay_minutes: number | null;
  days_since_last_activity: number;
  in_focus: boolean;
  company_name: string | null;
  website: string | null;
  enrichment_data: EnrichmentDataDto | null;
  created_at: string;
  updated_at: string;
  opportunity_cost: number;
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
    isOverdue: dto.is_overdue,
    daysOverdue: dto.days_overdue,
    nextBestAction: dto.next_best_action,
    suggestedMessage: dto.suggested_message,
    winProbability: dto.win_probability,
    estimatedValue: dto.estimated_value,
    expectedValue: dto.expected_value,
    priorityReason: dto.priority_reason,
    dealRiskLevel: dto.deal_risk_level,
    dealRiskReason: dto.deal_risk_reason,
    nextBestActionType: dto.next_best_action_type,
    nextBestActionUrgency: dto.next_best_action_urgency,
    readyToSendMessage: dto.ready_to_send_message,
    autoActionAvailable: dto.auto_action_available,
    leadResponseState: dto.lead_response_state,
    responseTimeMinutes: dto.response_time_minutes,
    hasPendingResponse: dto.has_pending_response,
    responseDelayMinutes: dto.response_delay_minutes,
    daysSinceLastActivity: dto.days_since_last_activity,
    inFocus: dto.in_focus,
    companyName: dto.company_name,
    website: dto.website,
    enrichmentData: dto.enrichment_data
      ? {
          industry: dto.enrichment_data.industry,
          companySize: dto.enrichment_data.company_size,
          city: dto.enrichment_data.city,
          description: dto.enrichment_data.description,
          enrichedAt: dto.enrichment_data.enriched_at,
        }
      : null,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    opportunityCost: dto.opportunity_cost,
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

/** PATCH /api/v1/leads/{id}/status. `reason` is only meaningful moving to
 * "lost" (why it was lost) — see LeadLossAction in lead-details-modal.tsx,
 * the only UI flow that ever passes one. Ignored by the backend for every
 * other status. */
export async function updateLeadStatus(
  id: string,
  status: LeadStatus,
  reason?: string
): Promise<LeadStatusUpdateResult> {
  try {
    const { data } = await apiClient.patch<
      ApiResponse<{ lead: LeadDto; notifications: string[] }>
    >(`/leads/${id}/status`, { status, reason });
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
  | "task_completed"
  | "enriched"
  | "message_generated";

/** Coarse bucket for `type`, additive alongside it — lets the UI pick an
 * icon without a case per exact fine-grained type. See TimelineCategory in
 * backend/app/schemas/leads/lead.py. */
export type LeadTimelineCategory = "status_change" | "automation" | "activity";

export interface LeadTimelineEntry {
  id: string;
  type: LeadTimelineEntryType;
  category: LeadTimelineCategory;
  from: string | null;
  to: string | null;
  /** Always a ready-to-render sentence — built by the backend, never
   * assembled here. */
  message: string;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}

/** Wire shape from GET /leads/{id}/timeline — see LeadTimelineEntry in
 * backend/app/schemas/leads/lead.py. Only "status_changed" carries from/to;
 * every type carries a backend-generated message. */
interface LeadTimelineEntryDto {
  id: string;
  type: LeadTimelineEntryType;
  category: LeadTimelineCategory;
  from: string | null;
  to: string | null;
  message: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

/** GET /api/v1/leads/{id}/timeline */
export async function getLeadTimeline(id: string): Promise<LeadTimelineEntry[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadTimelineEntryDto[]>>(
      `/leads/${id}/timeline`
    );
    return (data.data ?? []).map((entry) => ({
      id: entry.id,
      type: entry.type,
      category: entry.category,
      from: entry.from,
      to: entry.to,
      message: entry.message,
      metadata: entry.metadata,
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
  id: string;
  leadId: string;
  leadName: string;
  type: LeadTimelineEntryType;
  category: LeadTimelineCategory;
  message: string;
  metadata: Record<string, unknown> | null;
  createdAt: string;
}

/** Wire shape from GET /leads/activity — see LeadActivityFeedEntry in
 * backend/app/schemas/leads/lead.py. */
interface LeadActivityFeedEntryDto {
  id: string;
  lead_id: string;
  lead_name: string;
  type: LeadTimelineEntryType;
  category: LeadTimelineCategory;
  message: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

/** GET /api/v1/leads/activity — org-wide activity feed (status changes,
 * automation firings, owner/notes/task-completion events across every
 * lead), soonest-first. Backend default limit is 20; the dashboard's Recent
 * Activity card slices to the 10 it actually displays. */
export async function getLeadsActivityFeed(): Promise<LeadActivityFeedEntry[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeadActivityFeedEntryDto[]>>(
      "/leads/activity"
    );
    return (data.data ?? []).map((entry) => ({
      id: entry.id,
      leadId: entry.lead_id,
      leadName: entry.lead_name,
      type: entry.type,
      category: entry.category,
      message: entry.message,
      metadata: entry.metadata,
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

/** POST /api/v1/leads/{id}/enrich — "Atualizar dados": (re-)runs the
 * simulated enrichment pass, deterministic per lead (same profile every
 * time, not a different random one on each click). */
export async function enrichLead(id: string): Promise<Lead> {
  try {
    const { data } = await apiClient.post<ApiResponse<LeadDto>>(`/leads/${id}/enrich`, {});
    if (!data.data) {
      throw new Error("Enrichment succeeded but returned no data");
    }
    return toLead(data.data);
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** POST /api/v1/leads/{id}/generate-message — template-based first-contact
 * message (no LLM yet). Works whether or not the lead has been enriched. */
export async function generateLeadMessage(id: string): Promise<string> {
  try {
    const { data } = await apiClient.post<ApiResponse<{ message: string }>>(
      `/leads/${id}/generate-message`,
      {}
    );
    if (!data.data) {
      throw new Error("Message generation succeeded but returned no data");
    }
    return data.data.message;
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** GET /api/v1/leads/insights — org-wide learning-layer patterns mined from
 * real outcomes (compute_conversion_insights, scoring.py). Every field is
 * null until there's enough real outcome data to say something (e.g. no
 * lead converted yet). Backs the dashboard's Learning Panel. */
export interface ConversionInsights {
  bestIndustry: string | null;
  bestCompanySize: string | null;
  avgTimeToCloseDays: number | null;
  topLossReason: string | null;
}

interface ConversionInsightsDto {
  best_industry: string | null;
  best_company_size: string | null;
  avg_time_to_close_days: number | null;
  top_loss_reason: string | null;
}

export async function getLeadInsights(): Promise<ConversionInsights> {
  try {
    const { data } = await apiClient.get<ApiResponse<ConversionInsightsDto>>("/leads/insights");
    if (!data.data) {
      throw new Error("Insights request succeeded but returned no data");
    }
    return {
      bestIndustry: data.data.best_industry,
      bestCompanySize: data.data.best_company_size,
      avgTimeToCloseDays: data.data.avg_time_to_close_days,
      topLossReason: data.data.top_loss_reason,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export type LeadExecutableAction = "send_message" | "call_now" | "schedule_meeting";

/** POST /api/v1/leads/{id}/execute-action — execution-assistance round.
 * "send_message" 400s if the lead has no readyToSendMessage at the moment
 * the backend re-checks it (LeadCard only ever shows the "Enviar agora"
 * button when autoActionAvailable is already true, so this is a safety
 * net for a stale client cache, not the normal path). Returns the lead's
 * fresh state — same single-Lead shape enrichLead()/updateLeadOwner()
 * already return, no {lead, notifications} wrapper (this endpoint doesn't
 * fire automations). */
export async function executeLeadAction(id: string, action: LeadExecutableAction): Promise<Lead> {
  try {
    const { data } = await apiClient.post<ApiResponse<LeadDto>>(`/leads/${id}/execute-action`, {
      action,
    });
    if (!data.data) {
      throw new Error("Execute-action request succeeded but returned no data");
    }
    return toLead(data.data);
  } catch (error) {
    throw toApiClientError(error);
  }
}

export type LeadResponseOutcome = "responded" | "interested" | "not_interested";

/** POST /api/v1/leads/{id}/record-response — feedback-loop-of-outcomes
 * round. Closes the loop execute-action opened: records a real reply so
 * leadResponseState/the response-rate metrics/compute_lead_score
 * (scoring.py) all learn from real outcomes instead of assumptions.
 * Returns the lead's fresh state, same shape as executeLeadAction() above. */
export async function recordLeadResponse(
  id: string,
  responseOutcome: LeadResponseOutcome
): Promise<Lead> {
  try {
    const { data } = await apiClient.post<ApiResponse<LeadDto>>(`/leads/${id}/record-response`, {
      response: responseOutcome,
    });
    if (!data.data) {
      throw new Error("Record-response request succeeded but returned no data");
    }
    return toLead(data.data);
  } catch (error) {
    throw toApiClientError(error);
  }
}
