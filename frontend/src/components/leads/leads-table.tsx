import { Badge } from "@/components/ui/badge";
import type { Lead, LeadStatus } from "@/lib/api/leads";
import { formatDate } from "@/lib/utils/format";

const STATUS_LABEL: Record<LeadStatus, string> = {
  new: "New",
  contacted: "Contacted",
  converted: "Converted",
};

const STATUS_BADGE: Record<LeadStatus, "secondary" | "warning" | "success"> = {
  new: "secondary",
  contacted: "warning",
  converted: "success",
};

export function LeadsTable({ leads }: { leads: Lead[] }) {
  const sorted = [...leads].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-medium">Name</th>
            <th className="px-4 py-3 font-medium">Email</th>
            <th className="px-4 py-3 font-medium">Phone</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sorted.map((lead) => (
            <tr key={lead.id} className="transition-colors hover:bg-accent/50">
              <td className="px-4 py-3 font-medium text-foreground">{lead.name}</td>
              <td className="px-4 py-3 text-muted-foreground">{lead.email}</td>
              <td className="px-4 py-3 text-muted-foreground">{lead.phone}</td>
              <td className="px-4 py-3">
                <Badge variant={STATUS_BADGE[lead.status]}>{STATUS_LABEL[lead.status]}</Badge>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{formatDate(lead.createdAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
