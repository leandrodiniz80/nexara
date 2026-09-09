import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

export interface RevenueSummary {
  potentialRevenue: number;
  convertedRevenue: number;
  lostRevenue: number;
  atRiskRevenue: number;
  conversionRate: number;
}

interface RevenueSummaryDto {
  potential_revenue: number;
  converted_revenue: number;
  lost_revenue: number;
  at_risk_revenue: number;
  conversion_rate: number;
}

/** GET /api/v1/revenue/summary — org-wide revenue snapshot: pipeline
 * potential, what's already closed, what's been lost, and how much of the
 * open pipeline is going cold, plus the overall conversion rate. Every R$
 * figure is derived at read time from each lead's enrichment_data — never
 * a stored value. */
export async function getRevenueSummary(): Promise<RevenueSummary> {
  try {
    const { data } = await apiClient.get<ApiResponse<RevenueSummaryDto>>("/revenue/summary");
    if (!data.data) {
      throw new Error("Revenue summary request succeeded but returned no data");
    }
    return {
      potentialRevenue: data.data.potential_revenue,
      convertedRevenue: data.data.converted_revenue,
      lostRevenue: data.data.lost_revenue,
      atRiskRevenue: data.data.at_risk_revenue,
      conversionRate: data.data.conversion_rate,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface RevenueTrendDay {
  /** "YYYY-MM-DD" */
  date: string;
  converted: number;
  lost: number;
  created: number;
}

/** GET /api/v1/revenue/performance-trend — last 7 days, oldest first. Each
 * day's converted/lost/created is the estimated value (R$) of leads that
 * hit that state on that day, not a plain count. */
export async function getRevenuePerformanceTrend(): Promise<RevenueTrendDay[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<RevenueTrendDay[]>>(
      "/revenue/performance-trend"
    );
    return data.data ?? [];
  } catch (error) {
    throw toApiClientError(error);
  }
}
