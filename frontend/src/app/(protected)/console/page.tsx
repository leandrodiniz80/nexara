"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Sparkles } from "lucide-react";
import { useCallback } from "react";

import { AlertBlock } from "@/components/console/alert-block";
import { ExecutionPlan } from "@/components/console/execution-plan";
import { LeadCard } from "@/components/console/lead-card";
import { MainAction } from "@/components/console/main-action";
import { MoneyBlock } from "@/components/console/money-block";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";
import { PageContainer } from "@/components/layout/page-container";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { ApiClientError } from "@/lib/api/client";
import { getConsole, executeSystemAction, seedDemoData } from "@/lib/api/system";
import { useAuth } from "@/lib/auth/auth-context";

// Matches CommandCenter's own poll rhythm on /dashboard — fresh enough that
// "what to do now" never goes stale, without a refetch on every tab focus
// or remount in between polls.
const CONSOLE_POLL_MS = 45000;

export default function ConsolePage() {
  const { isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const {
    data: consoleData,
    isLoading,
    isFetching,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["system-console"],
    queryFn: getConsole,
    enabled: isAuthenticated,
    retry: false,
    staleTime: CONSOLE_POLL_MS,
    refetchInterval: CONSOLE_POLL_MS,
  });

  const executeMutation = useMutation({
    mutationFn: (leadId: string) => executeSystemAction(leadId),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["system-console"] });
      showToast(
        result.executed
          ? "Ação executada com sucesso."
          : "Não há nenhuma ação pendente para este lead agora."
      );
    },
    onError: () => {
      showToast("Não foi possível executar a ação. Tente novamente.");
    },
  });

  const demoSeedMutation = useMutation({
    mutationFn: seedDemoData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system-console"] });
      showToast("Oportunidades de demonstração geradas.");
    },
    onError: () => {
      showToast("Não foi possível gerar os dados de demonstração. Tente novamente.");
    },
  });

  const topPriorityLeadId = consoleData?.topPriorities[0]?.leadId ?? null;
  const executingLeadId = executeMutation.isPending ? executeMutation.variables : null;

  const handleExecuteMainAction = useCallback(() => {
    if (topPriorityLeadId && !executeMutation.isPending) {
      executeMutation.mutate(topPriorityLeadId);
    }
    // executeMutation.mutate is a stable reference from react-query; isPending
    // is read here only to avoid a double-submit race, not to resubscribe.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topPriorityLeadId, executeMutation.isPending]);

  const authErrorMessage =
    error instanceof ApiClientError && error.status === 403
      ? "Sua conta não tem permissão para ver o Command Center."
      : error instanceof ApiClientError && error.status === 401
        ? "Sua sessão expirou. Faça login novamente."
        : null;

  const hasNoOpportunities = consoleData !== undefined && consoleData.topPriorities.length === 0;
  const topThreeLeads = consoleData?.topPriorities.slice(0, 3) ?? [];

  return (
    <PageContainer
      title="Command Center"
      subtitle="Uma tela. Um número. Uma ação."
      actions={
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? "Atualizando…" : "Atualizar"}
        </Button>
      }
    >
      {isLoading ? (
        <DashboardSkeleton />
      ) : isError ? (
        <EmptyState
          icon={AlertCircle}
          title={authErrorMessage ? "Acesso indisponível" : "Não foi possível carregar o Command Center"}
          description={
            authErrorMessage ??
            "Houve um problema ao conectar com o servidor. Verifique sua conexão e tente novamente."
          }
          action={
            !authErrorMessage && (
              <Button onClick={() => refetch()} disabled={isFetching}>
                {isFetching ? "Tentando…" : "Tentar novamente"}
              </Button>
            )
          }
        />
      ) : !consoleData ? null : hasNoOpportunities ? (
        <EmptyState
          icon={Sparkles}
          title="Você ainda não tem oportunidades"
          description="Vamos gerar oportunidades reais para você agora"
          action={
            <Button onClick={() => demoSeedMutation.mutate()} disabled={demoSeedMutation.isPending}>
              {demoSeedMutation.isPending ? "Gerando…" : "Gerar minha primeira oportunidade"}
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          {/* execution_blocked outranks everything, including the money
              block — it's the one thing the owner must see first. Fixed
              order otherwise: money, the one action, the short plan, then
              exactly 3 leads. Never more than one clear next step. */}
          {consoleData.executionBlocked && (
            <AlertBlock variant="critical" message="Execução travada — você precisa fazer isso agora" />
          )}

          <MoneyBlock money={consoleData.money} />

          <MainAction
            mainAction={consoleData.mainAction}
            moneyGap={consoleData.money.gap}
            executionBlocked={consoleData.executionBlocked}
            disabled={!topPriorityLeadId}
            isExecuting={executeMutation.isPending}
            onExecute={handleExecuteMainAction}
          />

          {consoleData.consistencyWarning && (
            <AlertBlock
              variant="warning"
              message="O sistema detectou uma inconsistência interna nos dados — os números podem estar temporariamente desatualizados."
            />
          )}

          <ExecutionPlan focus={consoleData.focus} plan={consoleData.executionPlan} />

          <div className="space-y-2">
            <h2 className="text-sm font-medium text-muted-foreground">Top 3 oportunidades</h2>
            <div className="space-y-2">
              {topThreeLeads.map((priority) => (
                <LeadCard
                  key={priority.leadId}
                  priority={priority}
                  isExecuting={priority.leadId === executingLeadId}
                  isPrimaryTarget={priority.leadId === topPriorityLeadId}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
