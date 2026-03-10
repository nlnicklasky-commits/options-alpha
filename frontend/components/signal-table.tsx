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
import { ArrowUpDown, TrendingUp, Info, Settings2, Check } from "lucide-react";

/* ────────────────────── Column definitions ────────────────────── */

interface ColumnDef {
  key: string;
  label: string;
  tooltip: string;
  sortable: boolean;
  defaultVisible: boolean;
  group: string;
  render: (signal: Signal) => React.ReactNode;
}

function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const pct = Math.min(Math.max((score / max) * 100, 0), 100);
  const color =
    score >= 80 ? "bg-emerald-400" : score >= 60 ? "bg-amber-400" : "bg-rose-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-zinc-800">
        <div className={`h-1.5 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`font-mono text-sm font-bold ${scoreColor(score)}`}>{formatScore(score)}</span>
    </div>
  );
}

function MiniBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  const color = pct >= 70 ? "bg-emerald-400" : pct >= 40 ? "bg-amber-400" : "bg-rose-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-10 rounded-full bg-zinc-800">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs text-zinc-300">{formatScore(value)}</span>
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

const COLUMNS: ColumnDef[] = [
  // Core
  {
    key: "composite_score",
    label: "Score",
    tooltip: "Composite score (0–100) from the ensemble ML model. Higher = stronger bullish setup.",
    sortable: true,
    defaultVisible: true,
    group: "Core",
    render: (s) => <ScoreBar score={s.composite_score} />,
  },
  {
    key: "breakout_probability",
    label: "Breakout",
    tooltip: "Model-estimated probability this stock breaks out above resistance in 5–10 days.",
    sortable: true,
    defaultVisible: true,
    group: "Core",
    render: (s) => <BreakoutBadge probability={s.breakout_probability} />,
  },
  {
    key: "pattern",
    label: "Pattern",
    tooltip: "Dominant chart pattern detected (e.g., cup & handle, ascending triangle).",
    sortable: false,
    defaultVisible: true,
    group: "Core",
    render: (s) =>
      s.pattern ? (
        <span className="inline-flex items-center rounded-md bg-zinc-800 border border-zinc-700 px-2 py-0.5 text-xs text-zinc-300">
          {s.pattern}
        </span>
      ) : (
        <span className="text-zinc-600 text-xs">none</span>
      ),
  },
  {
    key: "price",
    label: "Price",
    tooltip: "Most recent closing price.",
    sortable: true,
    defaultVisible: true,
    group: "Core",
    render: (s) =>
      s.price != null ? (
        <span className="font-mono text-sm text-zinc-300">${formatPrice(s.price)}</span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  // Market Data
  {
    key: "iv_rank",
    label: "IV Rank",
    tooltip: "Implied Volatility Rank — how current IV compares to the past year. High = options are expensive.",
    sortable: true,
    defaultVisible: true,
    group: "Market Data",
    render: (s) =>
      s.iv_rank != null ? <MiniBar value={s.iv_rank} /> : <span className="text-zinc-600 text-xs">—</span>,
  },
  {
    key: "volume_ratio",
    label: "Vol Ratio",
    tooltip: "Today's volume vs. 30-day average. Above 1.5× suggests unusual activity.",
    sortable: true,
    defaultVisible: true,
    group: "Market Data",
    render: (s) =>
      s.volume_ratio != null ? (
        <span className={`font-mono text-sm ${s.volume_ratio >= 1.5 ? "text-emerald-400 font-bold" : "text-zinc-400"}`}>
          {s.volume_ratio.toFixed(1)}×
        </span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  {
    key: "sma_bullish",
    label: "SMA Trend",
    tooltip: "Whether the 50-day SMA is above the 200-day SMA (golden cross = bullish).",
    sortable: false,
    defaultVisible: false,
    group: "Market Data",
    render: (s) =>
      s.sma_bullish != null ? (
        <span className={`text-xs font-medium ${s.sma_bullish ? "text-emerald-400" : "text-rose-400"}`}>
          {s.sma_bullish ? "Bullish" : "Bearish"}
        </span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  // Sub-scores
  {
    key: "technical_score",
    label: "Technical",
    tooltip: "Technical analysis sub-score from the model (0–100).",
    sortable: true,
    defaultVisible: false,
    group: "Sub-Scores",
    render: (s) =>
      s.technical_score != null ? <MiniBar value={s.technical_score} /> : <span className="text-zinc-600 text-xs">—</span>,
  },
  {
    key: "momentum_score",
    label: "Momentum",
    tooltip: "Momentum sub-score based on RSI, MACD, Stochastic, etc. (0–100).",
    sortable: true,
    defaultVisible: false,
    group: "Sub-Scores",
    render: (s) =>
      s.momentum_score != null ? <MiniBar value={s.momentum_score} /> : <span className="text-zinc-600 text-xs">—</span>,
  },
  {
    key: "volume_score",
    label: "Volume Score",
    tooltip: "Volume analysis sub-score based on OBV, CMF, volume ratio (0–100).",
    sortable: true,
    defaultVisible: false,
    group: "Sub-Scores",
    render: (s) =>
      s.volume_score != null ? <MiniBar value={s.volume_score} /> : <span className="text-zinc-600 text-xs">—</span>,
  },
  {
    key: "pattern_score",
    label: "Pattern Score",
    tooltip: "Chart pattern sub-score — strength of detected patterns (0–100).",
    sortable: true,
    defaultVisible: false,
    group: "Sub-Scores",
    render: (s) =>
      s.pattern_score != null ? <MiniBar value={s.pattern_score} /> : <span className="text-zinc-600 text-xs">—</span>,
  },
  {
    key: "regime_score",
    label: "Regime Score",
    tooltip: "How well the signal aligns with the current market regime (0–100).",
    sortable: true,
    defaultVisible: false,
    group: "Sub-Scores",
    render: (s) =>
      s.regime_score != null ? <MiniBar value={s.regime_score} /> : <span className="text-zinc-600 text-xs">—</span>,
  },
  // Key Technicals
  {
    key: "rsi_14",
    label: "RSI(14)",
    tooltip: "Relative Strength Index (14-period). Above 70 = overbought, below 30 = oversold.",
    sortable: true,
    defaultVisible: false,
    group: "Technicals",
    render: (s) =>
      s.rsi_14 != null ? (
        <span className={`font-mono text-xs ${s.rsi_14 > 70 ? "text-rose-400" : s.rsi_14 < 30 ? "text-emerald-400" : "text-zinc-300"}`}>
          {s.rsi_14.toFixed(1)}
        </span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  {
    key: "adx_14",
    label: "ADX(14)",
    tooltip: "Average Directional Index — measures trend strength. Above 25 = strong trend.",
    sortable: true,
    defaultVisible: false,
    group: "Technicals",
    render: (s) =>
      s.adx_14 != null ? (
        <span className={`font-mono text-xs ${s.adx_14 > 25 ? "text-emerald-400" : "text-zinc-300"}`}>
          {s.adx_14.toFixed(1)}
        </span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  {
    key: "bb_pctb",
    label: "BB %B",
    tooltip: "Bollinger Band %B — position within the bands. >1 = above upper band, <0 = below lower.",
    sortable: true,
    defaultVisible: false,
    group: "Technicals",
    render: (s) =>
      s.bb_pctb != null ? (
        <span className="font-mono text-xs text-zinc-300">{(s.bb_pctb * 100).toFixed(0)}%</span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  // Trade Metrics
  {
    key: "expected_move_pct",
    label: "Exp. Move",
    tooltip: "Model's expected percentage move if breakout occurs.",
    sortable: true,
    defaultVisible: false,
    group: "Trade",
    render: (s) =>
      s.expected_move_pct != null ? (
        <span className="font-mono text-xs text-emerald-400">+{(s.expected_move_pct * 100).toFixed(1)}%</span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  {
    key: "confidence",
    label: "Confidence",
    tooltip: "Model's confidence in this signal (0–1).",
    sortable: true,
    defaultVisible: false,
    group: "Trade",
    render: (s) =>
      s.confidence != null ? (
        <span className="font-mono text-xs text-zinc-300">{(s.confidence * 100).toFixed(0)}%</span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  {
    key: "risk_reward_ratio",
    label: "R:R",
    tooltip: "Risk-reward ratio — potential reward divided by potential risk.",
    sortable: true,
    defaultVisible: false,
    group: "Trade",
    render: (s) =>
      s.risk_reward_ratio != null ? (
        <span className={`font-mono text-xs ${s.risk_reward_ratio >= 2 ? "text-emerald-400" : "text-zinc-300"}`}>
          {s.risk_reward_ratio.toFixed(1)}:1
        </span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
  {
    key: "sector",
    label: "Sector",
    tooltip: "GICS sector classification.",
    sortable: false,
    defaultVisible: false,
    group: "Info",
    render: (s) =>
      s.sector ? (
        <span className="text-xs text-zinc-400">{s.sector}</span>
      ) : (
        <span className="text-zinc-600 text-xs">—</span>
      ),
  },
];

/* ────────────────────── Column picker dropdown ────────────────────── */

function ColumnPicker({
  visible,
  onToggle,
}: {
  visible: Set<string>;
  onToggle: (key: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const groups = Array.from(new Set(COLUMNS.map((c) => c.group)));

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 transition-colors"
      >
        <Settings2 className="h-3.5 w-3.5" />
        Columns
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-lg border border-zinc-700 bg-zinc-900 shadow-xl overflow-hidden">
            {groups.map((group) => (
              <div key={group}>
                <div className="px-3 pt-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                  {group}
                </div>
                {COLUMNS.filter((c) => c.group === group).map((col) => (
                  <button
                    key={col.key}
                    onClick={() => onToggle(col.key)}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 transition-colors"
                  >
                    <span
                      className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                        visible.has(col.key)
                          ? "border-emerald-500 bg-emerald-500/20"
                          : "border-zinc-600"
                      }`}
                    >
                      {visible.has(col.key) && <Check className="h-3 w-3 text-emerald-400" />}
                    </span>
                    {col.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ────────────────────── Main table ────────────────────── */

type SortKey = string;

export function SignalTable() {
  const router = useRouter();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortAsc, setSortAsc] = useState(false);
  const [visibleCols, setVisibleCols] = useState<Set<string>>(
    () => new Set(COLUMNS.filter((c) => c.defaultVisible).map((c) => c.key))
  );

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

  const toggleCol = useCallback((key: string) => {
    setVisibleCols((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const sorted = [...signals].sort((a, b) => {
    const av = (a as unknown as Record<string, unknown>)[sortKey] ?? 0;
    const bv = (b as unknown as Record<string, unknown>)[sortKey] ?? 0;
    if (typeof av === "string" && typeof bv === "string") {
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return sortAsc ? Number(av) - Number(bv) : Number(bv) - Number(av);
  });

  const activeCols = COLUMNS.filter((c) => visibleCols.has(c.key));

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
    <div className="space-y-3">
      <div className="flex justify-end">
        <ColumnPicker visible={visibleCols} onToggle={toggleCol} />
      </div>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400 w-12">#</TableHead>
              <TableHead className="text-zinc-400 cursor-pointer" onClick={() => handleSort("symbol")}>
                <span className="inline-flex items-center gap-1">
                  Company <ArrowUpDown className="h-3 w-3" />
                </span>
              </TableHead>
              {activeCols.map((col) => (
                <TableHead
                  key={col.key}
                  className={`text-zinc-400 ${col.sortable ? "cursor-pointer hover:text-zinc-200" : ""}`}
                  onClick={col.sortable ? () => handleSort(col.key) : undefined}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {col.tooltip && (
                      <Tooltip content={col.tooltip}>
                        <Info className="h-3 w-3 text-zinc-600 hover:text-zinc-400" />
                      </Tooltip>
                    )}
                    {col.sortable && <ArrowUpDown className="h-3 w-3" />}
                  </span>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((signal, i) => (
              <TableRow
                key={signal.symbol}
                className="border-zinc-800 cursor-pointer hover:bg-zinc-800/50 transition-colors"
                onClick={() => router.push(`/ticker/${signal.symbol.toLowerCase()}`)}
              >
                <TableCell className="text-zinc-600 font-mono text-xs">{i + 1}</TableCell>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-bold text-zinc-100 text-sm">{signal.symbol}</span>
                    <span className="text-xs text-zinc-500 truncate max-w-[180px]">
                      {signal.name || signal.sector || "—"}
                    </span>
                  </div>
                </TableCell>
                {activeCols.map((col) => (
                  <TableCell key={col.key}>{col.render(signal)}</TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
