"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { formatPrice, formatPercent } from "@/lib/format";
import type { MarketRegime } from "@/lib/types";
import { Info, Shield } from "lucide-react";

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

const regimeDescriptions: Record<MarketRegime, string> = {
  BULL: "Markets are trending up — breadth is positive and volatility is low. Higher conviction on bullish signals.",
  BEAR: "Markets are under pressure — elevated volatility and negative breadth. The model raises entry thresholds.",
  CHOPPY: "Mixed signals — no clear directional trend. The model is more selective and favors lower-risk setups.",
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
        <CardTitle className="text-sm text-zinc-100 flex items-center gap-2">
          <Shield className="h-4 w-4 text-zinc-400" />
          Market Regime
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <Badge className={`text-sm ${regimeStyles[data.regime]}`}>
            {data.regime}
          </Badge>
          <p className="text-xs text-zinc-500 mt-2 leading-relaxed">
            {regimeDescriptions[data.regime]}
          </p>
        </div>

        <div className="space-y-2.5">
          <MetricRow
            label="VIX"
            tooltip="CBOE Volatility Index — measures expected market volatility. Below 18 is calm, above 25 signals fear."
            value={formatPrice(data.vix)}
            valueColor={
              data.vix > 25
                ? "text-rose-400"
                : data.vix > 18
                ? "text-amber-400"
                : "text-emerald-400"
            }
          />
          <MetricRow
            label="A/D Ratio"
            tooltip="Advance/Decline ratio — advancing stocks divided by declining stocks. Above 1.0 is bullish breadth."
            value={data.breadth.advance_decline.toFixed(2)}
            valueColor={
              data.breadth.advance_decline > 1
                ? "text-emerald-400"
                : "text-zinc-300"
            }
          />
          <MetricRow
            label=">200 SMA"
            tooltip="Percentage of S&P 500 stocks trading above their 200-day moving average. Above 60% is bullish."
            value={formatPercent(data.breadth.pct_above_200sma)}
            valueColor={
              data.breadth.pct_above_200sma > 60
                ? "text-emerald-400"
                : "text-zinc-300"
            }
          />
          <MetricRow
            label="NH/NL"
            tooltip="New Highs vs. New Lows ratio. Above 1.0 means more stocks are making new highs than new lows."
            value={data.breadth.new_highs_lows.toFixed(1)}
            valueColor={
              data.breadth.new_highs_lows > 1
                ? "text-emerald-400"
                : "text-zinc-300"
            }
          />
        </div>
      </CardContent>
    </Card>
  );
}

function MetricRow({
  label,
  tooltip,
  value,
  valueColor = "text-zinc-300",
}: {
  label: string;
  tooltip: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="flex justify-between items-center text-sm">
      <span className="text-zinc-400 flex items-center gap-1">
        {label}
        <Tooltip content={tooltip}>
          <Info className="h-3 w-3 text-zinc-600 hover:text-zinc-400 cursor-help" />
        </Tooltip>
      </span>
      <span className={`font-mono ${valueColor}`}>{value}</span>
    </div>
  );
}
