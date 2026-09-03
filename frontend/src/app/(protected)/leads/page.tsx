"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { PageContainer } from "@/components/layout/page-container";
import { CreateLeadModal } from "@/components/leads/create-lead-modal";
import { LeadDetailsModal } from "@/components/leads/lead-details-modal";
import { LeadsKanban } from "@/components/leads/leads-kanban";
import { LeadsTable } from "@/components/leads/leads-table";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/lib/auth/auth-context";
import { ApiClientError } from "@/lib/api/client";
import { createLead, getLeads, updateLeadStatus, type Lead, type LeadStatus } from "@/lib/api/leads";
import { cn } from "@/lib/utils/cn";

const STATUS_FILTERS: { label: string; value: "all" | LeadStatus }[] = [
  { label: "Todos", value: "all" },
  { label: "Novos", value: "new" },
  { label: "Contatados", value: "contacted" },
  { label: "Convertidos", value: "converted" },
];

const VIEW_OPTIONS: { label: string; value: "table" | "kanban" }[] = [
  { label: "Table View", value: "table" },
  { label: "Pipeline View", value: "kanban" },
];

function LeadsSkeleton() {
  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {[0, 1, 2].map((column) => (
        <div
          key={column}
          className="w-72 shrink-0 space-y-2 rounded-lg border border-border bg-card/40 p-3"
        >
          <div className="h-4 w-24 animate-pulse rounded bg-muted" />
          <div className="h-16 animate-pulse rounded-md bg-muted" />
          <div className="h-16 animate-pulse rounded-md bg-muted" />
        </div>
      ))}
    </div>
  );
}

export default function LeadsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { logout } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [detailsLead, setDetailsLead] = useState<Lead | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | LeadStatus>("all");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"table" | "kanban">("table");
  const [highlightedLeadId, setHighlightedLeadId] = useState<string | null>(null);
  const listTopRef = useRef<HTMLDivElement>(null);
  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const {
    data: leads = [],
    isLoading: isLeadsLoading,
    isError: isLeadsError,
    error: leadsError,
  } = useQuery({
    queryKey: ["leads"],
    queryFn: getLeads,
    retry: false,
  });

  // A 401 here means the session that was valid when this page mounted
  // expired mid-visit (tokens have a 1h TTL server-side) — auto-logout
  // instead of leaving the user staring at a dead list.
  useEffect(() => {
    if (leadsError instanceof ApiClientError && leadsError.status === 401) {
      logout().finally(() => router.replace("/login"));
    }
  }, [leadsError, logout, router]);

  const createLeadMutation = useMutation({
    mutationFn: createLead,
    onSuccess: ({ lead: newLead, notifications }) => {
      queryClient.setQueryData<Lead[]>(["leads"], (prev) => [newLead, ...(prev ?? [])]);
      queryClient.invalidateQueries({ queryKey: ["leads-metrics"] });
      showToast("Lead created successfully");
      notifications.forEach((message) => showToast(message));

      listTopRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

      if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
      setHighlightedLeadId(newLead.id);
      highlightTimeoutRef.current = setTimeout(() => setHighlightedLeadId(null), 2000);
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: LeadStatus }) =>
      updateLeadStatus(id, status),
    onSuccess: (result) => {
      queryClient.setQueryData<Lead[]>(["leads"], (prev) =>
        (prev ?? []).map((lead) => (lead.id === result.lead.id ? result.lead : lead))
      );
      queryClient.invalidateQueries({ queryKey: ["leads-metrics"] });
      result.notifications.forEach((message) => showToast(message));
    },
  });

  useEffect(() => {
    return () => {
      if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
    };
  }, []);

  // Deep link from a notification ("clicar → abre lead"): ?lead=<id>, once
  // the list has loaded. router.replace strips the param right after so
  // this doesn't re-fire on the next unrelated re-render/refetch.
  useEffect(() => {
    const leadId = searchParams.get("lead");
    if (!leadId || leads.length === 0) return;

    const match = leads.find((lead) => lead.id === leadId);
    if (match) {
      setDetailsLead(match);
      router.replace("/leads");
    }
  }, [searchParams, leads, router]);

  const filteredLeads = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return leads.filter((lead) => {
      const matchesStatus = statusFilter === "all" || lead.status === statusFilter;
      const matchesQuery =
        normalizedQuery === "" ||
        lead.name.toLowerCase().includes(normalizedQuery) ||
        lead.email.toLowerCase().includes(normalizedQuery);

      return matchesStatus && matchesQuery;
    });
  }, [leads, statusFilter, query]);

  function handleMoveLead(id: string, status: LeadStatus) {
    const lead = leads.find((item) => item.id === id);
    if (!lead || lead.status === status) return;
    updateStatusMutation.mutate({ id, status });
  }

  const isAuthError = leadsError instanceof ApiClientError && leadsError.status === 401;
  const isForbidden = leadsError instanceof ApiClientError && leadsError.status === 403;

  return (
    <>
      <PageContainer
        title="Leads"
        subtitle="Acompanhe e qualifique oportunidades em um só lugar."
        actions={
          <>
            <div className="flex gap-1 rounded-md border border-border bg-card/40 p-1">
              {VIEW_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setView(option.value)}
                  className={cn(
                    "rounded-sm px-3 py-1.5 text-sm font-medium transition-colors duration-200",
                    view === option.value
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <Button onClick={() => setIsModalOpen(true)}>New Lead</Button>
          </>
        }
      >
        {isLeadsLoading || isAuthError ? (
          <LeadsSkeleton />
        ) : isForbidden ? (
          <div className="flex flex-col items-center justify-center gap-3 p-16 text-center">
            <p className="text-sm font-medium text-foreground">
              Your account doesn&apos;t have permission to view leads.
            </p>
          </div>
        ) : isLeadsError ? (
          <div className="flex flex-col items-center justify-center gap-3 p-16 text-center">
            <p className="text-sm font-medium text-foreground">We couldn&apos;t load your leads.</p>
            <p className="text-xs text-muted-foreground">
              {leadsError instanceof Error ? leadsError.message : "Please try again."}
            </p>
          </div>
        ) : leads.length === 0 ? (
          <EmptyState
            icon={Users}
            title="No leads yet"
            description="Start by creating your first lead"
            action={<Button onClick={() => setIsModalOpen(true)}>Create your first lead</Button>}
          />
        ) : (
          <div ref={listTopRef} className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap gap-1 rounded-md border border-border bg-card/40 p-1">
                {STATUS_FILTERS.map((filter) => (
                  <button
                    key={filter.value}
                    type="button"
                    onClick={() => setStatusFilter(filter.value)}
                    className={cn(
                      "rounded-sm px-3 py-1.5 text-sm font-medium transition-colors duration-200",
                      statusFilter === filter.value
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                    )}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search leads..."
                className="sm:w-64"
              />
            </div>

            {filteredLeads.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                No leads match your filters.
              </p>
            ) : view === "table" ? (
              <LeadsTable leads={filteredLeads} highlightedLeadId={highlightedLeadId} />
            ) : (
              <LeadsKanban
                leads={filteredLeads}
                onMove={handleMoveLead}
                onOpenDetails={setDetailsLead}
                highlightedLeadId={highlightedLeadId}
              />
            )}
          </div>
        )}
      </PageContainer>

      <CreateLeadModal
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onCreate={(data) => createLeadMutation.mutate(data)}
      />

      <LeadDetailsModal
        lead={detailsLead}
        onClose={() => setDetailsLead(null)}
        onMove={(status) => {
          if (detailsLead) handleMoveLead(detailsLead.id, status);
          setDetailsLead(null);
        }}
      />
    </>
  );
}
