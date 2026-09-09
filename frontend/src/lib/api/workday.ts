import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";
import { toLead, type Lead, type LeadDto } from "@/lib/api/leads";

export interface WorkdayNext {
  lead: Lead | null;
  isNewFocus: boolean;
  tasksCompletedToday: number;
  streakDays: number;
}

interface WorkdayNextDto {
  lead: LeadDto | null;
  is_new_focus: boolean;
  tasks_completed_today: number;
  streak_days: number;
}

/** GET /api/v1/workday/next — "Começar meu dia": always returns exactly
 * one lead to work on, or null when the queue is empty. Mutates state
 * server-side (marks the lead in_focus) — not a plain read, so don't poll
 * this the way leads-priority/leads-activity are polled. Calling it again
 * while a lead is still in focus just returns that same lead
 * (isNewFocus: false); this is what makes the continuous "complete task ->
 * fetch the next one" flow safe to drive from a single button/callback. */
export async function getWorkdayNext(): Promise<WorkdayNext> {
  try {
    const { data } = await apiClient.get<ApiResponse<WorkdayNextDto>>("/workday/next");
    if (!data.data) {
      throw new Error("Workday request succeeded but returned no data");
    }
    return {
      lead: data.data.lead ? toLead(data.data.lead) : null,
      isNewFocus: data.data.is_new_focus,
      tasksCompletedToday: data.data.tasks_completed_today,
      streakDays: data.data.streak_days,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface WorkdaySummary {
  todayTasks: number;
  overdueTasks: number;
  highPriorityLeads: number;
  leadsAtRisk: number;
  estimatedRevenueAtRisk: number;
  /** Ready-to-render sentence — built by the backend, same rule the
   * timeline/activity feed already follow. Never assembled here. */
  focusMessage: string;
  /** Probability-weighted "money genuinely at risk" — contacted leads
   * that are overdue or stale, summed by expectedValue. Narrower than
   * estimatedRevenueAtRisk above (contacted+stale only, raw value). */
  revenueAtRisk: number;
  /** "Hoje você pode gerar R$ X" — expectedValue summed over today's
   * actionable leads (overdue or due today). */
  todayPotentialRevenue: number;
  /** AI Deal Coach round — same figure as todayPotentialRevenue above,
   * re-exposed under the Deal Coach's own vocabulary. */
  moneyInPlayToday: number;
  /** expectedValue summed over dealRiskLevel === "critical" leads only —
   * narrower and more urgent than revenueAtRisk above. */
  moneyAtRiskToday: number;
  criticalDealsCount: number;
  /** Execution-assistance round — how many leads the execution engine
   * auto-sent a message for today (never counts a manual "Enviar agora"
   * click — see backend's own docstring), gated behind AUTO_MODE_ENABLED
   * (off by default, so this is 0 for most orgs today). */
  autoActionsExecutedToday: number;
  /** Feedback-loop-of-outcomes round — "X% das suas mensagens recebem
   * resposta" (Command Center). A steady 30-day rate, not a single day's
   * noisy figure — see WorkdayPerformance.responseRateToday below for
   * that sharper daily number instead. */
  responseRate: number;
  /** Sales-operating-system round — Command Center's "Leads aguardando
   * resposta": every lead with a message out and no reply yet, whatever
   * the delay (a lead that's specifically been ignored for >24h feeds the
   * separate maybe_notify_ignored_leads() org-wide alert instead, backend-
   * side only — not its own field here). */
  pendingResponsesCount: number;
  /** expectedValue >= R$5000 AND dealRiskLevel in ("high", "critical"). */
  highValueAtRiskCount: number;
  /** Command Center's "Pipeline esperado hoje (R$)" — expectedValue summed
   * across every open (new/contacted) lead, not just today's actionable
   * ones the way todayPotentialRevenue above is scoped. */
  pipelineExpectedValue: number;
}

interface WorkdaySummaryDto {
  today_tasks: number;
  overdue_tasks: number;
  high_priority_leads: number;
  leads_at_risk: number;
  estimated_revenue_at_risk: number;
  focus_message: string;
  revenue_at_risk: number;
  today_potential_revenue: number;
  money_in_play_today: number;
  money_at_risk_today: number;
  critical_deals_count: number;
  auto_actions_executed_today: number;
  response_rate: number;
  pending_responses_count: number;
  high_value_at_risk_count: number;
  pipeline_expected_value: number;
}

/** GET /api/v1/workday/summary — the Command Center's "what does today
 * look like" snapshot: task counts, leads going cold, and a rough
 * R$-at-risk estimate, plus one backend-written headline sentence. */
export async function getWorkdaySummary(): Promise<WorkdaySummary> {
  try {
    const { data } = await apiClient.get<ApiResponse<WorkdaySummaryDto>>("/workday/summary");
    if (!data.data) {
      throw new Error("Workday summary request succeeded but returned no data");
    }
    return {
      todayTasks: data.data.today_tasks,
      overdueTasks: data.data.overdue_tasks,
      highPriorityLeads: data.data.high_priority_leads,
      leadsAtRisk: data.data.leads_at_risk,
      estimatedRevenueAtRisk: data.data.estimated_revenue_at_risk,
      focusMessage: data.data.focus_message,
      revenueAtRisk: data.data.revenue_at_risk,
      todayPotentialRevenue: data.data.today_potential_revenue,
      moneyInPlayToday: data.data.money_in_play_today,
      moneyAtRiskToday: data.data.money_at_risk_today,
      criticalDealsCount: data.data.critical_deals_count,
      autoActionsExecutedToday: data.data.auto_actions_executed_today,
      responseRate: data.data.response_rate,
      pendingResponsesCount: data.data.pending_responses_count,
      highValueAtRiskCount: data.data.high_value_at_risk_count,
      pipelineExpectedValue: data.data.pipeline_expected_value,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface WorkdayCompleteAndNextResult {
  completedLeadId: string;
  completedLead: Lead;
  nextLead: Lead | null;
}

interface WorkdayCompleteAndNextDto {
  completed_lead_id: string;
  completed_lead: LeadDto;
  next_lead: LeadDto | null;
}

/** POST /api/v1/workday/complete-and-next — the Command Center's
 * continuous-flow step: completes leadId's current task and, in the same
 * request, hands back whichever lead is most worth working on next (or
 * null once the queue is empty). Does not touch in_focus the way
 * getWorkdayNext() does — this is a separate, lighter "what's next"
 * suggestion, not another entry into that lock. */
export async function completeAndNext(leadId: string): Promise<WorkdayCompleteAndNextResult> {
  try {
    const { data } = await apiClient.post<ApiResponse<WorkdayCompleteAndNextDto>>(
      "/workday/complete-and-next",
      { lead_id: leadId }
    );
    if (!data.data) {
      throw new Error("Complete-and-next request succeeded but returned no data");
    }
    return {
      completedLeadId: data.data.completed_lead_id,
      completedLead: toLead(data.data.completed_lead),
      nextLead: data.data.next_lead ? toLead(data.data.next_lead) : null,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export type FailureState = "on_track" | "at_risk" | "failing";

export interface WorkdayPerformance {
  tasksCompletedToday: number;
  tasksExpectedToday: number;
  completionRate: number;
  overdueTasks: number;
  leadsIgnoredYesterday: number;
  estimatedRevenueLost: number;
  streakDays: number;
  failureState: FailureState;
  /** Ready-to-render sentence — built by the backend, same rule
   * focusMessage/the timeline/activity feed already follow. */
  accountabilityMessage: string;
  /** Same probability-weighted figure as WorkdaySummary.revenueAtRisk. */
  revenueAtRisk: number;
  /** AI Deal Coach round. criticalDeals is the same dealRiskLevel ===
   * "critical" count as WorkdaySummary.criticalDealsCount. moneySavedToday
   * is a proxy (not exact — see backend's own docstring): high-value leads
   * with a task completed today, standing in for "deals that got acted on
   * instead of going cold." */
  criticalDeals: number;
  moneySavedToday: number;
  /** Same auto-send-only count as WorkdaySummary.autoActionsExecutedToday
   * above — the Performance Panel's own "ações automatizadas hoje". */
  autoActionsExecutedToday: number;
  /** Feedback-loop-of-outcomes round — today-only counterpart to
   * WorkdaySummary.responseRate above (that one's a steadier 30-day
   * figure for the Command Center's headline). */
  responseRateToday: number;
  responsesReceivedToday: number;
  /** Sales-operating-system round — from the same today-scoped response
   * rows responsesReceivedToday above already reads. avgResponseTimeToday
   * is null (not 0) when nobody responded today at all. */
  avgResponseTimeToday: number | null;
  fastResponsesToday: number;
}

interface WorkdayPerformanceDto {
  tasks_completed_today: number;
  tasks_expected_today: number;
  completion_rate: number;
  overdue_tasks: number;
  leads_ignored_yesterday: number;
  estimated_revenue_lost: number;
  streak_days: number;
  failure_state: FailureState;
  accountability_message: string;
  revenue_at_risk: number;
  critical_deals: number;
  money_saved_today: number;
  auto_actions_executed_today: number;
  response_rate_today: number;
  responses_received_today: number;
  avg_response_time_today: number | null;
  fast_responses_today: number;
}

/** GET /api/v1/workday/performance — the accountability layer: how much of
 * today's expected work got done, what's still overdue, what yesterday's
 * neglect is costing, and the streak — collapsed into one failureState and
 * one backend-written accountabilityMessage. A "failing" read also fires a
 * persistent notification server-side (deduped within 6h), so this is a
 * real read, not idempotent-safe to call more aggressively than the rest of
 * the dashboard's polling. */
export async function getWorkdayPerformance(): Promise<WorkdayPerformance> {
  try {
    const { data } = await apiClient.get<ApiResponse<WorkdayPerformanceDto>>(
      "/workday/performance"
    );
    if (!data.data) {
      throw new Error("Workday performance request succeeded but returned no data");
    }
    return {
      tasksCompletedToday: data.data.tasks_completed_today,
      tasksExpectedToday: data.data.tasks_expected_today,
      completionRate: data.data.completion_rate,
      overdueTasks: data.data.overdue_tasks,
      leadsIgnoredYesterday: data.data.leads_ignored_yesterday,
      estimatedRevenueLost: data.data.estimated_revenue_lost,
      streakDays: data.data.streak_days,
      failureState: data.data.failure_state,
      accountabilityMessage: data.data.accountability_message,
      revenueAtRisk: data.data.revenue_at_risk,
      criticalDeals: data.data.critical_deals,
      moneySavedToday: data.data.money_saved_today,
      autoActionsExecutedToday: data.data.auto_actions_executed_today,
      responseRateToday: data.data.response_rate_today,
      responsesReceivedToday: data.data.responses_received_today,
      avgResponseTimeToday: data.data.avg_response_time_today,
      fastResponsesToday: data.data.fast_responses_today,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface WorkdayTarget {
  dailyTarget: number;
  completedToday: number;
  remaining: number;
  progress: number;
}

interface WorkdayTargetDto {
  daily_target: number;
  completed_today: number;
  remaining: number;
  progress: number;
}

/** GET /api/v1/workday/target — the daily gamification target: a fixed
 * default (no per-user/org customization yet) matched against today's
 * completed-task count. */
export async function getWorkdayTarget(): Promise<WorkdayTarget> {
  try {
    const { data } = await apiClient.get<ApiResponse<WorkdayTargetDto>>("/workday/target");
    if (!data.data) {
      throw new Error("Workday target request succeeded but returned no data");
    }
    return {
      dailyTarget: data.data.daily_target,
      completedToday: data.data.completed_today,
      remaining: data.data.remaining,
      progress: data.data.progress,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}
