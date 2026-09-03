"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { BusinessIntelligence } from "@/components/dashboard/business-intelligence";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { LeadsMetricsGrid } from "@/components/dashboard/leads-metrics-grid";
import { NeedsAttention } from "@/components/dashboard/needs-attention";
import { PipelineBar } from "@/components/dashboard/pipeline-bar";
import { RecentActivity } from "@/components/dashboard/recent-activity";
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
  completeLeadTask,
  getLeadMetrics,
  getLeadsActivityFeed,
  getLeadsNeedingAttention,
  getLeadsPriority,
  getLeadTasks,
  updateLeadStatus,
  type Lead,
  type LeadStatus,
} from "@/lib/api/leads";
import { getWorkdayNext } from "@/lib/api/workday";
import { useAuth } from "@/lib/auth/auth-context";
import { MOCK_BUSINESS_OVERVIEW } from "@/lib/mocks/business-overview";

export default function DashboardPage() {
  const { isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [detailsLead, setDetailsLead] = useState<Lead | null>(null);
  const [isWorkdayMode, setIsWorkdayMode] = useState(false);
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
      showToast("Task completed");
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: LeadStatus }) =>
      updateLeadStatus(id, status),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["leads-priority"] });
      queryClient.invalidateQueries({ queryKey: ["leads-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["leads-attention"] });
      queryClient.invalidateQueries({ queryKey: ["leads-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
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
        }}
        onMove={(status) => {
          if (detailsLead && detailsLead.status !== status) {
            updateStatusMutation.mutate({ id: detailsLead.id, status });
          }
          setDetailsLead(null);
          setIsWorkdayMode(false);
        }}
        onTaskCompleted={isWorkdayMode ? () => workdayNextMutation.mutate() : undefined}
        workdayStats={isWorkdayMode ? (workdayStats ?? undefined) : undefined}
      />
    </>
  );
}
