"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { LeaderboardEntry, TeamSummary } from "@/lib/api/performance";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

function formatMinutes(minutes: number | null): string {
  if (minutes === null) return "—";
  if (minutes < 60) return `${Math.round(minutes)}min`;
  return `${(minutes / 60).toFixed(1)}h`;
}

// Gamification round's own badge labels (Task 4, backend) — same three
// strings compute_user_performance() (team_performance.py) ever produces,
// each with its own emoji for a scannable row.
const BADGE_LABEL: Record<string, string> = {
  Closer: "🎯 Closer",
  "Speed Hunter": "⚡ Speed Hunter",
  "Hot Pipeline": "🔥 Hot Pipeline",
};

const TOP_N = 5;

/** Multi-user revenue-war round's "🔥 Ranking do Time" (Task 7) — the top
 * 5 of the leaderboard, each row showing revenue/response rate/badges/
 * commission estimate, plus "🏆 Top Performer"/"⚠️ Needs Attention"
 * callouts and (Task 8) a pressure banner for whichever row matches the
 * current logged-in user (currentUserEmail): green if they're #1, red if
 * they're last — omitted entirely for anyone in between, and whenever
 * there are fewer than two team members (no meaningful "leading"/"behind"
 * with only one combatant). */
export function TeamLeaderboard({
  leaderboard,
  teamSummary,
  currentUserEmail,
}: {
  leaderboard: LeaderboardEntry[];
  teamSummary?: TeamSummary;
  currentUserEmail?: string | null;
}) {
  if (leaderboard.length === 0) return null;

  const topPerformer = leaderboard[0];
  const worstPerformer = leaderboard[leaderboard.length - 1];
  const isCurrentUserTop = leaderboard.length > 1 && currentUserEmail === topPerformer.userId;
  const isCurrentUserLast = leaderboard.length > 1 && currentUserEmail === worstPerformer.userId;

  return (
    <div className="space-y-3">
      {isCurrentUserTop && (
        <div className="rounded-lg border border-success bg-success/15 p-3 text-center text-sm font-bold text-success">
          🏆 Você está liderando o time
        </div>
      )}
      {isCurrentUserLast && (
        <div className="rounded-lg border border-destructive bg-destructive/15 p-3 text-center text-sm font-bold text-destructive">
          🚨 Você precisa reagir agora
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Card className="border-success/30 bg-success/5">
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              🏆 Top Performer
            </p>
            <p className="mt-1 truncate text-lg font-bold text-success">
              {teamSummary?.topPerformerName ?? topPerformer.name}
            </p>
            <p className="text-xs text-muted-foreground">
              R$ {formatBRL(topPerformer.revenueConverted)} convertidos
            </p>
          </CardContent>
        </Card>

        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              ⚠️ Needs Attention
            </p>
            <p className="mt-1 truncate text-lg font-bold text-destructive">
              {teamSummary?.worstPerformerName ?? worstPerformer.name}
            </p>
            <p className="text-xs text-muted-foreground">
              R$ {formatBRL(worstPerformer.revenueConverted)} convertidos
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="border-primary/30">
        <CardHeader>
          <CardTitle className="text-foreground">🔥 Ranking do Time</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {leaderboard.slice(0, TOP_N).map((entry) => (
              <li
                key={entry.userId}
                className="flex flex-wrap items-center justify-between gap-2 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-foreground">
                    #{entry.position} {entry.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {entry.dealsClosed} fechados · {entry.responseRate.toFixed(0)}% resposta ·{" "}
                    {formatMinutes(entry.avgResponseTimeMinutes)} médio
                  </p>
                  {entry.badges.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {entry.badges.map((badge) => (
                        <Badge key={badge} variant="outline" className="text-[10px]">
                          {BADGE_LABEL[badge] ?? badge}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <p className="font-semibold text-success">
                    R$ {formatBRL(entry.revenueConverted)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    comissão R$ {formatBRL(entry.commissionEstimate)}
                  </p>
                  {/* Revenue Per User real-time (Elite round, Task 5) */}
                  <p className="text-[11px] text-muted-foreground">
                    hoje R$ {formatBRL(entry.revenueToday)} · semana R$ {formatBRL(entry.revenueThisWeek)}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    pipeline R$ {formatBRL(entry.pipelineValue)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
