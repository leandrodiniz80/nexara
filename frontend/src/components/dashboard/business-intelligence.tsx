import { AlertTriangle, Sparkles, Target } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AtRiskCustomerEntry, BusinessOverview, OpportunityEntry } from "@/lib/api/types";
import { formatCurrency } from "@/lib/utils/format";

const ACTION_BADGE: Record<string, "success" | "warning" | "destructive"> = {
  contact_now: "destructive",
  monitor: "warning",
  ignore: "success",
};

function EmptyState({ message }: { message: string }) {
  return <p className="py-6 text-center text-sm text-muted-foreground">{message}</p>;
}

function OpportunityRow({ entry }: { entry: OpportunityEntry }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-2.5 last:border-0">
      <div>
        <p className="text-sm font-medium text-foreground">{entry.org_id}</p>
        <p className="text-xs capitalize text-muted-foreground">{entry.type.replace("_", " ")}</p>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-muted-foreground">
          Priority {entry.priority_score.toFixed(1)}
        </span>
        <Badge variant={ACTION_BADGE[entry.recommended_action] ?? "warning"}>
          {entry.recommended_action.replace("_", " ")}
        </Badge>
      </div>
    </div>
  );
}

function AtRiskRow({ entry }: { entry: AtRiskCustomerEntry }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-2.5 last:border-0">
      <div>
        <p className="text-sm font-medium text-foreground">{entry.org_id}</p>
        <p className="text-xs text-muted-foreground">
          {formatCurrency(entry.revenue_at_risk)} at risk
        </p>
      </div>
      <Badge variant={ACTION_BADGE[entry.recommended_action] ?? "warning"}>
        {entry.recommended_action.replace("_", " ")}
      </Badge>
    </div>
  );
}

export function BusinessIntelligence({ overview }: { overview: BusinessOverview }) {
  const totalRevenueAtRisk = overview.at_risk_customers.reduce(
    (sum, entry) => sum + entry.revenue_at_risk,
    0
  );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card className="lg:col-span-2">
        <CardHeader className="flex flex-row items-center gap-2 space-y-0">
          <Sparkles className="h-4 w-4 text-primary" />
          <CardTitle className="text-foreground">Executive Insight</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-foreground/90">
            {overview.executive_insight}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center gap-2 space-y-0">
          <Target className="h-4 w-4 text-primary" />
          <CardTitle className="text-foreground">Weekly Focus</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-foreground/90">{overview.weekly_focus.message}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-foreground">Revenue at Risk</CardTitle>
          <AlertTriangle className="h-4 w-4 text-destructive" />
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold text-foreground">
            {formatCurrency(totalRevenueAtRisk)}
          </p>
          <p className="text-xs text-muted-foreground">
            Across {overview.at_risk_customers.length} at-risk account
            {overview.at_risk_customers.length === 1 ? "" : "s"}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-foreground">Top Opportunities</CardTitle>
        </CardHeader>
        <CardContent>
          {overview.top_opportunities.length === 0 ? (
            <EmptyState message="No revenue opportunities right now." />
          ) : (
            overview.top_opportunities.map((entry, index) => (
              <OpportunityRow key={`${entry.org_id}-${entry.type}-${index}`} entry={entry} />
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-foreground">At-Risk Customers</CardTitle>
        </CardHeader>
        <CardContent>
          {overview.at_risk_customers.length === 0 ? (
            <EmptyState message="No customers currently at risk." />
          ) : (
            overview.at_risk_customers.map((entry, index) => (
              <AtRiskRow key={`${entry.org_id}-${index}`} entry={entry} />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
