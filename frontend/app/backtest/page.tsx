"use client";

import { BacktestResults } from "@/components/backtest-results";

export default function BacktestPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight text-zinc-100">
        Backtest
      </h2>
      <BacktestResults />
    </div>
  );
}
