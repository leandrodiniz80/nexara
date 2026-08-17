"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { BusinessIntelligence } from "@/components/dashboard/business-intelligence";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { Button } from "@/components/ui/button";
import { ApiClientError } from "@/lib/api/client";
import { getBusinessOverview } from "@/lib/api/billing";
import { useAuth } from "@/lib/auth/auth-context";

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();

  useEffect(() => {
    if (!isAuthLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthLoading, isAuthenticated, router]);

  const {
    data: overview,
    isLoading: isOverviewLoading,
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

  if (isAuthLoading || !isAuthenticated) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Loading Nexara…</p>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <DashboardSidebar />
      <div className="flex flex-1 flex-col">
        <DashboardHeader />
        <main className="flex-1 overflow-y-auto">
          {isOverviewLoading ? (
            <DashboardSkeleton />
          ) : isError ? (
            <div className="flex flex-col items-center justify-center gap-3 p-16 text-center">
              <p className="text-sm font-medium text-foreground">
                {error instanceof ApiClientError && error.status === 403
                  ? "Your account doesn't have permission to view the Business Overview."
                  : "We couldn't load the Business Overview."}
              </p>
              <p className="text-xs text-muted-foreground">
                {error instanceof Error ? error.message : "Please try again."}
              </p>
              <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
                {isFetching ? "Retrying…" : "Retry"}
              </Button>
            </div>
          ) : overview ? (
            <div className="space-y-6 p-6">
              <KpiGrid overview={overview} />
              <BusinessIntelligence overview={overview} />
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}
