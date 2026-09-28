import { memo } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { formatBRL } from "@/components/console/format-brl";
import type { ConsoleMoney } from "@/lib/api/system";

/** The console's headline number — how much revenue is reachable today,
 * and how much is already slipping away. One glance, no scrolling.
 * Green/red are semantic (gain vs. risk), not the accent hue — primary
 * stays reserved for actions, per the app's own color system. */
export const MoneyBlock = memo(function MoneyBlock({ money }: { money: ConsoleMoney }) {
  return (
    <Card className="border-2 border-success/30 bg-gradient-to-br from-success/[0.07] to-transparent shadow-md">
      <CardContent className="flex flex-col items-center gap-8 py-12 text-center sm:flex-row sm:justify-around sm:gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Você pode faturar isso hoje
          </p>
          <p className="mt-2 text-4xl font-extrabold tabular-nums tracking-tight text-success sm:text-6xl">
            {formatBRL(money.todayPossible)}
          </p>
        </div>

        <div className="h-px w-20 bg-border sm:h-20 sm:w-px" />

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Você está perdendo isso agora
          </p>
          <p className="mt-2 text-3xl font-bold tabular-nums tracking-tight text-destructive sm:text-4xl">
            {formatBRL(money.atRisk)}
          </p>
        </div>
      </CardContent>
    </Card>
  );
});
