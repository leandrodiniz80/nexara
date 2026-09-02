import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeadMetrics } from "@/lib/api/leads";

const STAGES: { label: string; key: keyof LeadMetrics["by_status"] }[] = [
  { label: "New", key: "new" },
  { label: "Contacted", key: "contacted" },
  { label: "Converted", key: "converted" },
];

export function PipelineBar({ metrics }: { metrics: LeadMetrics }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-foreground">Pipeline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {STAGES.map((stage) => {
          const value = metrics.by_status[stage.key];
          const pct = metrics.total > 0 ? (value / metrics.total) * 100 : 0;

          return (
            <div key={stage.key}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-foreground">{stage.label}</span>
                <span className="text-muted-foreground">
                  {value} ({pct.toFixed(0)}%)
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
