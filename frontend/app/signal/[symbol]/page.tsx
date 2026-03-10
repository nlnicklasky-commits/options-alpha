"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TechnicalChart } from "@/components/technical-chart";
import { api } from "@/lib/api";
import { formatScore, scoreColor, scoreBgColor, formatPrice } from "@/lib/format";
import type { SignalDetail, DriverInfo } from "@/lib/types";
import { ArrowLeft, ChevronDown, ChevronRight, TrendingUp, Activity, BarChart3, Waves, Shapes, Target } from "lucide-react";

interface SignalPageProps {
  params: Promise<{ symbol: string }>;
}

function MetricRow({
  label,
  value,
  color = "text-zinc-300",
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-zinc-800 last:border-0">
      <span className="text-sm text-zinc-400">{label}</span>
      <span className={`font-mono text-sm ${color}`}>{value}</span>
    </div>
  );
}

function FeatureBar({
  label,
  importance,
  value,
}: {
  label: string;
  importance: number;
  value: number | null;
}) {
  const pct = Math.min(Math.max(importance * 100, 0), 100);
  const color =
    pct >= 80 ? "bg-emerald-400" : pct >= 60 ? "bg-amber-400" : "bg-rose-400";

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-400">{label}</span>
        <span className="text-zinc-500">
          {(importance * 100).toFixed(1)}%
          {value != null && (
            <span className="text-zinc-600 ml-2">
              ({typeof value === "number" ? value.toFixed(2) : value})
            </span>
          )}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-zinc-800">
        <div
          className={`h-1.5 rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function ComponentScoreBar({
  name,
  score,
}: {
  name: string;
  score: number;
}) {
  const pct = Math.min(Math.max((score / 100) * 100, 0), 100);
  const color =
    score >= 75 ? "bg-emerald-400" : score >= 60 ? "bg-amber-400" : "bg-rose-400";

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-400">{name}</span>
        <span className={`font-mono font-semibold ${scoreColor(score)}`}>
          {formatScore(score)}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-zinc-800">
        <div
          className={`h-2 rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const categoryMeta: Record<string, { icon: React.ReactNode; color: string; border: string; bg: string }> = {
  momentum: {
    icon: <TrendingUp className="h-4 w-4" />,
    color: "text-emerald-400",
    border: "border-emerald-500/30",
    bg: "bg-emerald-500/10",
  },
  trend: {
    icon: <Activity className="h-4 w-4" />,
    color: "text-sky-400",
    border: "border-sky-500/30",
    bg: "bg-sky-500/10",
  },
  volume: {
    icon: <BarChart3 className="h-4 w-4" />,
    color: "text-blue-400",
    border: "border-blue-500/30",
    bg: "bg-blue-500/10",
  },
  volatility: {
    icon: <Waves className="h-4 w-4" />,
    color: "text-amber-400",
    border: "border-amber-500/30",
    bg: "bg-amber-500/10",
  },
  pattern: {
    icon: <Shapes className="h-4 w-4" />,
    color: "text-purple-400",
    border: "border-purple-500/30",
    bg: "bg-purple-500/10",
  },
  conviction: {
    icon: <Target className="h-4 w-4" />,
    color: "text-zinc-300",
    border: "border-zinc-600/50",
    bg: "bg-zinc-500/10",
  },
  other: {
    icon: <Target className="h-4 w-4" />,
    color: "text-zinc-400",
    border: "border-zinc-700",
    bg: "bg-zinc-800/50",
  },
};

function DriverCard({ driver }: { driver: DriverInfo }) {
  const [expanded, setExpanded] = useState(false);
  const meta = categoryMeta[driver.category] || categoryMeta.other;

  return (
    <div
      className={`rounded-lg border ${meta.border} ${meta.bg} transition-all cursor-pointer`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <span className={meta.color}>{meta.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-zinc-200">{driver.label}</span>
            <span className={`text-xs uppercase tracking-wide ${meta.color} opacity-60`}>
              {driver.category}
            </span>
          </div>
        </div>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-zinc-500 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-zinc-500 shrink-0" />
        )}
      </div>
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-zinc-800/50 pt-3">
          <div>
            <div className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-1">
              What is this?
            </div>
            <p className="text-sm text-zinc-400 leading-relaxed">
              {driver.description}
            </p>
          </div>
          <div>
            <div className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-1">
              What the model says
            </div>
            <p className="text-sm text-zinc-300 leading-relaxed">
              {driver.signal}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function SignalPage({ params }: SignalPageProps) {
  const { symbol } = use(params);
  const upper = symbol.toUpperCase();
  const router = useRouter();

  const [signal, setSignal] = useState<SignalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<SignalDetail>(`/api/signals/${symbol}`)
      .then(setSignal)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.back()}
            className="text-zinc-400 hover:text-zinc-100 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <Skeleton className="h-8 w-32 bg-zinc-800" />
        </div>
        <Skeleton className="h-64 w-full bg-zinc-800" />
      </div>
    );
  }

  if (error || !signal) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => router.back()}
          className="text-zinc-400 hover:text-zinc-100 transition-colors flex items-center gap-2"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-400">
          Could not load signal data for {upper}.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="text-zinc-400 hover:text-zinc-100 transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-3xl font-bold text-zinc-100 font-mono">
            {upper}
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            {signal.name && signal.name !== signal.symbol ? signal.name : signal.sector || "Stock"}
          </p>
        </div>
        <div className="ml-auto">
          <Badge className={`text-base px-3 py-1.5 ${scoreBgColor(signal.composite_score)}`}>
            {formatScore(signal.composite_score)}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Signal Drivers - promoted to primary position */}
          {signal.drivers && signal.drivers.length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-zinc-100">
                  Signal Drivers
                  <span className="text-xs text-zinc-500 font-normal ml-2">
                    Click to expand
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {signal.drivers.map((driver, i) => (
                  <DriverCard key={i} driver={driver} />
                ))}
              </CardContent>
            </Card>
          )}

          {/* Score breakdown */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100">Score Breakdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {Object.keys(signal.component_scores).length > 0 ? (
                <>
                  {Object.entries(signal.component_scores).map(([name, score]) => (
                    <ComponentScoreBar
                      key={name}
                      name={name.replace(/_/g, " ").toUpperCase()}
                      score={score}
                    />
                  ))}
                </>
              ) : (
                <p className="text-zinc-500 text-sm">
                  Component scores unavailable
                </p>
              )}
            </CardContent>
          </Card>

          {/* Top feature drivers */}
          {signal.top_features && signal.top_features.length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-zinc-100">
                  Top Feature Drivers
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {signal.top_features.map((feature, i) => (
                  <FeatureBar
                    key={i}
                    label={feature.feature.replace(/_/g, " ")}
                    importance={feature.importance}
                    value={feature.value}
                  />
                ))}
              </CardContent>
            </Card>
          )}

          {/* Price chart */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100">Price Chart</CardTitle>
            </CardHeader>
            <CardContent>
              <TechnicalChart symbol={symbol} />
            </CardContent>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Key metrics */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100">Key Metrics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              <MetricRow
                label="Composite Score"
                value={formatScore(signal.composite_score)}
                color={scoreColor(signal.composite_score)}
              />
              <MetricRow
                label="Breakout Prob."
                value={`${Math.round(signal.breakout_probability * 100)}%`}
              />
              {signal.rsi_14 != null && (
                <MetricRow
                  label="RSI(14)"
                  value={formatScore(signal.rsi_14)}
                  color={
                    signal.rsi_14 > 70
                      ? "text-rose-400"
                      : signal.rsi_14 < 30
                        ? "text-emerald-400"
                        : "text-zinc-300"
                  }
                />
              )}
              {signal.adx_14 != null && (
                <MetricRow
                  label="ADX(14)"
                  value={formatScore(signal.adx_14)}
                  color={signal.adx_14 > 25 ? "text-emerald-400" : "text-zinc-300"}
                />
              )}
              {signal.bb_pctb != null && (
                <MetricRow
                  label="BB %B"
                  value={`${(signal.bb_pctb * 100).toFixed(0)}%`}
                />
              )}
              {signal.price != null && (
                <MetricRow label="Price" value={`$${formatPrice(signal.price)}`} />
              )}
              {signal.volume_ratio != null && (
                <MetricRow
                  label="Volume Ratio"
                  value={`${signal.volume_ratio.toFixed(1)}x`}
                  color={signal.volume_ratio >= 1.5 ? "text-emerald-400" : "text-zinc-300"}
                />
              )}
              {signal.sma_bullish != null && (
                <MetricRow
                  label="SMA Trend"
                  value={signal.sma_bullish ? "Bullish" : "Bearish"}
                  color={signal.sma_bullish ? "text-emerald-400" : "text-rose-400"}
                />
              )}
            </CardContent>
          </Card>

          {/* Pattern */}
          {signal.pattern && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-zinc-100">Pattern</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-zinc-300 font-medium">{signal.pattern}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
