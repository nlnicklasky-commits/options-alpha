"use client";

import { useState, useEffect } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatPrice, formatPercent } from "@/lib/format";
import type { RegimeData } from "@/lib/types";

export function MarketBar() {
  const [data, setData] = useState<RegimeData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<RegimeData>("/api/signals/regime")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="h-12 bg-zinc-900/50 border border-zinc-800 rounded-lg">
        <Skeleton className="h-full w-full bg-zinc-800" />
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const regimeColor =
    data.regime === "BULL"
      ? "text-emerald-400"
      : data.regime === "BEAR"
        ? "text-rose-400"
        : "text-amber-400";

  const regimeBg =
    data.regime === "BULL"
      ? "bg-emerald-500/10"
      : data.regime === "BEAR"
        ? "bg-rose-500/10"
        : "bg-amber-500/10";

  const timestamp = new Date().toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  return (
    <div className={`flex items-center gap-4 px-4 py-3 text-sm ${regimeBg} border border-zinc-800 rounded-lg`}>
      <span className={`font-semibold ${regimeColor}`}>
        {data.regime === "BULL" ? "🟢" : data.regime === "BEAR" ? "🔴" : "🟠"}{" "}
        {data.regime}
      </span>
      <span className="text-zinc-400">VIX: {formatPrice(data.vix)}</span>
      <span className="text-zinc-400">A/D: {data.breadth.advance_decline.toFixed(2)}</span>
      <span className="text-zinc-400">
        Above 200 SMA: {formatPercent(data.breadth.pct_above_200sma)}
      </span>
      <span className="text-zinc-400">Data: {timestamp}</span>
    </div>
  );
}
