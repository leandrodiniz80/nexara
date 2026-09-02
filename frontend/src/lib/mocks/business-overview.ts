import type { BusinessOverview } from "@/lib/api/types";

/**
 * Shown when /billing/overview is unreachable (timeout, 500, network error)
 * so the dashboard never renders a dead error screen for a transient
 * backend issue. Shaped exactly like the real BusinessOverview — KpiGrid
 * and BusinessIntelligence destructure these fields directly, so a flatter
 * ad hoc shape would break both components.
 *
 * Never silent: executive_insight says outright it's sample data, and
 * dashboard/page.tsx shows a "Sample data" badge whenever this is in use.
 */
export const MOCK_BUSINESS_OVERVIEW: BusinessOverview = {
  mrr: 48250,
  active_customers: 132,
  churn_rate: 3.4,
  business_score: 78,
  business_status: "growing",
  top_opportunities: [
    {
      org_id: "acme-corp",
      type: "expansion",
      priority_score: 8.7,
      recommended_action: "contact_now",
      reason: "Usage trending above plan limit for 3 weeks",
    },
    {
      org_id: "globex-inc",
      type: "high_intent",
      priority_score: 7.2,
      recommended_action: "contact_now",
    },
  ],
  at_risk_customers: [
    {
      org_id: "initech",
      type: "churn_risk",
      priority_score: 6.5,
      recommended_action: "monitor",
      revenue_at_risk: 2400,
    },
  ],
  top_customers: [
    { org_id: "acme-corp", plan: "enterprise", revenue: 8200 },
    { org_id: "globex-inc", plan: "pro", revenue: 3100 },
  ],
  conversion_summary: {
    upgrade_offer: { pending: 4, contacted: 2, converted: 1, ignored: 1, conversion_rate: 25 },
    retention_offer: { pending: 2, contacted: 1, converted: 1, ignored: 0, conversion_rate: 50 },
    expansion_offer: { pending: 3, contacted: 2, converted: 0, ignored: 1, conversion_rate: 0 },
  },
  weekly_focus: {
    org_id: "acme-corp",
    type: "expansion",
    priority_score: 8.7,
    recommended_action: "contact_now",
    message: "Follow up with Acme Corp — usage signals a likely upsell this week.",
  },
  executive_insight:
    "Sample data — live connection to the Business Overview service is temporarily unavailable.",
};
