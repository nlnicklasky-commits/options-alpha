"use client";

import { useState, useEffect, memo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  ComposedChart,
  Bar,
  ReferenceLine,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";

interface PricePoint {
  date: string;
  close: number;
  volume: number;
  sma_50?: number;
  sma_200?: number;
  bb_upper?: number;
  bb_lower?: number;
}

interface TechnicalChartProps {
  symbol: string;
}

export const TechnicalChart = memo(function TechnicalChart({ symbol }: TechnicalChartProps) {
  const [data, setData] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<PricePoint[]>(`/api/score/${symbol}/chart`)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return <Skeleton className="h-80 w-full bg-zinc-800" />;
  }

  if (error || data.length === 0) {
    return (
      <div className="flex h-80 items-center justify-center text-zinc-500">
        Chart data unavailable for {symbol.toUpperCase()}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickFormatter={(v: string) => v.slice(5)}
            stroke="#3f3f46"
          />
          <YAxis
            domain={["auto", "auto"]}
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
          {data[0]?.bb_upper != null && (
            <Area
              dataKey="bb_upper"
              stroke="none"
              fill="#3f3f46"
              fillOpacity={0.3}
              type="monotone"
            />
          )}
          {data[0]?.bb_lower != null && (
            <Area
              dataKey="bb_lower"
              stroke="none"
              fill="#18181b"
              fillOpacity={1}
              type="monotone"
            />
          )}
          <Line
            type="monotone"
            dataKey="close"
            stroke="#f4f4f5"
            strokeWidth={1.5}
            dot={false}
          />
          {data[0]?.sma_50 != null && (
            <Line
              type="monotone"
              dataKey="sma_50"
              stroke="#34d399"
              strokeWidth={1}
              dot={false}
              strokeDasharray="4 2"
            />
          )}
          {data[0]?.sma_200 != null && (
            <Line
              type="monotone"
              dataKey="sma_200"
              stroke="#f59e0b"
              strokeWidth={1}
              dot={false}
              strokeDasharray="4 2"
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      <ResponsiveContainer width="100%" height={60}>
        <ComposedChart data={data}>
          <XAxis dataKey="date" hide />
          <YAxis hide />
          <Bar dataKey="volume" fill="#3f3f46" />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="flex gap-4 text-xs text-zinc-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-3 bg-zinc-100" /> Price
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-3 bg-emerald-400" style={{ borderTop: "1px dashed" }} /> SMA 50
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-3 bg-amber-400" style={{ borderTop: "1px dashed" }} /> SMA 200
        </span>
      </div>
    </div>
  );
});
