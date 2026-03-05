"use client";

interface TechnicalChartProps {
  symbol: string;
}

export function TechnicalChart({ symbol }: TechnicalChartProps) {
  return (
    <div className="flex h-64 items-center justify-center text-muted-foreground">
      Chart for {symbol.toUpperCase()} will render here with Recharts.
    </div>
  );
}
