"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Power, Zap } from "lucide-react";

import { PageContainer } from "@/components/layout/page-container";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getAutomations, toggleAutomation, type Automation } from "@/lib/api/automations";

export default function AutomationsPage() {
  const queryClient = useQueryClient();

  const { data: automations = [], isLoading } = useQuery({
    queryKey: ["automations"],
    queryFn: getAutomations,
    retry: false,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      toggleAutomation(id, active),
    onSuccess: (updated) => {
      queryClient.setQueryData<Automation[]>(["automations"], (prev) =>
        (prev ?? []).map((automation) => (automation.id === updated.id ? updated : automation))
      );
    },
  });

  return (
    <PageContainer
      title="Automações"
      subtitle="Configure fluxos automáticos de prospecção e follow-up."
    >
      {isLoading ? (
        <div className="space-y-3">
          {[0, 1].map((index) => (
            <div key={index} className="h-20 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {automations.map((automation) => (
            <div
              key={automation.id}
              className="flex items-center justify-between rounded-lg border border-border bg-card p-4"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted">
                  <Zap className="h-4 w-4 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{automation.name}</p>
                  <p className="text-xs capitalize text-muted-foreground">
                    {automation.trigger_from
                      ? `${automation.trigger_from} → ${automation.trigger_to}`
                      : automation.trigger_to}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant={automation.active ? "success" : "outline"}>
                  {automation.active ? "Active" : "Inactive"}
                </Badge>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={toggleMutation.isPending}
                  onClick={() =>
                    toggleMutation.mutate({ id: automation.id, active: !automation.active })
                  }
                >
                  <Power className="mr-2 h-4 w-4" />
                  {automation.active ? "Turn off" : "Turn on"}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
