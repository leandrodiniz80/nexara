"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ActionQueuePanel } from "@/components/dashboard/action-queue-panel";
import { BusinessIntelligence } from "@/components/dashboard/business-intelligence";
import { CommandCenter } from "@/components/dashboard/command-center";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";
import { EnforcementOverlay } from "@/components/dashboard/enforcement-overlay";
import { ExecutiveDashboard } from "@/components/dashboard/executive-dashboard";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { LeadsMetricsGrid } from "@/components/dashboard/leads-metrics-grid";
import { LearningPanel } from "@/components/dashboard/learning-panel";
import { NeedsAttention } from "@/components/dashboard/needs-attention";
import { PerformancePanel } from "@/components/dashboard/performance-panel";
import { PipelineBar } from "@/components/dashboard/pipeline-bar";
import { PressureBanner } from "@/components/dashboard/pressure-banner";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { RevenuePanel } from "@/components/dashboard/revenue-panel";
import { TeamLeaderboard } from "@/components/dashboard/team-leaderboard";
import { TodaysFocus } from "@/components/dashboard/todays-focus";
import { UpcomingTasks } from "@/components/dashboard/upcoming-tasks";
import { LeadDetailsModal } from "@/components/leads/lead-details-modal";
import { PageContainer } from "@/components/layout/page-container";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useMinimumLoadingDelay } from "@/hooks/use-minimum-loading-delay";
import { getBusinessOverview } from "@/lib/api/billing";
import { ApiClientError } from "@/lib/api/client";
import {
  getAdaptiveWeights,
  getAggressionLevel,
  getExecInsight,
  getGlobalStrategy,
  getRevenueLeaks,
} from "@/lib/api/intelligence";
import { getLeaderboard, getPressureState, getTeamSummary } from "@/lib/api/performance";
import { getRevenueForecast, getRevenuePerformanceTrend, getRevenueSummary } from "@/lib/api/revenue";
import {
  completeLeadTask,
  executeLeadAction,
  getLeadInsights,
  getLeadMetrics,
  getLeads,
  getLeadsActivityFeed,
  getLeadsNeedingAttention,
  getLeadsPriority,
  getLeadTasks,
  updateLeadStatus,
  type Lead,
  type LeadExecutableAction,
  type LeadStatus,
} from "@/lib/api/leads";
import {
  completeAndNext,
  getActionQueue,
  getEnforcementState,
  getWorkdayNext,
  getWorkdayPerformance,
  getWorkdaySummary,
  getWorkdayTarget,
} from "@/lib/api/workday";
import { useAuth } from "@/lib/auth/auth-context";
import { MOCK_BUSINESS_OVERVIEW } from "@/lib/mocks/business-overview";

