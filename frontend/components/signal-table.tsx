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
import { api } from "@/lib/api";
import { formatPrice, formatScore, formatPercent, scoreColor } from "@/lib/format";
import type { Signal } from "@/lib/types";
import { ArrowUpDown } from "lucide-react";

type SortKey = "composite_score" | "symbol" | "breakout_probability" | "iv_rank" | "price" | "volume_ratio";

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

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <TableHead
      className="cursor-pointer select-none text-zinc-400 hover:text-zinc-200"
      onClick={() => handleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown className="h-3 w-3" />
      </span>
    </TableHead>
  );

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full bg-zinc-800" />
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
          <SortHeader label="Symbol" field="symbol" />
          <SortHeader label="Score" field="composite_score" />
          <TableHead className="text-zinc-400">Pattern</TableHead>
          <SortHeader label="IV Rank" field="iv_rank" />
          <SortHeader label="Price" field="price" />
          <SortHeader label="Vol Ratio" field="volume_ratio" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((signal, i) => (
          <TableRow
            key={signal.symbol}
            className="border-zinc-800 cursor-pointer hover:bg-zinc-800/50"
            onClick={() => router.push(`/ticker/${signal.symbol.toLowerCase()}`)}
          >
            <TableCell className="text-zinc-500 font-mono text-xs">
              {i + 1}
            </TableCell>
            <TableCell className="font-bold text-zinc-100">
              {signal.symbol}
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
              {signal.iv_rank != null ? formatPercent(signal.iv_rank) : "--"}
            </TableCell>
            <TableCell className="font-mono text-zinc-300">
              ${formatPrice(signal.price)}
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
  );
}
