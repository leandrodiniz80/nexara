import { memo } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatBRL } from "@/components/console/format-brl";
import { cn } from "@/lib/utils/cn";

/** The single instruction telling the owner what to do right now — the
 * most visually dominant element on the screen after the money itself.
 * Renders as three short, fast-reading lines when there's a real
 * shortfall to name (money.gap — compute_revenue_gap()'s own
 * "pressure-facing" figure, backend docstring), falling back to the plain
 * compute_main_action() sentence when there isn't one (gap <= 0), since
 * "you'll lose R$0" isn't a real warning. Text sizes step down below the
 * `sm` breakpoint so the loss figure never wraps awkwardly on a phone. */
export const MainAction = memo(function MainAction({
  mainAction,
  moneyGap,
  executionBlocked,
  onExecute,
  isExecuting,
  disabled,
  targetLeadName,
}: {
  mainAction: string;
  moneyGap: number;
  executionBlocked: boolean;
  onExecute: () => void;
  isExecuting: boolean;
  disabled: boolean;
  targetLeadName: string | null;
}) {
  return (
    <Card
      className={cn("border-2", executionBlocked ? "border-destructive/50" : "border-primary/40")}
    >
      <CardContent className="flex flex-col items-center gap-8 py-10 text-center">
        {moneyGap > 0 ? (
          <div className="space-y-2">
            <p className="text-base font-medium leading-snug text-muted-foreground sm:text-lg">
              Você vai perder
            </p>
            <p className="text-3xl font-extrabold tabular-nums leading-tight tracking-tight text-destructive sm:text-5xl">
              {formatBRL(moneyGap)}
            </p>
            <p className="text-base font-medium leading-snug text-muted-foreground sm:text-lg">
              se não fizer isso hoje:
            </p>
            <p className="max-w-xl text-balance text-xl font-bold leading-snug text-foreground sm:text-2xl">
              {mainAction}
            </p>
          </div>
        ) : (
          <p className="max-w-xl text-balance text-2xl font-bold leading-snug text-foreground sm:text-3xl">
            {mainAction}
          </p>
        )}

        <Button
          size="lg"
          variant={executionBlocked ? "destructive" : "default"}
          className="w-full max-w-md py-8 text-lg font-bold tracking-wide hover:scale-[1.02] active:brightness-90"
          onClick={onExecute}
          disabled={disabled || isExecuting}
        >
          {isExecuting ? "Executando…" : "EXECUTAR AGORA"}
        </Button>
        {targetLeadName && (
          <p className="-mt-5 text-sm text-muted-foreground">
            Executa a ação recomendada para <span className="font-medium">{targetLeadName}</span>
          </p>
        )}
      </CardContent>
    </Card>
  );
});
