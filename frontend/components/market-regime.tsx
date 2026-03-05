"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatPrice, formatPercent } from "@/lib/format";
import type { MarketRegime } from "@/lib/types";

interface RegimeData {
  regime: MarketRegime;
  vix: number;
  breadth: {
    advance_decline: number;
    pct_above_200sma: number;
    new_highs_lows: number;
  };
}

const regimeStyles: Record<MarketRegime, string> = {
  BULL: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  BEAR: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  CHOPPY: "bg-amber-500/10 text-amber-400 border-amber-500/20",
};

export function MarketRegimePanel() {
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
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-sm text-zinc-100">Market Regime</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-8 w-24 bg-zinc-800" />
          <Skeleton className="h-4 w-full bg-zinc-800" />
          <Skeleton className="h-4 w-full bg-zinc-800" />
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-sm text-zinc-100">Market Regime</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-zinc-500">Regime data unavailable</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardHeader>
        <CardTitle className="text-sm text-zinc-100">Market Regime</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Badge className={`text-sm ${regimeStyles[data.regime]}`}>
          {data.regime}
        </Badge>

        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-zinc-400">VIX</span>
            <span className={`font-mono ${data.vix > 25 ? "text-rose-400" : data.vix > 18 ? "text-amber-400" : "text-emerald-400"}`}>
              {formatPrice(data.vix)}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-400">A/D Ratio</span>
            <span className="font-mono text-zinc-300">
              {data.breadth.advance_decline.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-400">&gt;200 SMA</span>
            <span className="font-mono text-zinc-300">
              {formatPercent(data.breadth.pct_above_200sma)}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-zinc-400">NH/NL</span>
            <span className="font-mono text-zinc-300">
              {data.breadth.new_highs_lows.toFixed(1)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
