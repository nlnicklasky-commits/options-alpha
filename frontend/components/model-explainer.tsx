"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChevronDown, ChevronUp, Brain, BarChart3, TrendingUp, Activity } from "lucide-react";

const sections = [
  {
    id: "how-it-works",
    icon: Brain,
    title: "How the Model Works",
    content:
      "Options Alpha uses an ensemble of three machine learning models — XGBoost, LightGBM, and Random Forest — combined through a Logistic Regression meta-learner. Each model independently scores every stock in the universe, then the meta-learner weights their predictions to produce a single composite score from 0 to 100. Higher scores indicate stronger bullish setups with better risk/reward profiles.",
  },
  {
    id: "composite-score",
    icon: BarChart3,
    title: "Composite Score (0–100)",
    content:
      "The headline number for each signal. It blends predictions from all three models into a single confidence metric. Scores above 80 represent high-conviction opportunities where multiple models strongly agree. Scores between 60–80 are moderate-conviction setups worth monitoring. Below 60, the models see weaker or conflicting signals.",
  },
  {
    id: "features",
    icon: TrendingUp,
    title: "What the Model Looks At",
    content:
      "The model analyzes 82+ technical indicators across 8 categories: trend (SMA crossovers, ADX), momentum (RSI, MACD, Stochastic), volume (OBV, volume ratio), volatility (Bollinger Bands, ATR), options flow (IV rank, put/call ratio), and 13 chart pattern detectors (cup & handle, head & shoulders, wedges, etc.). Each feature contributes differently depending on current market conditions.",
  },
  {
    id: "metrics",
    icon: Activity,
    title: "Key Metrics Explained",
    content: null, // Special rendering below
  },
];

const metricDefinitions = [
  {
    term: "Breakout Probability",
    definition:
      "The model's estimated likelihood (0–100%) that this stock will break out above recent resistance within the next 5–10 trading days.",
  },
  {
    term: "IV Rank",
    definition:
      "Implied Volatility Rank compares current IV to the past year's range. High IV Rank (>50%) means options are relatively expensive — good for selling premium. Low IV Rank means options are cheap — better for buying.",
  },
  {
    term: "Volume Ratio",
    definition:
      "Today's volume divided by the 30-day average. Values above 1.5× suggest unusual activity that often precedes significant moves. The model weights this heavily.",
  },
  {
    term: "Pattern",
    definition:
      "The dominant chart pattern detected by the pattern recognition engine. Patterns like cup & handle or ascending triangle are typically bullish. The confidence score (0–100) is factored into the composite score.",
  },
  {
    term: "SMA Bullish",
    definition:
      "Whether the 50-day Simple Moving Average is above the 200-day SMA (a \"golden cross\" condition). This confirms the stock is in a medium-term uptrend.",
  },
  {
    term: "Market Regime",
    definition:
      "Classified as BULL, BEAR, or CHOPPY based on VIX levels, breadth indicators (advance/decline ratio, % above 200 SMA), and new highs vs. new lows. The model adjusts signal thresholds based on the current regime.",
  },
];

export function ModelExplainer() {
  const [expanded, setExpanded] = useState<string | null>(null);

  const toggle = (id: string) =>
    setExpanded((prev) => (prev === id ? null : id));

  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardHeader>
        <CardTitle className="text-zinc-100 flex items-center gap-2">
          <Brain className="h-5 w-5 text-emerald-400" />
          Understanding the Signals
        </CardTitle>
        <p className="text-sm text-zinc-500 mt-1">
          How Options Alpha scores stocks and what the numbers mean
        </p>
      </CardHeader>
      <CardContent className="space-y-1">
        {sections.map(({ id, icon: Icon, title, content }) => {
          const isOpen = expanded === id;
          return (
            <div key={id} className="border border-zinc-800 rounded-lg overflow-hidden">
              <button
                onClick={() => toggle(id)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-zinc-800/50 transition-colors"
              >
                <Icon className="h-4 w-4 text-zinc-400 shrink-0" />
                <span className="flex-1 text-sm font-medium text-zinc-200">
                  {title}
                </span>
                {isOpen ? (
                  <ChevronUp className="h-4 w-4 text-zinc-500" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-zinc-500" />
                )}
              </button>
              {isOpen && (
                <div className="px-4 pb-4 pt-0">
                  {content ? (
                    <p className="text-sm text-zinc-400 leading-relaxed pl-7">
                      {content}
                    </p>
                  ) : (
                    <dl className="space-y-3 pl-7">
                      {metricDefinitions.map(({ term, definition }) => (
                        <div key={term}>
                          <dt className="text-sm font-medium text-zinc-300">
                            {term}
                          </dt>
                          <dd className="text-sm text-zinc-500 mt-0.5 leading-relaxed">
                            {definition}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
