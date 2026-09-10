import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

/** GET /api/v1/intelligence/adaptive-weights — Adaptive Scoring Weights
 * (Task 1/7, Adaptive Intelligence round): the same multipliers the
 * backend's own compute_lead_score() already applies to its matching
 * bonuses (industry:X, company_size:X, action:X, fast_response,
 * high_risk), exposed here purely for visibility. Keys with no real
 * 30-day signal yet are simply absent, not defaulted to 1.0. */
export async function getAdaptiveWeights(): Promise<Record<string, number>> {
  try {
    const { data } = await apiClient.get<ApiResponse<Record<string, number>>>(
      "/intelligence/adaptive-weights"
    );
    return data.data ?? {};
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface RevenueSimulation {
  currentExpected: number;
  optimizedExpected: number;
  delta: number;
}

interface RevenueSimulationDto {
  current_expected: number;
  optimized_expected: number;
  delta: number;
}

/** GET /api/v1/intelligence/revenue-simulation — Revenue Simulation Engine
 * (Task 5/7): a deterministic "best case" projection assuming every
 * pending action gets executed, not a forecast. */
export async function getRevenueSimulation(): Promise<RevenueSimulation> {
  try {
    const { data } = await apiClient.get<ApiResponse<RevenueSimulationDto>>(
      "/intelligence/revenue-simulation"
    );
    return {
      currentExpected: data.data?.current_expected ?? 0,
      optimizedExpected: data.data?.optimized_expected ?? 0,
      delta: data.data?.delta ?? 0,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** GET /api/v1/intelligence/exec-insight — CEO Insight Layer (Task 6/7):
 * one ready-to-render sentence combining today's lost opportunity with
 * the Revenue Simulation Engine's own optimistic delta. */
export async function getExecInsight(): Promise<string> {
  try {
    const { data } = await apiClient.get<ApiResponse<{ message: string }>>(
      "/intelligence/exec-insight"
    );
    return data.data?.message ?? "";
  } catch (error) {
    throw toApiClientError(error);
  }
}

export type GlobalStrategyFocus = "calls" | "messages" | "meetings";

export interface GlobalStrategy {
  focus: GlobalStrategyFocus;
  reason: string;
  confidence: number;
}

interface GlobalStrategyDto {
  focus: GlobalStrategyFocus;
  reason: string;
  confidence: number;
}

/** GET /api/v1/intelligence/global-strategy — Global Strategy Engine
 * (final round, Task 2/8): one recommended channel to focus on right now
 * (calls/messages/meetings), plain deterministic rules. */
export async function getGlobalStrategy(): Promise<GlobalStrategy | null> {
  try {
    const { data } = await apiClient.get<ApiResponse<GlobalStrategyDto>>(
      "/intelligence/global-strategy"
    );
    if (!data.data) return null;
    return { focus: data.data.focus, reason: data.data.reason, confidence: data.data.confidence };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export type AggressionLevel = "low" | "medium" | "high" | "extreme";
/** compute_revenue_mode()'s own relabeling of AggressionLevel (final
 * round, Task 6/8) — same underlying signal, "efficiency"/"balanced"/
 * "aggressive" vocabulary instead, for the Command Center's own Revenue
 * Mode indicator. */
export type RevenueMode = "efficiency" | "balanced" | "aggressive";

export interface AggressionState {
  level: AggressionLevel;
  revenueMode: RevenueMode;
}

/** GET /api/v1/intelligence/aggression-level — Dynamic Aggression Mode
 * (final round, Task 3/8): how hard the system should be pushing right
 * now, derived from today's lost opportunity and the Revenue Simulation
 * Engine's own gap, plus its own revenue_mode relabeling. */
export async function getAggressionLevel(): Promise<AggressionState | null> {
  try {
    const { data } = await apiClient.get<
      ApiResponse<{ level: AggressionLevel; revenue_mode: RevenueMode }>
    >("/intelligence/aggression-level");
    if (!data.data) return null;
    return { level: data.data.level, revenueMode: data.data.revenue_mode };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface RevenueLeaks {
  leadsIgnoredOver24h: number;
  highValueLeadsWithoutAction: number;
  leadsStuckSameStage: number;
  totalLeakValue: number;
}

interface RevenueLeaksDto {
  leads_ignored_over_24h: number;
  high_value_leads_without_action: number;
  leads_stuck_same_stage: number;
  total_leak_value: number;
}

/** GET /api/v1/intelligence/revenue-leaks — Revenue Leak Detector (final
 * round, Task 5/8): three independent leak patterns plus totalLeakValue,
 * the summed expectedValue across every lead caught by at least one. */
export async function getRevenueLeaks(): Promise<RevenueLeaks> {
  try {
    const { data } = await apiClient.get<ApiResponse<RevenueLeaksDto>>(
      "/intelligence/revenue-leaks"
    );
    return {
      leadsIgnoredOver24h: data.data?.leads_ignored_over_24h ?? 0,
      highValueLeadsWithoutAction: data.data?.high_value_leads_without_action ?? 0,
      leadsStuckSameStage: data.data?.leads_stuck_same_stage ?? 0,
      totalLeakValue: data.data?.total_leak_value ?? 0,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}
