import { CheckCircle2 } from "lucide-react";
import { memo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const MAX_PLAN_ITEMS = 3;

// The backend's focus value (FOCUS_BY_NEXT_ACTION, intelligence.py) is a
// raw English token ("calls"/"messages"/"meetings") — translated here only
// for display. An unrecognized value (none exist today — always one of
// these three) falls back to "oportunidades" rather than echoing the raw
// token, so no English can ever reach the screen.
const FOCUS_LABEL: Record<string, string> = {
  calls: "ligações",
  messages: "mensagens",
  meetings: "reuniões",
};

export const ExecutionPlan = memo(function ExecutionPlan({
  focus,
  plan,
}: {
  focus: string;
  plan: string[];
}) {
  // The backend's no-action fallback line ("continue monitorando o
  // pipeline", workday_engine.py) carries the one other English loanword
  // that can reach this screen. Sanitized the same way as focus/urgency
  // above — display-only, the underlying plan text is untouched.
  const items = plan
    .slice(0, MAX_PLAN_ITEMS)
    .map((item) => item.replace(/\bpipeline\b/gi, "oportunidades"));
  const focusLabel = FOCUS_LABEL[focus] ?? "oportunidades";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm text-foreground">
          Hoje você precisa: <span className="text-muted-foreground">foco em {focusLabel}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-0">
        {items.map((item, index) => (
          <div key={index} className="flex items-start gap-2 text-sm text-foreground">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>{item}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
});
