"use client";

import { useState, useEffect, use } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TechnicalChart } from "@/components/technical-chart";
import { api } from "@/lib/api";
import {
  formatPrice,
  formatPercent,
  formatScore,
  scoreColor,
  scoreBgColor,
} from "@/lib/format";
import type { ScoreDetail } from "@/lib/types";

interface TickerPageProps {
  params: Promise<{ symbol: string }>;
}

function ScoreCircle({ score }: { score: number }) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="120" height="120" className="-rotate-90">
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          stroke="#27272a"
          strokeWidth="8"
        />
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          stroke={score >= 80 ? "#34d399" : score >= 60 ? "#fbbf24" : "#f87171"}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
        />
      </svg>
      <span
        className={`absolute text-2xl font-bold ${scoreColor(score)}`}
      >
        {formatScore(score)}
      </span>
    </div>
  );
}

function BreakdownBar({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  const pct = Math.min(Math.max(value * 100, 0), 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-400">{label}</span>
        <span className="font-mono text-zinc-300">{formatPercent(pct)}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-zinc-800">
        <div
          className={`h-1.5 rounded-full ${
            pct >= 80
              ? "bg-emerald-400"
              : pct >= 60
              ? "bg-amber-400"
              : "bg-rose-400"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function TickerPage({ params }: TickerPageProps) {
  const { symbol } = use(params);
  const upper = symbol.toUpperCase();
  const [score, setScore] = useState<ScoreDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [scoreError, setScoreError] = useState(false);

  useEffect(() => {
    api<ScoreDetail>(`/api/score/${symbol}`)
      .then(setScore)
      .catch(() => setScoreError(true))
      .finally(() => setLoading(false));
  }, [symbol]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <h2 className="text-2xl font-bold tracking-tight text-zinc-100">
          {upper}
        </h2>
        {score && (
          <Badge className={`text-sm ${scoreBgColor(score.composite_score)}`}>
            Score: {formatScore(score.composite_score)}
          </Badge>
        )}
      </div>

      {scoreError && (
        <div className="rounded-md border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-400">
          Could not load score data for {upper}. The model may not be trained yet or the backend is offline.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          {/* Score card */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100">Composite Score</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex gap-8">
                  <Skeleton className="h-[120px] w-[120px] rounded-full bg-zinc-800" />
                  <div className="flex-1 space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-6 w-full bg-zinc-800" />
                    ))}
                  </div>
                </div>
              ) : score ? (
                <div className="flex gap-8 items-start">
                  <ScoreCircle score={score.composite_score} />
                  <div className="flex-1 space-y-3">
                    {Object.entries(score.component_scores).map(
                      ([key, val]) => (
                        <BreakdownBar
                          key={key}
                          label={key.replace(/_/g, " ")}
                          value={val}
                        />
                      )
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-zinc-500">Score data unavailable</p>
              )}
            </CardContent>
          </Card>

          {/* Technical chart */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100">Price Chart</CardTitle>
            </CardHeader>
            <CardContent>
              <TechnicalChart symbol={symbol} />
            </CardContent>
          </Card>
        </div>

        {/* Right panel */}
        <div className="space-y-6">
          {/* Options panel */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-sm text-zinc-100">
                Options Data
              </CardTitle>
            </CardHeader>
            <CardContent>
              <OptionsPanel symbol={symbol} />
            </CardContent>
          </Card>

          {/* Top features */}
          {score && score.top_features.length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-sm text-zinc-100">
                  Top Feature Drivers
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {score.top_features.map((f) => (
                    <div
                      key={f.feature}
                      className="flex justify-between text-sm"
                    >
                      <span className="text-zinc-400">
                        {f.feature.replace(/_/g, " ")}
                      </span>
                      <span className="font-mono text-zinc-300">
                        {(f.importance * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function OptionsPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<{
    iv_rank: number | null;
    iv: number | null;
    hv: number | null;
    put_call_ratio: number | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<{
      iv_rank: number | null;
      iv: number | null;
      hv: number | null;
      put_call_ratio: number | null;
    }>(`/api/options/${symbol}`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-5 w-full bg-zinc-800" />
        ))}
      </div>
    );
  }

  if (!data) {
    return <p className="text-xs text-zinc-500">Options data unavailable</p>;
  }

  return (
    <div className="space-y-3">
      {/* IV Rank gauge */}
      {data.iv_rank != null && (
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-zinc-400">IV Rank</span>
            <span className="font-mono text-zinc-300">
              {formatPercent(data.iv_rank)}
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-zinc-800">
            <div
              className={`h-2 rounded-full ${
                data.iv_rank >= 70
                  ? "bg-emerald-400"
                  : data.iv_rank >= 40
                  ? "bg-amber-400"
                  : "bg-rose-400"
              }`}
              style={{ width: `${data.iv_rank}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex justify-between text-sm">
        <span className="text-zinc-400">IV</span>
        <span className="font-mono text-zinc-300">
          {data.iv != null ? formatPercent(data.iv) : "--"}
        </span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-zinc-400">HV</span>
        <span className="font-mono text-zinc-300">
          {data.hv != null ? formatPercent(data.hv) : "--"}
        </span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-zinc-400">P/C Ratio</span>
        <span className="font-mono text-zinc-300">
          {data.put_call_ratio != null
            ? data.put_call_ratio.toFixed(2)
            : "--"}
        </span>
      </div>
    </div>
  );
}
