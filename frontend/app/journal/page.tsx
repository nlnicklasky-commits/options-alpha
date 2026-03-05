"use client";

import { TradeJournal } from "@/components/trade-journal";

export default function JournalPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight text-zinc-100">
        Trade Journal
      </h2>
      <TradeJournal />
    </div>
  );
}
