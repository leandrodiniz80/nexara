import { Layers, Percent, Target, Users } from "lucide-react";
import type * as React from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeadMetrics } from "@/lib/api/leads";
import { formatNumber, formatPercent } from "@/lib/utils/format";

function MetricCard({
  title,
  value,
  icon: Icon,
}: {
  title: string;
  value: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle>{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold text-foreground">{value}</div>
      </CardContent>
    </Card>
  );
}

export function LeadsMetricsGrid({ metrics }: { metrics: LeadMetrics }) {
  const inPipeline = metrics.by_status.new + metrics.by_status.contacted;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <MetricCard title="Total Leads" value={formatNumber(metrics.total)} icon={Users} />
      <MetricCard
        title="Conversion Rate"
        value={formatPercent(metrics.conversion_rate)}
        icon={Percent}
      />
      <MetricCard
        title="Leads Converted"
        value={formatNumber(metrics.by_status.converted)}
        icon={Target}
      />
      <MetricCard title="Leads in Pipeline" value={formatNumber(inPipeline)} icon={Layers} />
    </div>
  );
}
