export interface DriverInfo {
  label: string;
  description: string;
  signal: string;
  category: "momentum" | "trend" | "volume" | "volatility" | "pattern" | "conviction" | "other";
}

export interface Signal {
  symbol: string;
  name: string | null;
  composite_score: number;
  breakout_probability: number;
  date: string | null;
  price: number | null;
  volume_ratio: number | null;
  sma_bullish: boolean | null;
  rsi_14: number | null;
  pattern: string | null;
  sector: string | null;
  drivers: DriverInfo[];
}

export interface SignalDetail extends Signal {
  adx_14: number | null;
  bb_pctb: number | null;
  component_scores: Record<string, number>;
  top_features: Array<{
    feature: string;
    importance: number;
    value: number | null;
  }>;
}

export interface RegimeData {
  regime: "BULL" | "BEAR" | "CHOPPY";
  vix: number;
  breadth: {
    advance_decline: number;
    pct_above_200sma: number;
    new_highs_lows: number;
  };
}

// Legacy interfaces for backward compatibility
export type ScoreDetail = SignalDetail;
export type FeatureDriver = SignalDetail["top_features"][0];

export interface BacktestRequest {
  name?: string;
  start_date: string;
  end_date: string;
  model_path?: string | null;
  entry_threshold?: number;
  target_pct?: number;
  stop_pct?: number;
  max_days?: number;
}

export interface BacktestStats {
  win_rate: number;
  avg_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  profit_factor: number;
  sortino_ratio: number;
  expectancy: number;
  avg_days_held: number;
  total_trades: number;
}

export interface EquityCurvePoint {
  date: string;
  cumulative_pnl: number;
}

export interface BacktestResponse {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  model_version: string | null;
  stats: BacktestStats;
  equity_curve: EquityCurvePoint[];
  results_by_regime: Record<string, { win_rate: number; count: number }>;
  results_by_score_bucket: Record<string, { win_rate: number; count: number }>;
  results_by_pattern: Record<string, { win_rate: number; count: number }>;
}

export interface BacktestTrade {
  id: number;
  stock_id: number;
  symbol: string | null;
  entry_date: string;
  exit_date: string | null;
  entry_price: number;
  exit_price: number | null;
  return_pct: number | null;
  signal_score: number | null;
  pattern_type: string | null;
  regime: string | null;
}

export interface JournalEntry {
  id: number;
  symbol: string;
  entry_date: string;
  entry_price: number;
  strike: number | null;
  expiry: string | null;
  contracts: number;
  exit_date: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  pnl: number | null;
  notes: string | null;
  tags: string[];
  status: "open" | "closed";
}

export type MarketRegime = "BULL" | "BEAR" | "CHOPPY";
