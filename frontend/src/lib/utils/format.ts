export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(new Date(value));
}

const RELATIVE_TIME_UNITS: { unit: Intl.RelativeTimeFormatUnit; seconds: number }[] = [
  { unit: "year", seconds: 31536000 },
  { unit: "month", seconds: 2592000 },
  { unit: "day", seconds: 86400 },
  { unit: "hour", seconds: 3600 },
  { unit: "minute", seconds: 60 },
];

/** "5 minutes ago" style — used by activity feeds where an exact date reads
 * as noise. Falls back to "just now" under a minute. */
export function formatRelativeTime(value: string): string {
  const diffSeconds = (Date.now() - new Date(value).getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat("en-US", { numeric: "auto" });

  for (const { unit, seconds } of RELATIVE_TIME_UNITS) {
    const amount = Math.floor(diffSeconds / seconds);
    if (amount >= 1) {
      return rtf.format(-amount, unit);
    }
  }
  return "just now";
}
