"use client";

import { Settings } from "lucide-react";

import { PageContainer } from "@/components/layout/page-container";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

function handleResetData() {
  const confirmed = window.confirm(
    "This will clear all locally saved leads and reload the page. Continue?"
  );
  if (!confirmed) return;

  // Scoped removeItem, not localStorage.clear() — a blanket clear would also
  // wipe nexara_token (src/lib/auth/token.ts) and silently log the user out,
  // which isn't what "reset demo data" should do.
  window.localStorage.removeItem("nexara-leads");
  window.location.reload();
}

export default function SettingsPage() {
  return (
    <PageContainer title="Configurações" subtitle="Preferências da conta e da organização.">
      <div className="space-y-4">
        <EmptyState
          icon={Settings}
          title="Nada para configurar ainda"
          description="As opções de conta e organização vão aparecer aqui em breve."
        />

        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm font-medium text-foreground">Reset all data</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Clears locally saved leads and reloads the page. This does not affect your account.
          </p>
          <Button variant="destructive" size="sm" className="mt-3" onClick={handleResetData}>
            Reset all data
          </Button>
        </div>
      </div>
    </PageContainer>
  );
}
