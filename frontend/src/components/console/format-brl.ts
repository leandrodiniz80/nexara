/** Console-only formatter — the console's own copy (GET /system/console)
 * is entirely pt-BR, unlike the rest of the dashboard, so this stays local
 * to components/console instead of changing lib/utils/format.ts's
 * shared, en-US/USD formatCurrency() used everywhere else. */
export function formatBRL(value: number): string {
  const formatted = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(value);
  // Intl's own space between "R$" and the figure isn't guaranteed
  // non-breaking across engines — forced here so the biggest numbers on
  // the screen can never wrap between the symbol and the digits on a
  // narrow phone.
  return formatted.replace(" ", " ");
}
