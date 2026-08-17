import { Activity, Gauge, TrendingDown, TrendingUp, Users } from "lucide-react";
import type * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BusinessOverview } from "@/lib/api/types";
import { cn } from "@/lib/utils/cn";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/utils/format";

const STATUS_BADGE: Record<string, "success" | "warning" | "destructive"> = {
  growing: "success",
  stable: "warning",
  risk: "destructive",
};

function KpiCard({
  title,
  value,
  icon: Icon,
  trend,
}: {
  title: string;
  value: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  trend?: "up" | "down";
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle>{title}</CardTitle>
        <Icon
          className={cn(
            "h-4 w-4 text-muted-foreground",
            trend === "up" && "text-success",
            trend === "down" && "text-destructive"
          )}
        />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold text-foreground">{value}</div>
      </CardContent>
    </Card>
  );
}

export function KpiGrid({ overview }: { overview: BusinessOverview }) {
  const arr = overview.mrr * 12;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <KpiCard title="MRR" value={formatCurrency(overview.mrr)} icon={TrendingUp} />
      <KpiCard title="ARR" value={formatCurrency(arr)} icon={TrendingUp} />
      <KpiCard
        title="Active Customers"
        value={formatNumber(overview.active_customers)}
        icon={Users}
      />
      <KpiCard
        title="Churn Rate"
        value={formatPercent(overview.churn_rate)}
        icon={TrendingDown}
        trend={overview.churn_rate > 0 ? "down" : undefined}
      />
      <KpiCard title="Business Score" value={`${overview.business_score}/100`} icon={Gauge} />
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle>Business Status</CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <Badge variant={STATUS_BADGE[overview.business_status] ?? "warning"} className="text-sm capitalize">
            {overview.business_status}
          </Badge>
        </CardContent>
      </Card>
    </div>
  );
}
