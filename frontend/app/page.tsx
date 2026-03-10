"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SignalTable } from "@/components/signal-table";
import { MarketBar } from "@/components/market-bar";
import { api } from "@/lib/api";
import type { Signal } from "@/lib/types";

export default function HomePage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<Signal[]>("/api/signals?n=20")
      .then(setSignals)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-100">
          Options Alpha
        </h1>
        <p className="text-sm text-zinc-400 mt-2">
          ML-scored trading signals · Breakout probability · Signal drivers
        </p>
      </div>

      {/* Market regime bar */}
      <MarketBar />

      {error && (
        <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-400">
          Unable to connect to the backend. Make sure the API server is running.
        </div>
      )}

      {/* Signals table */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-zinc-100">Signal Scanner</CardTitle>
              <p className="text-xs text-zinc-500 mt-1">
                Click any row to view detailed analysis
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <SignalTable signals={signals} loading={loading} />
        </CardContent>
      </Card>
    </div>
  );
}
