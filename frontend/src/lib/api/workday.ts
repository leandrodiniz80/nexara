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
