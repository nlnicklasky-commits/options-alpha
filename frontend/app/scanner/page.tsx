"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatPrice, formatScore, formatPercent, scoreColor } from "@/lib/format";
import type { Signal } from "@/lib/types";
import { Search, ArrowUpDown } from "lucide-react";

const PATTERN_TYPES = [
  "wedge",
  "triangle",
  "flag",
  "cup",
  "channel",
  "double_bottom",
  "head_shoulders",
];

export default function ScannerPage() {
  const router = useRouter();
  const [minScore, setMinScore] = useState(60);
  const [minVolume, setMinVolume] = useState(1.0);
  const [ivMin, setIvMin] = useState(0);
  const [ivMax, setIvMax] = useState(100);
  const [pattern, setPattern] = useState<string>("all");
  const [smaFilter, setSmaFilter] = useState(true);
  const [results, setResults] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runScan = useCallback(async () => {
    setLoading(true);
    setSearched(true);
    setError(null);
    try {
      const data = await api<Signal[]>(
        `/api/signals?n=100&min_score=${minScore}`
      );
      const filtered = data.filter((s) => {
        if (s.volume_ratio != null && s.volume_ratio < minVolume) return false;
        if (s.iv_rank != null && (s.iv_rank < ivMin || s.iv_rank > ivMax))
          return false;
        if (pattern !== "all" && s.pattern !== pattern) return false;
        if (smaFilter && s.sma_bullish === false) return false;
        return true;
      });
      setResults(filtered);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch signals. Backend may be offline.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [minScore, minVolume, ivMin, ivMax, pattern, smaFilter]);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight text-zinc-100">
        Scanner
      </h2>

      {/* Filter bar */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-zinc-100">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Label className="text-zinc-400">
                Min Score: {minScore}
              </Label>
              <Slider
                value={[minScore]}
                onValueChange={([v]) => setMinScore(v)}
                min={0}
                max={100}
                step={5}
                className="mt-2"
              />
            </div>
            <div>
              <Label className="text-zinc-400">Pattern Type</Label>
              <Select value={pattern} onValueChange={setPattern}>
                <SelectTrigger className="mt-1 bg-zinc-800 border-zinc-700 text-zinc-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-800 border-zinc-700">
                  <SelectItem value="all">All Patterns</SelectItem>
                  {PATTERN_TYPES.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p.replace("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-zinc-400">
                IV Rank: {ivMin}-{ivMax}
              </Label>
              <div className="mt-2 flex gap-2">
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={ivMin}
                  onChange={(e) => setIvMin(Number(e.target.value))}
                  className="w-20 bg-zinc-800 border-zinc-700 text-zinc-100"
                />
                <span className="text-zinc-500 self-center">-</span>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  value={ivMax}
                  onChange={(e) => setIvMax(Number(e.target.value))}
                  className="w-20 bg-zinc-800 border-zinc-700 text-zinc-100"
                />
              </div>
            </div>
            <div>
              <Label className="text-zinc-400">Min Vol Ratio</Label>
              <Input
                type="number"
                step="0.1"
                min={0}
                value={minVolume}
                onChange={(e) => setMinVolume(Number(e.target.value))}
                className="mt-1 bg-zinc-800 border-zinc-700 text-zinc-100"
              />
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-zinc-400">
              <input
                type="checkbox"
                checked={smaFilter}
                onChange={(e) => setSmaFilter(e.target.checked)}
                className="rounded border-zinc-600"
              />
              SMA 50 &gt; SMA 200
            </label>
            <Button
              onClick={runScan}
              disabled={loading}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <Search className="mr-2 h-4 w-4" />
              {loading ? "Scanning..." : "Scan Now"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full bg-zinc-800" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-400">
          {error}
        </div>
      )}

      {!loading && searched && !error && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">
              {results.length} stocks match your criteria
            </CardTitle>
          </CardHeader>
          <CardContent>
            {results.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-zinc-500">
                No matches found. Try adjusting your filters.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="border-zinc-800 hover:bg-transparent">
                    <TableHead className="text-zinc-400 w-12">#</TableHead>
                    <TableHead className="text-zinc-400">Company</TableHead>
                    <TableHead className="text-zinc-400">Score</TableHead>
                    <TableHead className="text-zinc-400">Pattern</TableHead>
                    <TableHead className="text-zinc-400">IV Rank</TableHead>
                    <TableHead className="text-zinc-400">Price</TableHead>
                    <TableHead className="text-zinc-400">Vol Ratio</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((signal, i) => (
                    <TableRow
                      key={signal.symbol}
                      className="border-zinc-800 cursor-pointer hover:bg-zinc-800/50"
                      onClick={() =>
                        router.push(
                          `/ticker/${signal.symbol.toLowerCase()}`
                        )
                      }
                    >
                      <TableCell className="text-zinc-500 font-mono text-xs">
                        {i + 1}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-bold text-zinc-100 text-sm">{signal.symbol}</span>
                          <span className="text-xs text-zinc-500 truncate max-w-[180px]">
                            {signal.name || signal.sector || "—"}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell
                        className={`font-mono font-bold ${scoreColor(signal.composite_score)}`}
                      >
                        {formatScore(signal.composite_score)}
                      </TableCell>
                      <TableCell className="text-zinc-300">
                        {signal.pattern || "--"}
                      </TableCell>
                      <TableCell className="font-mono text-zinc-300">
                        {signal.iv_rank != null
                          ? formatPercent(signal.iv_rank)
                          : "--"}
                      </TableCell>
                      <TableCell className="font-mono text-zinc-300">
                        {signal.price != null
                          ? `$${formatPrice(signal.price)}`
                          : "--"}
                      </TableCell>
                      <TableCell className="font-mono text-zinc-300">
                        {signal.volume_ratio != null
                          ? signal.volume_ratio.toFixed(1) + "x"
                          : "--"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
