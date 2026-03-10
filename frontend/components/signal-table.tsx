"use client";

import { useState, useEffect } from "react";
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
import { api } from "@/lib/api";
import { formatPrice, formatScore, scoreColor } from "@/lib/format";
import type { Signal } from "@/lib/types";
import { ArrowUp, ArrowDown } from "lucide-react";

interface SignalTableProps {
  signals?: Signal[];
  loading?: boolean;
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(Math.max((score / 100) * 100, 0), 100);
  const color =
    score >= 75 ? "bg-emerald-400" : score >= 60 ? "bg-amber-400" : "bg-rose-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 rounded-full bg-zinc-800">
        <div
          className={`h-2 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-mono text-xs font-bold ${scoreColor(score)}`}>
        {formatScore(score)}
      </span>
    </div>
  );
}

function BreakoutBadge({ probability }: { probability: number }) {
  const pct = Math.round(probability * 100);
  const color =
    pct >= 75 ? "text-emerald-400" : pct >= 60 ? "text-amber-400" : "text-rose-400";
  return (
    <span className={`font-mono text-xs font-semibold ${color}`}>
      {pct}%
    </span>
  );
}

function DriverChip({ text }: { text: string }) {
  // Try to infer color from driver content
  let bgColor = "bg-zinc-500/20 text-zinc-400";
  if (
    text.toLowerCase().includes("momentum") ||
    text.toLowerCase().includes("strong")
  ) {
    bgColor = "bg-emerald-500/20 text-emerald-400";
  } else if (
    text.toLowerCase().includes("volume") ||
    text.toLowerCase().includes("unusual")
  ) {
    bgColor = "bg-blue-500/20 text-blue-400";
  } else if (
    text.toLowerCase().includes("pattern") ||
    text.toLowerCase().includes("flag")
  ) {
    bgColor = "bg-purple-500/20 text-purple-400";
  }

  return (
    <span
      className={`inline-block px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap ${bgColor}`}
    >
      {text}
    </span>
  );
}

function DriverColumn({ drivers }: { drivers: string[] }) {
  if (!drivers || drivers.length === 0) {
    return <span className="text-zinc-600 text-xs">—</span>;
  }

  const shown = drivers.slice(0, 3);
  const hidden = Math.max(0, drivers.length - 3);

  return (
    <div className="flex flex-wrap gap-1.5">
      {shown.map((driver, i) => (
        <DriverChip key={i} text={driver} />
      ))}
      {hidden > 0 && (
        <span className="text-zinc-500 text-xs font-medium">+{hidden} more</span>
      )}
    </div>
  );
}

export function SignalTable({ signals: propSignals, loading: propLoading }: SignalTableProps) {
  const router = useRouter();
  const [signals, setSignals] = useState<Signal[]>(propSignals || []);
  const [loading, setLoading] = useState(propLoading ?? true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<"composite_score" | "breakout_probability">(
    "composite_score"
  );
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    if (propSignals !== undefined && propLoading !== undefined) {
      setSignals(propSignals);
      setLoading(propLoading);
      return;
    }

    api<Signal[]>("/api/signals?n=20")
      .then(setSignals)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [propSignals, propLoading]);

  const handleSort = (key: "composite_score" | "breakout_probability") => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const sorted = [...signals].sort((a, b) => {
    const av = sortKey === "composite_score" ? a.composite_score : a.breakout_probability;
    const bv = sortKey === "composite_score" ? b.composite_score : b.breakout_probability;
    return sortAsc ? av - bv : bv - av;
  });

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
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400 w-12">#</TableHead>
              <TableHead className="text-zinc-400 min-w-[200px]">
                Ticker
              </TableHead>
              <TableHead
                className="text-zinc-400 cursor-pointer hover:text-zinc-200 transition-colors"
                onClick={() => handleSort("composite_score")}
              >
                <div className="flex items-center gap-1">
                  Score
                  <ArrowUp className="h-3 w-3" />
                </div>
              </TableHead>
              <TableHead
                className="text-zinc-400 cursor-pointer hover:text-zinc-200 transition-colors"
                onClick={() => handleSort("breakout_probability")}
              >
                <div className="flex items-center gap-1">
                  Breakout
                  <ArrowUp className="h-3 w-3" />
                </div>
              </TableHead>
              <TableHead className="text-zinc-400 min-w-[300px]">
                Drivers
              </TableHead>
              <TableHead className="text-zinc-400 w-20">Price</TableHead>
              <TableHead className="text-zinc-400 w-20">Volume</TableHead>
              <TableHead className="text-zinc-400 w-16">Trend</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((signal, i) => (
              <TableRow
                key={signal.symbol}
                className="border-zinc-800 cursor-pointer hover:bg-zinc-900/50 transition-colors"
                onClick={() => router.push(`/signal/${signal.symbol.toLowerCase()}`)}
              >
                <TableCell className="text-zinc-600 font-mono text-xs">
                  {i + 1}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-bold text-zinc-100 text-sm font-mono">
                      {signal.symbol}
                    </span>
                    <span className="text-xs text-zinc-500 truncate max-w-[180px]">
                      {signal.name && signal.name !== signal.symbol
                        ? signal.name
                        : signal.sector || "—"}
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
                  <DriverColumn drivers={signal.drivers || []} />
                </TableCell>
                <TableCell className="text-zinc-300 font-mono text-sm">
                  {signal.price != null ? `$${formatPrice(signal.price)}` : "—"}
                </TableCell>
                <TableCell className="text-zinc-300 font-mono text-sm">
                  {signal.volume_ratio != null
                    ? `${signal.volume_ratio.toFixed(1)}x`
                    : "—"}
                </TableCell>
                <TableCell className="text-center">
                  {signal.sma_bullish === true ? (
                    <ArrowUp className="h-4 w-4 text-emerald-400 mx-auto" />
                  ) : signal.sma_bullish === false ? (
                    <ArrowDown className="h-4 w-4 text-rose-400 mx-auto" />
                  ) : (
                    <span className="text-zinc-600 text-xs">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="text-xs text-zinc-600">
        Showing {sorted.length} signals · Last updated{" "}
        {new Date().toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })}
      </div>
    </div>
  );
}
