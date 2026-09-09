import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse } from "@/lib/api/types";

export interface LeaderboardEntry {
  userId: string;
  /** Same raw email as userId — this codebase's real user identity has no
   * separate display-name column anywhere (see backend's own
   * UserPerformanceResponse docstring), so "name" is just the email. */
  name: string;
  revenueConverted: number;
  responseRate: number;
  avgResponseTimeMinutes: number | null;
  /** 1-based rank — #1 is the top performer. */
  position: number;
  commissionEstimate: number;
  badges: string[];
}

interface LeaderboardEntryDto {
  user_id: string;
  name: string;
  revenue_converted: number;
  response_rate: number;
  avg_response_time_minutes: number | null;
  position: number;
  commission_estimate: number;
  badges: string[];
}

/** GET /api/v1/performance/leaderboard — Multi-user revenue-war round's
 * Leaderboard Engine: every team member (anyone owning at least one lead
 * in this org) ranked by revenue_converted DESC, then response_rate DESC,
 * then avg_response_time_minutes ASC. */
export async function getLeaderboard(): Promise<LeaderboardEntry[]> {
  try {
    const { data } = await apiClient.get<ApiResponse<LeaderboardEntryDto[]>>(
      "/performance/leaderboard"
    );
    return (data.data ?? []).map((entry) => ({
      userId: entry.user_id,
      name: entry.name,
      revenueConverted: entry.revenue_converted,
      responseRate: entry.response_rate,
      avgResponseTimeMinutes: entry.avg_response_time_minutes,
      position: entry.position,
      commissionEstimate: entry.commission_estimate,
      badges: entry.badges,
    }));
  } catch (error) {
    throw toApiClientError(error);
  }
}

export interface TeamSummary {
  totalRevenue: number;
  totalConvertedToday: number;
  totalAtRisk: number;
  avgResponseRate: number;
  topPerformerName: string | null;
  worstPerformerName: string | null;
}

interface TeamSummaryDto {
  total_revenue: number;
  total_converted_today: number;
  total_at_risk: number;
  avg_response_rate: number;
  top_performer_name: string | null;
  worst_performer_name: string | null;
}

/** GET /api/v1/performance/team-summary — org-wide roll-up of the same
 * per-user metrics the leaderboard reads. */
export async function getTeamSummary(): Promise<TeamSummary> {
  try {
    const { data } = await apiClient.get<ApiResponse<TeamSummaryDto>>(
      "/performance/team-summary"
    );
    if (!data.data) {
      throw new Error("Team summary request succeeded but returned no data");
    }
    return {
      totalRevenue: data.data.total_revenue,
      totalConvertedToday: data.data.total_converted_today,
      totalAtRisk: data.data.total_at_risk,
      avgResponseRate: data.data.avg_response_rate,
      topPerformerName: data.data.top_performer_name,
      worstPerformerName: data.data.worst_performer_name,
    };
  } catch (error) {
    throw toApiClientError(error);
  }
}
