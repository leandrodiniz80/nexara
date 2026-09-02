import { Megaphone } from "lucide-react";

import { PageContainer } from "@/components/layout/page-container";
import { EmptyState } from "@/components/ui/empty-state";

export default function CampaignsPage() {
  return (
    <PageContainer title="Campanhas" subtitle="Gerencie campanhas de prospecção e outreach.">
      <EmptyState
        icon={Megaphone}
        title="Nenhuma campanha criada"
        description="Crie sua primeira campanha para começar a prospectar."
      />
    </PageContainer>
  );
}
