"use client";

import { useQuery } from "@tanstack/react-query";

import { BusinessIntelligence } from "@/components/dashboard/business-intelligence";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { LeadsMetricsGrid } from "@/components/dashboard/leads-metrics-grid";
import { PipelineBar } from "@/components/dashboard/pipeline-bar";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { PageContainer } from "@/components/layout/page-container";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useMinimumLoadingDelay } from "@/hooks/use-minimum-loading-delay";
import { getAutomationsActivity } from "@/lib/api/automations";
import { getBusinessOverview } from "@/lib/api/billing";
import { ApiClientError } from "@/lib/api/client";
import { getLeadMetrics } from "@/lib/api/leads";
import { useAuth } from "@/lib/auth/auth-context";
import { MOCK_BUSINESS_OVERVIEW } from "@/lib/mocks/business-overview";

export default function DashboardPage() {
  const { isAuthenticated } = useAuth();

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

  const { data: automationsActivity } = useQuery({
    queryKey: ["automations-activity"],
    queryFn: getAutomationsActivity,
    enabled: isAuthenticated,
    retry: false,
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
          <LeadsMetricsGrid metrics={leadsMetrics} />
          <PipelineBar metrics={leadsMetrics} />
          {automationsActivity && <RecentActivity entries={automationsActivity} />}
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
  );
}
