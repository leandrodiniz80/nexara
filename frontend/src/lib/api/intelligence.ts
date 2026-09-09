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