export default function DashboardPage() {
  const { isAuthenticated, user } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [detailsLead, setDetailsLead] = useState<Lead | null>(null);
  const [isWorkdayMode, setIsWorkdayMode] = useState(false);
  const [isCommandMode, setIsCommandMode] = useState(false);
  const [workdayStats, setWorkdayStats] = useState<{
    tasksCompletedToday: number;
    streakDays: number;
  } | null>(null);

  const {
    data: overview,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["billing-overview"],
    queryFn: getBusinessOverview,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: leadsMetrics } = useQuery({
    queryKey: ["leads-metrics"],
    queryFn: getLeadMetrics,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: activityFeed } = useQuery({
    queryKey: ["leads-activity"],
    queryFn: getLeadsActivityFeed,
    enabled: isAuthenticated,
    retry: false,
    // No websocket yet — a light 45s poll keeps "what just happened" from
    // going stale while someone's sitting on the dashboard.
    refetchInterval: 45000,
  });

  const { data: leadsNeedingAttention } = useQuery({
    queryKey: ["leads-attention"],
    queryFn: getLeadsNeedingAttention,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: leadTasks } = useQuery({
    queryKey: ["leads-tasks"],
    queryFn: getLeadTasks,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: priorityLeads } = useQuery({
    queryKey: ["leads-priority"],
    queryFn: getLeadsPriority,
    enabled: isAuthenticated,
    retry: false,
    // Same rationale as leads-activity above: "who needs me today" drifts
    // out of date the longer this stays open without a refresh.
    refetchInterval: 45000,
  });

  const { data: workdaySummary } = useQuery({
    queryKey: ["workday-summary"],
    queryFn: getWorkdaySummary,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 45000,
  });

  // Adaptive Intelligence round (Task 8) — Command Center's own three new
  // notices. adaptiveWeights/execInsight are independent, low-frequency
  // reads (no need for activityFeed's own 45s poll rhythm); hasRecentReassignments
  // is derived from activityFeed above, already fetched for Recent Activity.
  const { data: adaptiveWeights } = useQuery({
    queryKey: ["intelligence-adaptive-weights"],
    queryFn: getAdaptiveWeights,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: execInsight } = useQuery({
    queryKey: ["intelligence-exec-insight"],
    queryFn: getExecInsight,
    enabled: isAuthenticated,
    retry: false,
  });

  // Final round (Task 9) — the same low-frequency read rhythm as
  // adaptiveWeights/execInsight above.
  const { data: aggressionState } = useQuery({
    queryKey: ["intelligence-aggression-level"],
    queryFn: getAggressionLevel,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: globalStrategy } = useQuery({
    queryKey: ["intelligence-global-strategy"],
    queryFn: getGlobalStrategy,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: revenueLeaks } = useQuery({
    queryKey: ["intelligence-revenue-leaks"],
    queryFn: getRevenueLeaks,
    enabled: isAuthenticated,
    retry: false,
  });

  // Sales Pressure Engine (final round, Task 1/8) — the calling user's
  // own behavioral-control classification, for the Pressure Banner.
  const { data: pressureState } = useQuery({
    queryKey: ["performance-pressure-state"],
    queryFn: getPressureState,
    enabled: isAuthenticated,
    retry: false,
  });

  const hasRecentReassignments = activityFeed?.some((entry) => entry.type === "lead_reassigned") ?? false;

  // Execution-engine round — full leads, so the mandatory-lead button and
  // each action-queue row's own button can resolve an id into a full Lead
  // to open in the details modal, without a per-click fetch.
  const { data: leads } = useQuery({
    queryKey: ["leads"],
    queryFn: getLeads,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: actionQueue } = useQuery({
    queryKey: ["action-queue"],
    queryFn: getActionQueue,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 45000,
  });

  // Autonomous-sales-OS round — the hard-enforcement gate. Polled tighter
  // than the other dashboard queries (20s, not 45s): this one can put up a
  // fullscreen block, so it needs to notice a newly-mandatory lead (or the
  // block clearing) sooner than a routine dashboard refresh would.
  const { data: enforcementState } = useQuery({
    queryKey: ["enforcement-state"],
    queryFn: getEnforcementState,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 20000,
  });

  const { data: revenueForecast } = useQuery({
    queryKey: ["revenue-forecast"],
    queryFn: getRevenueForecast,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 45000,
  });

  const { data: workdayTarget } = useQuery({
    queryKey: ["workday-target"],
    queryFn: getWorkdayTarget,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 45000,
  });

  // Multi-user revenue-war round — the leaderboard's own read also fires
  // maybe_notify_underperformance() server-side (see that endpoint's own
  // docstring), so this poll doubles as the pressure system's trigger.
  const { data: leaderboard } = useQuery({
    queryKey: ["performance-leaderboard"],
    queryFn: getLeaderboard,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 45000,
  });

  const { data: teamSummary } = useQuery({
    queryKey: ["performance-team-summary"],
    queryFn: getTeamSummary,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 45000,
  });

  function openLeadById(leadId: string) {
    const lead = leads?.find((item) => item.id === leadId);
    if (lead) {
      setIsWorkdayMode(false);
      setIsCommandMode(false);
      setDetailsLead(lead);
    }
  }

  // Accountability layer's own snapshot — a "failing" read also fires a
  // persistent notification server-side (deduped within 6h), so this is a
  // deliberate real read, same 45s cadence as the other dashboard polls.
  const { data: workdayPerformance } = useQuery({
    queryKey: ["workday-performance"],
    queryFn: getWorkdayPerformance,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 45000,
  });

  // Feedback-loop round's Learning Panel — no polling (org-wide learned
  // patterns shift slowly), just invalidated below wherever a lead is
  // actually won or lost.
  const { data: conversionInsights } = useQuery({
    queryKey: ["leads-insights"],
    queryFn: getLeadInsights,
    enabled: isAuthenticated,
    retry: false,
  });

  const { data: revenueSummary } = useQuery({
    queryKey: ["revenue-summary"],
    queryFn: getRevenueSummary,
    enabled: isAuthenticated,
    retry: false,
    refetchInterval: 45000,
  });

  // Last 7 days — doesn't move within a session the way the other polled
  // queries do, so no refetchInterval; still invalidated below wherever a
  // status change or task completion could shift it.
  const { data: revenueTrend } = useQuery({
    queryKey: ["revenue-trend"],
    queryFn: getRevenuePerformanceTrend,
    enabled: isAuthenticated,
    retry: false,
  });

  // "Começar meu dia": fetches the one lead to work on right now, marks it
  // in_focus server-side, and opens its modal. Completing that lead's task
  // (see the modal's onTaskCompleted below) calls this again automatically
  // — the continuous "finish one, get the next" flow — until the queue is
  // empty. isWorkdayMode gates that auto-continue: opening a lead any other
  // way (e.g. Today's Focus card's own View button) never chains into it.
  const workdayNextMutation = useMutation({
    mutationFn: getWorkdayNext,
    onSuccess: (result) => {
      setWorkdayStats({
        tasksCompletedToday: result.tasksCompletedToday,
        streakDays: result.streakDays,
      });
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      if (result.lead) {
        setIsWorkdayMode(true);
        setDetailsLead(result.lead);
      } else {
        setIsWorkdayMode(false);
        showToast("You're all caught up — nothing left to work on right now.");
      }
    },
  });

  // Command Center's "Começar agora": same entry point as "Começar meu dia"
  // (GET /workday/next finds the one lead to start with) but flags
  // isCommandMode instead of isWorkdayMode, so the modal's completion flow
  // below routes through completeAndNextMutation (get_next_actionable_lead's
  // overdue -> due-today -> future -> no-action ranking) instead of another
  // GET /workday/next round-trip per step.
  const commandStartMutation = useMutation({
    mutationFn: getWorkdayNext,
    onSuccess: (result) => {
      setWorkdayStats({
        tasksCompletedToday: result.tasksCompletedToday,
        streakDays: result.streakDays,
      });
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      if (result.lead) {
        setIsCommandMode(true);
        setIsWorkdayMode(false);
        setDetailsLead(result.lead);
      } else {
        showToast("Você já está em dia — nada pendente agora.");
      }
    },
  });

  // The Command Center's own continuous-flow step: completes the lead
  // currently open in the modal and, in the same request, gets back
  // whichever lead is most worth working on next — see
  // completeTaskOverride on the modal below for how this replaces its
  // default plain completeLeadTask() call while isCommandMode is on.
  const completeAndNextMutation = useMutation({
    mutationFn: (leadId: string) => completeAndNext(leadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      queryClient.invalidateQueries({ queryKey: ["leads-attention"] });
      queryClient.invalidateQueries({ queryKey: ["leads-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["leads-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
      queryClient.invalidateQueries({ queryKey: ["workday-summary"] });
      queryClient.invalidateQueries({ queryKey: ["workday-performance"] });
      queryClient.invalidateQueries({ queryKey: ["revenue-summary"] });
    },
  });

  // Direct "Marcar como feito" from the dashboard cards (Today's Focus,
  // Needs Attention) — no modal round-trip. Strips the completed lead out
  // of the priority/attention/tasks caches immediately (no full-page
  // reload, no waiting on the next poll), then invalidates the other lists
  // it can affect (score/updated_at changed) in the background.
  const completeTaskMutation = useMutation({
    mutationFn: (id: string) => completeLeadTask(id),
    onSuccess: (_result, id) => {
      const withoutLead = (leads: Lead[] | undefined) => leads?.filter((lead) => lead.id !== id);
      queryClient.setQueryData<Lead[]>(["leads-priority"], withoutLead);
      queryClient.setQueryData<Lead[]>(["leads-attention"], withoutLead);
      queryClient.setQueryData<Lead[]>(["leads-tasks"], withoutLead);
      queryClient.invalidateQueries({ queryKey: ["leads-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["leads-activity"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["workday-summary"] });
      queryClient.invalidateQueries({ queryKey: ["workday-performance"] });
      queryClient.invalidateQueries({ queryKey: ["revenue-summary"] });
      showToast("Task completed");
    },
  });

  // Autonomous-sales-OS round — the enforcement overlay's own "execute"
  // button. Executes requiredAction, then best-effort completes that
  // lead's pending task too (swallowed if there isn't one — a call_now/
  // schedule_meeting requirement can be mandatory purely because the
  // underlying task is overdue, and execute-action alone doesn't clear
  // next_action_due_at the way completing the task does; without this,
  // the overlay could reappear for the same lead immediately after
  // "executing" it).
  const enforcementExecuteMutation = useMutation({
    mutationFn: async ({ leadId, action }: { leadId: string; action: LeadExecutableAction }) => {
      await executeLeadAction(leadId, action);
      try {
        await completeLeadTask(leadId);
      } catch {
        // No pending task to complete — the action itself still went
        // through, so this is not a failure.
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["enforcement-state"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      queryClient.invalidateQueries({ queryKey: ["action-queue"] });
      queryClient.invalidateQueries({ queryKey: ["workday-summary"] });
      queryClient.invalidateQueries({ queryKey: ["workday-target"] });
      showToast("Ação executada.");
    },
    onError: () => {
      showToast("Não foi possível executar a ação automaticamente. Abra o lead para tratar manualmente.");
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status, reason }: { id: string; status: LeadStatus; reason?: string }) =>
      updateLeadStatus(id, status, reason),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      queryClient.invalidateQueries({ queryKey: ["leads-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["leads-attention"] });
      queryClient.invalidateQueries({ queryKey: ["leads-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["revenue-summary"] });
      queryClient.invalidateQueries({ queryKey: ["revenue-trend"] });
      // A won/lost transition changes what compute_conversion_insights()
      // (scoring.py) mines from, so the Learning Panel's own read goes
      // stale the moment this one does.
      if (result.lead.status === "converted" || result.lead.status === "lost") {
        queryClient.invalidateQueries({ queryKey: ["leads-insights"] });
      }
      result.notifications.forEach((message) => showToast(message));
    },
  });

  const showSkeleton = useMinimumLoadingDelay(isLoading, 400);

  // Only a real auth failure blocks the dashboard. Any other failure
  // (timeout, 500, network) falls back to sample data instead of a dead
  // screen — see lib/mocks/business-overview.ts for why that's never silent.
  const authErrorMessage =
    error instanceof ApiClientError && error.status === 403
      ? "Your account doesn't have permission to view the Business Overview."
      : error instanceof ApiClientError && error.status === 401
        ? "Your session expired. Please sign in again."
        : null;
  const isAuthError = authErrorMessage !== null;
  const isUsingMock = isError && !isAuthError;
  const displayOverview = overview ?? (isUsingMock ? MOCK_BUSINESS_OVERVIEW : undefined);

  return (
    <>
      <PageContainer
        title="Business Overview"
        subtitle="Executive summary, updated in real time"
        actions={
          <>
            {isUsingMock && <Badge variant="warning">Sample data</Badge>}
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
              {isFetching ? "Refreshing…" : "Refresh Data"}
            </Button>
          </>
        }
      >
        {leadsMetrics && (
          <div className="space-y-4">
            <ExecutiveDashboard
              forecast={revenueForecast}
              target={workdayTarget}
              performance={workdayPerformance}
              summary={workdaySummary}
            />

            {leaderboard && (
              <TeamLeaderboard
                leaderboard={leaderboard}
                teamSummary={teamSummary}
                currentUserEmail={user?.email}
              />
            )}

            {revenueSummary && (
              <RevenuePanel summary={revenueSummary} trend={revenueTrend ?? []} />
            )}

            <PressureBanner pressureState={pressureState} />

            {workdaySummary && (
              <CommandCenter
                summary={workdaySummary}
                performance={workdayPerformance}
                tasksCompletedToday={workdayStats?.tasksCompletedToday ?? 0}
                onStart={() => commandStartMutation.mutate()}
                isStarting={commandStartMutation.isPending}
                onOpenMandatoryLead={openLeadById}
                execInsight={execInsight}
                adaptiveWeights={adaptiveWeights}
                hasRecentReassignments={hasRecentReassignments}
                aggressionLevel={aggressionState?.level}
                revenueMode={aggressionState?.revenueMode}
                globalStrategy={globalStrategy ?? undefined}
                revenueLeakValue={revenueLeaks?.totalLeakValue}
              />
            )}

            {actionQueue && <ActionQueuePanel items={actionQueue} onOpenLead={openLeadById} />}

            {workdayPerformance && <PerformancePanel performance={workdayPerformance} />}

            {conversionInsights && <LearningPanel insights={conversionInsights} />}

            <div className="flex flex-col items-start gap-2 rounded-lg border border-primary/30 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Ready to focus?</p>
                <p className="text-xs text-muted-foreground">
                  We&apos;ll line up one lead at a time — worst-off first.
                </p>
              </div>
              <div className="flex items-center gap-3">
                {workdayStats && (
                  <span className="text-xs text-muted-foreground">
                    {workdayStats.tasksCompletedToday} resolved today
                    {workdayStats.streakDays > 1 ? ` · ${workdayStats.streakDays}-day streak` : ""}
                  </span>
                )}
                <Button
                  size="lg"
                  onClick={() => workdayNextMutation.mutate()}
                  disabled={workdayNextMutation.isPending}
                >
                  {workdayNextMutation.isPending ? "Finding your next lead…" : "Começar meu dia"}
                </Button>
              </div>
            </div>

            {priorityLeads && (
              <TodaysFocus
                leads={priorityLeads}
                onOpenDetails={(lead) => {
                  // Opened via the card's own View button, not the workday
                  // flow — never chains into an auto-continue on completion.
                  setIsWorkdayMode(false);
                  setDetailsLead(lead);
                }}
                onCompleteTask={(lead) => completeTaskMutation.mutate(lead.id)}
                completingLeadId={completeTaskMutation.variables}
              />
            )}
            <LeadsMetricsGrid metrics={leadsMetrics} />
            <PipelineBar metrics={leadsMetrics} />
            {leadsNeedingAttention && (
              <NeedsAttention
                leads={leadsNeedingAttention}
                onOpenDetails={(lead) => {
                  setIsWorkdayMode(false);
                  setDetailsLead(lead);
                }}
                onCompleteTask={(lead) => completeTaskMutation.mutate(lead.id)}
                completingLeadId={completeTaskMutation.variables}
              />
            )}
            {leadTasks && <UpcomingTasks leads={leadTasks} />}
            {activityFeed && <RecentActivity entries={activityFeed} />}
          </div>
        )}

        {showSkeleton ? (
          <DashboardSkeleton />
        ) : isAuthError ? (
          <div className="flex flex-col items-center justify-center gap-3 p-16 text-center">
            <p className="text-sm font-medium text-foreground">{authErrorMessage}</p>
          </div>
        ) : displayOverview ? (
          <>
            <KpiGrid overview={displayOverview} />
            <BusinessIntelligence overview={displayOverview} />
          </>
        ) : null}
      </PageContainer>

      <LeadDetailsModal
        lead={detailsLead}
        onClose={() => {
          setDetailsLead(null);
          setIsWorkdayMode(false);
          setIsCommandMode(false);
        }}
        onMove={(status, reason) => {
          if (detailsLead && detailsLead.status !== status) {
            updateStatusMutation.mutate({ id: detailsLead.id, status, reason });
          }
          setDetailsLead(null);
          setIsWorkdayMode(false);
          setIsCommandMode(false);
        }}
        onTaskCompleted={
          isCommandMode
            ? (nextLead) => {
                if (nextLead) {
                  setDetailsLead(nextLead);
                  setWorkdayStats((prev) => ({
                    tasksCompletedToday: (prev?.tasksCompletedToday ?? 0) + 1,
                    streakDays: prev?.streakDays ?? 0,
                  }));
                } else {
                  setIsCommandMode(false);
                  setDetailsLead(null);
                  showToast("Dia concluído — não há mais leads para trabalhar agora.");
                }
              }
            : isWorkdayMode
              ? () => workdayNextMutation.mutate()
              : undefined
        }
        workdayStats={isWorkdayMode || isCommandMode ? (workdayStats ?? undefined) : undefined}
        completeTaskOverride={
          isCommandMode
            ? async (leadId) => {
                const result = await completeAndNextMutation.mutateAsync(leadId);
                return { lead: result.completedLead, nextLead: result.nextLead };
              }
            : undefined
        }
      />

      {/* Stepped aside (not rendered) while the user has explicitly opened
          the mandatory lead's own modal via "Abrir lead" below — both use
          z-50, and the modal needs to actually be reachable, not hidden
          behind this. Reappears the moment that modal closes if the lead
          is still mandatory. */}
      {enforcementState && detailsLead?.id !== enforcementState.leadId && (
        <EnforcementOverlay
          state={enforcementState}
          isExecuting={enforcementExecuteMutation.isPending}
          onExecute={() => {
            if (!enforcementState.leadId || !enforcementState.requiredAction) return;
            enforcementExecuteMutation.mutate({
              leadId: enforcementState.leadId,
              action: enforcementState.requiredAction as LeadExecutableAction,
            });
          }}
          onOpenLead={() => {
            if (enforcementState.leadId) openLeadById(enforcementState.leadId);
          }}
        />
      )}
    </>
  );
}
