"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { formatPrice, formatScore, formatPercent, scoreColor } from "@/lib/format";
import type { Signal } from "@/lib/types";
import { ArrowUpDown, TrendingUp, Info } from "lucide-react";

type SortKey =
  | "composite_score"
  | "symbol"
  | "breakout_probability"
  | "iv_rank"
  | "price"
  | "volume_ratio";

function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const pct = Math.min(Math.max((score / max) * 100, 0), 100);
  const color =
    score >= 80
      ? "bg-emerald-400"
      : score >= 60
      ? "bg-amber-400"
      : "bg-rose-400";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-zinc-800">
        <div
          className={`h-1.5 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-mono text-sm font-bold ${scoreColor(score)}`}>
        {formatScore(score)}
      </span>
    </div>
  );
}

function BreakoutBadge({ probability }: { probability: number }) {
  const pct = Math.round(probability * 100);
  const color =
    pct >= 70
      ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
      : pct >= 50
      ? "text-amber-400 bg-amber-400/10 border-amber-400/20"
      : "text-zinc-400 bg-zinc-800 border-zinc-700";

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-mono ${color}`}>
      <TrendingUp className="h-3 w-3" />
      {pct}%
    </span>
  );
}

const columnTooltips: Record<string, string> = {
  Score:
    "Composite score (0–100) from the ensemble ML model. Higher = stronger bullish setup.",
  Breakout:
    "Model-estimated probability this stock breaks out above resistance in the next 5–10 days.",
  "IV Rank":
    "Implied Volatility Rank — how current IV compares to the past year. High = options are expensive.",
  "Vol Ratio":
    "Today's volume vs. 30-day average. Values above 1.5× suggest unusual activity.",
  Pattern:
    "Dominant chart pattern detected (e.g., cup & handle, ascending triangle).",
};

export function SignalTable() {
  const router = useRouter();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    api<Signal[]>("/api/signals?n=20")
      .then(setSignals)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSort = useCallback((key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortAsc((a) => !a);
        return key;
      }
      setSortAsc(false);
      return key;
    });
  }, []);

  const sorted = [...signals].sort((a, b) => {
    const av = a[sortKey] ?? 0;
    const bv = b[sortKey] ?? 0;
    if (typeof av === "string" && typeof bv === "string") {
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return sortAsc ? Number(av) - Number(bv) : Number(bv) - Number(av);
  });

  const SortHeader = ({
    label,
    field,
    tooltip,
  }: {
    label: string;
    field: SortKey;
    tooltip?: string;
  }) => (
    <TableHead
      className="cursor-pointer select-none text-zinc-400 hover:text-zinc-200"
      onClick={() => handleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {tooltip && (
          <Tooltip content={tooltip}>
            <Info className="h-3 w-3 text-zinc-600 hover:text-zinc-400" />
          </Tooltip>
        )}
        <ArrowUpDown className="h-3 w-3" />
      </span>
    </TableHead>
  );

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full bg-zinc-800" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-32 items-center justify-center text-zinc-500">
        Unable to load signals. Backend may be offline.
      </div>
    );
  }

  if (sorted.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-zinc-500">
        No signals yet. Run the pipeline to generate signals.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-zinc-800 hover:bg-transparent">
          <TableHead className="text-zinc-400 w-12">#</TableHead>
          <SortHeader label="Company" field="symbol" />
          <SortHeader
            label="Score"
            field="composite_score"
            tooltip={columnTooltips["Score"]}
          />
          <TableHead className="text-zinc-400">
            <span className="inline-flex items-center gap-1">
              Breakout
              <Tooltip content={columnTooltips["Breakout"]}>
                <Info className="h-3 w-3 text-zinc-600 hover:text-zinc-400" />
              </Tooltip>
            </span>
          </TableHead>
          <TableHead className="text-zinc-400">
            <span className="inline-flex items-center gap-1">
              Pattern
              <Tooltip content={columnTooltips["Pattern"]}>
                <Info className="h-3 w-3 text-zinc-600 hover:text-zinc-400" />
              </Tooltip>
            </span>
          </TableHead>
          <SortHeader
            label="IV Rank"
            field="iv_rank"
            tooltip={columnTooltips["IV Rank"]}
          />
          <SortHeader label="Price" field="price" />
          <SortHeader
            label="Vol Ratio"
            field="volume_ratio"
            tooltip={columnTooltips["Vol Ratio"]}
          />
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((signal, i) => (
          <TableRow
            key={signal.symbol}
            className="border-zinc-800 cursor-pointer hover:bg-zinc-800/50 transition-colors"
            onClick={() => router.push(`/ticker/${signal.symbol.toLowerCase()}`)}
          >
            <TableCell className="text-zinc-600 font-mono text-xs">
              {i + 1}
            </TableCell>
            <TableCell>
              <div className="flex flex-col">
                <span className="font-bold text-zinc-100 text-sm">
                  {signal.symbol}
                </span>
                <span className="text-xs text-zinc-500 truncate max-w-[180px]">
                  {signal.name || signal.sector || "—"}
                </span>
              </div>
            </TableCell>
            <TableCell>
              <ScoreBar score={signal.composite_score} />
            </TableCell>
            <TableCell>
              <BreakoutBadge probability={signal.breakout_probability} />
            </TableCell>
            <TableCell>
              {signal.pattern ? (
                <span className="inline-flex items-center rounded-md bg-zinc-800 border border-zinc-700 px-2 py-0.5 text-xs text-zinc-300">
                  {signal.pattern.replace(/_/g, " ")}
                </span>
              ) : (
                <span className="text-zinc-600 text-xs">none</span>
              )}
            </TableCell>
            <TableCell>
              {signal.iv_rank != null ? (
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-10 rounded-full bg-zinc-800">
                    <div
                      className={`h-1.5 rounded-full ${
                        signal.iv_rank >= 70
                          ? "bg-emerald-400"
                          : signal.iv_rank >= 40
                          ? "bg-amber-400"
                          : "bg-rose-400"
                      }`}
                      style={{ width: `${signal.iv_rank}%` }}
                    />
                  </div>
                  <span className="font-mono text-xs text-zinc-300">
                    {formatPercent(signal.iv_rank)}
                  </span>
                </div>
              ) : (
                <span className="text-zinc-600 text-xs">—</span>
              )}
            </TableCell>
            <TableCell className="font-mono text-sm text-zinc-300">
              {signal.price != null ? `$${formatPrice(signal.price)}` : "—"}
            </TableCell>
            <TableCell>
              {signal.volume_ratio != null ? (
                <span
                  className={`font-mono text-sm ${
                    signal.volume_ratio >= 1.5
                      ? "text-emerald-400 font-bold"
                      : "text-zinc-400"
                  }`}
                >
                  {signal.volume_ratio.toFixed(1)}×
                </span>
              ) : (
                <span className="text-zinc-600 text-xs">—</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
