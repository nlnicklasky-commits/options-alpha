export function formatPrice(value: number | null | undefined): string {
  if (value == null) return "--";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return "--";
  return `${value.toFixed(1)}%`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null) return "--";
  return value.toLocaleString("en-US");
}

export function formatScore(value: number | null | undefined): string {
  if (value == null) return "--";
  return value.toFixed(1);
}

export function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-amber-400";
  return "text-rose-400";
}

export function scoreBgColor(score: number): string {
  if (score >= 80) return "bg-emerald-400/10 border-emerald-400/20";
  if (score >= 60) return "bg-amber-400/10 border-amber-400/20";
  return "bg-rose-400/10 border-rose-400/20";
}
