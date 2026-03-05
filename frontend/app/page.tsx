"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreCard } from "@/components/score-card";
import { SignalTable } from "@/components/signal-table";
import { MarketRegimePanel } from "@/components/market-regime";
import { api } from "@/lib/api";
import { formatScore, scoreColor } from "@/lib/format";
import type { Signal } from "@/lib/types";

export default function DashboardPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<Signal[]>("/api/signals?n=20")
      .then(setSignals)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  const avgScore =
    signals.length > 0
      ? signals.reduce((s, sig) => s + sig.composite_score, 0) / signals.length
      : 0;
  const best = signals.length > 0
    ? signals.reduce((a, b) =>
        a.composite_score > b.composite_score ? a : b
      )
    : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight text-zinc-100">
          Dashboard
        </h2>
        <span className="text-xs text-zinc-500">
          Last updated: {new Date().toLocaleString()}
        </span>
      </div>

      {error && (
        <div className="rounded-md border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-400">
          Unable to connect to the backend. Make sure the API server is running.
        </div>
      )}

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <ScoreCard
          title="Total Signals"
          value={loading ? "--" : String(signals.length)}
          loading={loading}
        />
        <ScoreCard
          title="Avg Score"
          value={loading ? "--" : formatScore(avgScore)}
          loading={loading}
        />
        <ScoreCard
          title="Best Signal"
          value={
            loading || !best
              ? "--"
              : `${best.symbol} (${formatScore(best.composite_score)})`
          }
          loading={loading}
        />
        <ScoreCard title="Market Regime" value="--" loading={loading} />
      </div>

      {/* Main content: table + regime sidebar */}
      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">Top Signals</CardTitle>
          </CardHeader>
          <CardContent>
            <SignalTable />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <MarketRegimePanel />
        </div>
      </div>
    </div>
  );
}
