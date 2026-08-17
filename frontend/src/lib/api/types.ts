/**
 * Mirrors backend/app/api/responses/api_response.py and
 * backend/app/api/responses/error_response.py exactly — every Nexara API
 * route returns this envelope, success or failure alike.
 */
export interface ApiError {
  code: string;
  message: string;
  details: unknown | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  errors: ApiError[];
  warnings: string[];
  request_id: string;
  execution_time: number;
  timestamp: string;
}

/** backend/app/api/routers/auth.py: LoginRequest */
export interface LoginRequest {
  email: string;
  password: string;
}

/** backend/app/api/routers/auth.py: SessionResponse */
export interface SessionResponse {
  token: string;
  email: string;
}

/** backend/app/api/routers/auth.py: MeResponse */
export interface MeResponse {
  email: string;
  role: string | null;
  permissions: string[];
  organization_id: string | null;
}

/**
 * backend/app/platform/revenue/business_overview.py: an entry annotated by
 * BusinessOverviewEngine._annotate() — shared shape for top_opportunities
 * and (extended with revenue_at_risk) at_risk_customers.
 */
export interface OpportunityEntry {
  org_id: string;
  type: "high_intent" | "expansion" | "churn_risk" | string;
  priority_score: number;
  recommended_action: "contact_now" | "monitor" | "ignore" | string;
  reason?: string;
  score?: number;
}

export interface AtRiskCustomerEntry extends OpportunityEntry {
  revenue_at_risk: number;
}

export interface TopCustomerEntry {
  org_id: string;
  plan: string;
  revenue: number;
}

export interface WeeklyFocus {
  org_id: string | null;
  type: string | null;
  priority_score: number | null;
  recommended_action: string | null;
  message: string;
}

/** backend/app/platform/revenue/lead_execution.py: LeadExecutionTracker.conversion_summary() */
export interface ConversionMetrics {
  pending: number;
  contacted: number;
  converted: number;
  ignored: number;
  conversion_rate: number;
}

export interface ConversionSummary {
  upgrade_offer: ConversionMetrics;
  retention_offer: ConversionMetrics;
  expansion_offer: ConversionMetrics;
}

/** backend/app/api/routers/billing.py: BusinessOverviewResponse (GET /billing/overview) */
export interface BusinessOverview {
  mrr: number;
  active_customers: number;
  churn_rate: number;
  business_score: number;
  business_status: "growing" | "stable" | "risk" | string;
  top_opportunities: OpportunityEntry[];
  at_risk_customers: AtRiskCustomerEntry[];
  top_customers: TopCustomerEntry[];
  conversion_summary: ConversionSummary;
  weekly_focus: WeeklyFocus;
  executive_insight: string;
}
