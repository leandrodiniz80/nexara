import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ConversionInsights } from "@/lib/api/leads";

/** Dashboard's "learning layer" (feedback-loop round) — what's actually
 * converting for this org, mined from real outcomes by
 * compute_conversion_insights() (scoring.py), not a fixed rule. Each field
 * shows a neutral placeholder until there's enough real data (e.g. no lead
 * converted yet) rather than a misleading zero/empty look. Industry/company
 * size are shown exactly as enrichment_data stores them (e.g. "Technology",
 * "201-500") — same untranslated convention LeadIntelligence
 * (lead-details-modal.tsx) already uses for the same values, not a new
 * Portuguese label map invented just for this card. */
export function LearningPanel({ insights }: { insights: ConversionInsights }) {
  return (
    <Card className="border-primary/40 bg-primary/5">
      <CardHeader>
        <CardTitle className="text-foreground">O que está funcionando</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
          <div>
            <p className="text-lg font-semibold text-foreground">
              {insights.bestIndustry ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">Melhor segmento</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">
              {insights.bestCompanySize ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">Melhor porte</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-foreground">
              {insights.avgTimeToCloseDays !== null ? `${insights.avgTimeToCloseDays}d` : "—"}
            </p>
            <p className="text-xs text-muted-foreground">Tempo médio de fechamento</p>
          </div>
          <div>
            <p className="text-lg font-semibold text-destructive">
              {insights.topLossReason ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">Principal motivo de perda</p>
          </div>
        </div>
        {!insights.bestIndustry &&
          !insights.bestCompanySize &&
          insights.avgTimeToCloseDays === null &&
          !insights.topLossReason && (
            <p className="mt-3 text-xs text-muted-foreground">
              Ainda sem dados suficientes — feche ou perca alguns leads para o sistema começar a
              aprender.
            </p>
          )}
      </CardContent>
    </Card>
  );
}
