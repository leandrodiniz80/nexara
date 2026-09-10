import { Card, CardContent } from "@/components/ui/card";
import type { PressureState, PressureStateValue } from "@/lib/api/performance";

// Sales Pressure Engine (final round, Task 1/8) — same red/green framing
// the prompt's own example asks for ("Você está perdendo para o time" /
// "Você é o líder"), plus the two milder states compute_user_pressure_
// state() (team_performance.py) can also return.
const PRESSURE_STYLE: Record<PressureStateValue, { border: string; bg: string; text: string }> = {
  leader: { border: "border-success/40", bg: "bg-success/10", text: "text-success" },
  neutral: { border: "border-border", bg: "bg-muted/30", text: "text-muted-foreground" },
  at_risk: { border: "border-warning/40", bg: "bg-warning/10", text: "text-warning" },
  underperforming: { border: "border-destructive/40", bg: "bg-destructive/10", text: "text-destructive" },
};

const PRESSURE_HEADLINE: Record<PressureStateValue, string> = {
  leader: "Você é o líder",
  neutral: "Desempenho estável",
  at_risk: "Você está perdendo para o time",
  underperforming: "Você está perdendo para o time",
};

/** Sales Pressure Engine's own frontend surface (final round, Task 1/8) —
 * GET /performance/pressure-state's own {state, message}, rendered as a
 * banner the "human control" layer intends to actually be seen: red for
 * pressure (at_risk/underperforming), green for leader, neutral otherwise.
 * Omitted entirely (not rendered as a blank/neutral card) only while the
 * query hasn't resolved yet — "neutral" itself IS a real, renderable
 * state (a calm one), not a loading placeholder. */
export function PressureBanner({ pressureState }: { pressureState?: PressureState | null }) {
  if (!pressureState) return null;
  const style = PRESSURE_STYLE[pressureState.state];

  return (
    <Card className={`${style.border} ${style.bg}`}>
      <CardContent className="flex items-center justify-between gap-3 p-4">
        <div>
          <p className={`text-sm font-bold ${style.text}`}>
            {PRESSURE_HEADLINE[pressureState.state]}
          </p>
          <p className="text-xs text-muted-foreground">{pressureState.message}</p>
        </div>
        {pressureState.state === "leader" && <span className="text-2xl">🏆</span>}
        {(pressureState.state === "at_risk" || pressureState.state === "underperforming") && (
          <span className="text-2xl">🚨</span>
        )}
      </CardContent>
    </Card>
  );
}
