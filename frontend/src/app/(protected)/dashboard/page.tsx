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
  getLeadMetrics,
  getLeadsActivityFeed,
  getLeadsNeedingAttention,
  getLeadsPriority,
  getLeadTasks,
  updateLeadStatus,
  type Lead,
  type LeadStatus,
} from "@/lib/api/leads";
import { useAuth } from "@/lib/auth/auth-context";
import { MOCK_BUSINESS_OVERVIEW } from "@/lib/mocks/business-overview";

export default function DashboardPage() {
  const { isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [detailsLead, setDetailsLead] = useState<Lead | null>(null);

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
            {priorityLeads && (
              <TodaysFocus leads={priorityLeads} onOpenDetails={setDetailsLead} />
            )}
            <LeadsMetricsGrid metrics={leadsMetrics} />
            <PipelineBar metrics={leadsMetrics} />
            {leadsNeedingAttention && <NeedsAttention leads={leadsNeedingAttention} />}
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
        onClose={() => setDetailsLead(null)}
        onMove={(status) => {
          if (detailsLead && detailsLead.status !== status) {
            updateStatusMutation.mutate({ id: detailsLead.id, status });
          }
          setDetailsLead(null);
        }}
      />
    </>
  );
}
