"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreCard } from "@/components/score-card";
import { SignalTable } from "@/components/signal-table";
import { MarketRegimePanel } from "@/components/market-regime";
import { ModelExplainer } from "@/components/model-explainer";
import { api } from "@/lib/api";
import { formatScore, scoreColor } from "@/lib/format";
import type { Signal } from "@/lib/types";
import { Activity, TrendingUp, Zap, Award } from "lucide-react";

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
  const best =
    signals.length > 0
      ? signals.reduce((a, b) =>
          a.composite_score > b.composite_score ? a : b
        )
      : null;
  const highConviction = signals.filter((s) => s.composite_score >= 80).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-100">
            Dashboard
          </h2>
          <p className="text-sm text-zinc-500 mt-1">
            ML-scored stock opportunities updated daily
          </p>
        </div>
        <span className="text-xs text-zinc-600">
          {new Date().toLocaleDateString("en-US", {
            weekday: "long",
            month: "short",
            day: "numeric",
          })}
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
          description="Stocks scored today"
          loading={loading}
        />
        <ScoreCard
          title="Avg Score"
          value={loading ? "--" : formatScore(avgScore)}
          description={
            loading
              ? undefined
              : avgScore >= 70
              ? "Strong average"
              : avgScore >= 50
              ? "Moderate average"
              : "Below average"
          }
          loading={loading}
        />
        <ScoreCard
          title="High Conviction"
          value={loading ? "--" : String(highConviction)}
          description="Score ≥ 80"
          loading={loading}
        />
        <ScoreCard
          title="Best Signal"
          value={
            loading || !best
              ? "--"
              : `${best.symbol}`
          }
          description={
            loading || !best
              ? undefined
              : `${best.name || best.sector || ""} — ${formatScore(best.composite_score)}`
          }
          loading={loading}
        />
      </div>

      {/* Main content: table + sidebar */}
      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div className="space-y-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-zinc-100">Top Signals</CardTitle>
                <p className="text-xs text-zinc-500 mt-1">
                  Click any row to see full analysis
                </p>
              </div>
              {!loading && signals.length > 0 && (
                <span className="text-xs text-zinc-600">
                  {signals.length} results
                </span>
              )}
            </CardHeader>
            <CardContent>
              <SignalTable />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <MarketRegimePanel />
          <ModelExplainer />
        </div>
      </div>
    </div>
  );
}
