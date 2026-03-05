"use client";

import { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatPrice, formatPercent, formatNumber, scoreColor } from "@/lib/format";
import type {
  BacktestRequest,
  BacktestResponse,
  BacktestTrade,
} from "@/lib/types";
import { ScoreCard } from "@/components/score-card";

export function BacktestResults() {
  const [params, setParams] = useState<BacktestRequest>({
    start_date: "2025-01-01",
    end_date: "2026-03-01",
    entry_threshold: 0.65,
    target_pct: 1.0,
    stop_pct: -0.5,
    max_days: 20,
  });
  const [result, setResult] = useState<BacktestResponse | null>(null);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    try {
      const { backtest_id } = await api<{ backtest_id: number }>(
        "/api/backtest",
        {
          method: "POST",
          body: JSON.stringify(params),
        }
      );
      const [bt, tradeList] = await Promise.all([
        api<BacktestResponse>(`/api/backtest/${backtest_id}`),
        api<BacktestTrade[]>(`/api/backtest/${backtest_id}/trades`),
      ]);
      setResult(bt);
      setTrades(tradeList);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  const bucketData = result
    ? Object.entries(result.results_by_score_bucket).map(([k, v]) => ({
        bucket: k,
        win_rate: v.win_rate * 100,
        count: v.count,
      }))
    : [];

  const patternData = result
    ? Object.entries(result.results_by_pattern).map(([k, v]) => ({
        pattern: k,
        win_rate: v.win_rate * 100,
        count: v.count,
      }))
    : [];

  const regimeData = result
    ? Object.entries(result.results_by_regime).map(([k, v]) => ({
        regime: k,
        win_rate: v.win_rate * 100,
        count: v.count,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Parameter form */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-zinc-100">Backtest Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Label className="text-zinc-400">Start Date</Label>
              <Input
                type="date"
                value={params.start_date}
                onChange={(e) =>
                  setParams((p) => ({ ...p, start_date: e.target.value }))
                }
                className="bg-zinc-800 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <Label className="text-zinc-400">End Date</Label>
              <Input
                type="date"
                value={params.end_date}
                onChange={(e) =>
                  setParams((p) => ({ ...p, end_date: e.target.value }))
                }
                className="bg-zinc-800 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <Label className="text-zinc-400">Entry Threshold</Label>
              <Input
                type="number"
                step="0.05"
                min="0"
                max="1"
                value={params.entry_threshold}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    entry_threshold: parseFloat(e.target.value),
                  }))
                }
                className="bg-zinc-800 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <Label className="text-zinc-400">Target %</Label>
              <Input
                type="number"
                step="0.1"
                value={params.target_pct}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    target_pct: parseFloat(e.target.value),
                  }))
                }
                className="bg-zinc-800 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <Label className="text-zinc-400">Stop %</Label>
              <Input
                type="number"
                step="0.1"
                value={params.stop_pct}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    stop_pct: parseFloat(e.target.value),
                  }))
                }
                className="bg-zinc-800 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <Label className="text-zinc-400">Max Days</Label>
              <Input
                type="number"
                min="1"
                value={params.max_days}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    max_days: parseInt(e.target.value),
                  }))
                }
                className="bg-zinc-800 border-zinc-700 text-zinc-100"
              />
            </div>
            <div className="flex items-end">
              <Button
                onClick={runBacktest}
                disabled={loading}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {loading ? "Running..." : "Run Backtest"}
              </Button>
            </div>
          </div>
          {error && (
            <p className="mt-3 text-sm text-rose-400">{error}</p>
          )}
        </CardContent>
      </Card>

      {loading && (
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 bg-zinc-800" />
          ))}
        </div>
      )}

      {result && (
        <>
          {/* Summary stats */}
          <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
            <ScoreCard
              title="Total Trades"
              value={formatNumber(result.stats.total_trades)}
            />
            <ScoreCard
              title="Win Rate"
              value={formatPercent(result.stats.win_rate * 100)}
            />
            <ScoreCard
              title="Profit Factor"
              value={result.stats.profit_factor.toFixed(2)}
            />
            <ScoreCard
              title="Sharpe"
              value={result.stats.sharpe_ratio.toFixed(2)}
            />
            <ScoreCard
              title="Max Drawdown"
              value={formatPercent(result.stats.max_drawdown * 100)}
            />
            <ScoreCard
              title="Expectancy"
              value={formatPercent(result.stats.expectancy * 100)}
            />
          </div>

          {/* Equity curve */}
          {result.equity_curve.length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-zinc-100">Equity Curve</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={result.equity_curve}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: "#71717a", fontSize: 11 }}
                      tickFormatter={(v: string) => v.slice(5)}
                      stroke="#3f3f46"
                    />
                    <YAxis
                      tick={{ fill: "#71717a", fontSize: 11 }}
                      stroke="#3f3f46"
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181b",
                        border: "1px solid #3f3f46",
                        borderRadius: "6px",
                        color: "#f4f4f5",
                        fontSize: 12,
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="cumulative_pnl"
                      stroke="#34d399"
                      fill="#34d399"
                      fillOpacity={0.1}
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Breakdown charts */}
          <div className="grid gap-4 md:grid-cols-3">
            {bucketData.length > 0 && (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-sm text-zinc-100">
                    Win Rate by Score Bucket
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={bucketData}>
                      <XAxis
                        dataKey="bucket"
                        tick={{ fill: "#71717a", fontSize: 10 }}
                        stroke="#3f3f46"
                      />
                      <YAxis
                        tick={{ fill: "#71717a", fontSize: 10 }}
                        stroke="#3f3f46"
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#18181b",
                          border: "1px solid #3f3f46",
                          borderRadius: "6px",
                          color: "#f4f4f5",
                          fontSize: 12,
                        }}
                      />
                      <Bar dataKey="win_rate" fill="#34d399" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            )}

            {patternData.length > 0 && (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-sm text-zinc-100">
                    Win Rate by Pattern
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={patternData}>
                      <XAxis
                        dataKey="pattern"
                        tick={{ fill: "#71717a", fontSize: 10 }}
                        stroke="#3f3f46"
                      />
                      <YAxis
                        tick={{ fill: "#71717a", fontSize: 10 }}
                        stroke="#3f3f46"
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#18181b",
                          border: "1px solid #3f3f46",
                          borderRadius: "6px",
                          color: "#f4f4f5",
                          fontSize: 12,
                        }}
                      />
                      <Bar dataKey="win_rate" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            )}

            {regimeData.length > 0 && (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-sm text-zinc-100">
                    Win Rate by Regime
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={regimeData}>
                      <XAxis
                        dataKey="regime"
                        tick={{ fill: "#71717a", fontSize: 10 }}
                        stroke="#3f3f46"
                      />
                      <YAxis
                        tick={{ fill: "#71717a", fontSize: 10 }}
                        stroke="#3f3f46"
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#18181b",
                          border: "1px solid #3f3f46",
                          borderRadius: "6px",
                          color: "#f4f4f5",
                          fontSize: 12,
                        }}
                      />
                      <Bar dataKey="win_rate" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Trade log */}
          {trades.length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-zinc-100">Trade Log</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-96 overflow-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-zinc-800">
                        <TableHead className="text-zinc-400">Symbol</TableHead>
                        <TableHead className="text-zinc-400">Entry</TableHead>
                        <TableHead className="text-zinc-400">Exit</TableHead>
                        <TableHead className="text-zinc-400">Entry $</TableHead>
                        <TableHead className="text-zinc-400">Exit $</TableHead>
                        <TableHead className="text-zinc-400">Return</TableHead>
                        <TableHead className="text-zinc-400">Score</TableHead>
                        <TableHead className="text-zinc-400">Pattern</TableHead>
                        <TableHead className="text-zinc-400">Regime</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {trades.map((t) => (
                        <TableRow key={t.id} className="border-zinc-800">
                          <TableCell className="font-bold text-zinc-100">
                            {t.symbol || "--"}
                          </TableCell>
                          <TableCell className="text-zinc-300 font-mono text-xs">
                            {t.entry_date}
                          </TableCell>
                          <TableCell className="text-zinc-300 font-mono text-xs">
                            {t.exit_date || "--"}
                          </TableCell>
                          <TableCell className="text-zinc-300 font-mono">
                            ${formatPrice(t.entry_price)}
                          </TableCell>
                          <TableCell className="text-zinc-300 font-mono">
                            {t.exit_price != null
                              ? `$${formatPrice(t.exit_price)}`
                              : "--"}
                          </TableCell>
                          <TableCell
                            className={`font-mono font-bold ${
                              t.return_pct != null
                                ? t.return_pct >= 0
                                  ? "text-emerald-400"
                                  : "text-rose-400"
                                : "text-zinc-500"
                            }`}
                          >
                            {t.return_pct != null
                              ? formatPercent(t.return_pct * 100)
                              : "--"}
                          </TableCell>
                          <TableCell
                            className={`font-mono ${
                              t.signal_score != null
                                ? scoreColor(t.signal_score)
                                : "text-zinc-500"
                            }`}
                          >
                            {t.signal_score?.toFixed(1) ?? "--"}
                          </TableCell>
                          <TableCell className="text-zinc-300">
                            {t.pattern_type || "--"}
                          </TableCell>
                          <TableCell className="text-zinc-300">
                            {t.regime || "--"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
