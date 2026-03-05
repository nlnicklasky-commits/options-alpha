"use client";

import { useState, useEffect } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ScoreCard } from "@/components/score-card";
import { api } from "@/lib/api";
import { formatPrice, formatPercent } from "@/lib/format";
import type { JournalEntry } from "@/lib/types";
import { Plus, Pencil } from "lucide-react";

interface NewEntryForm {
  symbol: string;
  entry_date: string;
  entry_price: string;
  strike: string;
  expiry: string;
  contracts: string;
  notes: string;
  tags: string;
}

const emptyForm: NewEntryForm = {
  symbol: "",
  entry_date: new Date().toISOString().slice(0, 10),
  entry_price: "",
  strike: "",
  expiry: "",
  contracts: "1",
  notes: "",
  tags: "",
};

export function TradeJournal() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [newOpen, setNewOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);
  const [closingId, setClosingId] = useState<number | null>(null);
  const [form, setForm] = useState<NewEntryForm>(emptyForm);
  const [closeForm, setCloseForm] = useState({
    exit_date: new Date().toISOString().slice(0, 10),
    exit_price: "",
    exit_reason: "",
  });
  const [filter, setFilter] = useState<"all" | "open" | "closed">("all");

  const fetchEntries = () => {
    api<JournalEntry[]>("/api/journal")
      .then(setEntries)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchEntries();
  }, []);

  const handleCreate = async () => {
    try {
      await api("/api/journal", {
        method: "POST",
        body: JSON.stringify({
          symbol: form.symbol.toUpperCase(),
          entry_date: form.entry_date,
          entry_price: parseFloat(form.entry_price),
          strike: form.strike ? parseFloat(form.strike) : null,
          expiry: form.expiry || null,
          contracts: parseInt(form.contracts),
          notes: form.notes || null,
          tags: form.tags
            ? form.tags.split(",").map((t) => t.trim())
            : [],
        }),
      });
      setNewOpen(false);
      setForm(emptyForm);
      fetchEntries();
    } catch {
      // Error handled silently for now
    }
  };

  const handleClose = async () => {
    if (!closingId) return;
    try {
      await api(`/api/journal/${closingId}`, {
        method: "PATCH",
        body: JSON.stringify({
          exit_date: closeForm.exit_date,
          exit_price: parseFloat(closeForm.exit_price),
          exit_reason: closeForm.exit_reason || null,
        }),
      });
      setCloseOpen(false);
      setClosingId(null);
      fetchEntries();
    } catch {
      // Error handled silently
    }
  };

  const filtered = entries.filter((e) => {
    if (filter === "open") return e.status === "open";
    if (filter === "closed") return e.status === "closed";
    return true;
  });

  const closed = entries.filter((e) => e.status === "closed" && e.pnl != null);
  const totalPnl = closed.reduce((sum, e) => sum + (e.pnl ?? 0), 0);
  const wins = closed.filter((e) => (e.pnl ?? 0) > 0);
  const losses = closed.filter((e) => (e.pnl ?? 0) <= 0);
  const winRate = closed.length > 0 ? (wins.length / closed.length) * 100 : 0;
  const avgWin =
    wins.length > 0
      ? wins.reduce((s, e) => s + (e.pnl ?? 0), 0) / wins.length
      : 0;
  const avgLoss =
    losses.length > 0
      ? losses.reduce((s, e) => s + (e.pnl ?? 0), 0) / losses.length
      : 0;

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full bg-zinc-800" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-32 items-center justify-center text-zinc-500">
        Journal unavailable. Backend may be offline.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
        <ScoreCard title="Total P/L" value={`$${formatPrice(totalPnl)}`} />
        <ScoreCard title="Win Rate" value={formatPercent(winRate)} />
        <ScoreCard title="Avg Win" value={`$${formatPrice(avgWin)}`} />
        <ScoreCard title="Avg Loss" value={`$${formatPrice(avgLoss)}`} />
        <ScoreCard
          title="Best Trade"
          value={
            wins.length > 0
              ? `$${formatPrice(Math.max(...wins.map((w) => w.pnl ?? 0)))}`
              : "--"
          }
        />
        <ScoreCard
          title="Worst Trade"
          value={
            losses.length > 0
              ? `$${formatPrice(Math.min(...losses.map((l) => l.pnl ?? 0)))}`
              : "--"
          }
        />
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Select
            value={filter}
            onValueChange={(v) => setFilter(v as "all" | "open" | "closed")}
          >
            <SelectTrigger className="w-32 bg-zinc-800 border-zinc-700 text-zinc-100">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-800 border-zinc-700">
              <SelectItem value="all">All Trades</SelectItem>
              <SelectItem value="open">Open</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Dialog open={newOpen} onOpenChange={setNewOpen}>
          <DialogTrigger asChild>
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
              <Plus className="mr-2 h-4 w-4" /> New Entry
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
            <DialogHeader>
              <DialogTitle>New Trade Entry</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label className="text-zinc-400">Symbol</Label>
                <Input
                  value={form.symbol}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, symbol: e.target.value }))
                  }
                  placeholder="AAPL"
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div>
                <Label className="text-zinc-400">Entry Date</Label>
                <Input
                  type="date"
                  value={form.entry_date}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, entry_date: e.target.value }))
                  }
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div>
                <Label className="text-zinc-400">Entry Price</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.entry_price}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, entry_price: e.target.value }))
                  }
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div>
                <Label className="text-zinc-400">Strike</Label>
                <Input
                  type="number"
                  step="0.5"
                  value={form.strike}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, strike: e.target.value }))
                  }
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div>
                <Label className="text-zinc-400">Expiry</Label>
                <Input
                  type="date"
                  value={form.expiry}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, expiry: e.target.value }))
                  }
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div>
                <Label className="text-zinc-400">Contracts</Label>
                <Input
                  type="number"
                  min="1"
                  value={form.contracts}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, contracts: e.target.value }))
                  }
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div className="sm:col-span-2">
                <Label className="text-zinc-400">Notes</Label>
                <Input
                  value={form.notes}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, notes: e.target.value }))
                  }
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div className="sm:col-span-2">
                <Label className="text-zinc-400">Tags (comma separated)</Label>
                <Input
                  value={form.tags}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, tags: e.target.value }))
                  }
                  placeholder="breakout, momentum"
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
            </div>
            <Button
              onClick={handleCreate}
              className="mt-4 w-full bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Create Entry
            </Button>
          </DialogContent>
        </Dialog>
      </div>

      {/* Close trade dialog */}
      <Dialog open={closeOpen} onOpenChange={setCloseOpen}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
          <DialogHeader>
            <DialogTitle>Close Trade</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4">
            <div>
              <Label className="text-zinc-400">Exit Date</Label>
              <Input
                type="date"
                value={closeForm.exit_date}
                onChange={(e) =>
                  setCloseForm((f) => ({ ...f, exit_date: e.target.value }))
                }
                className="bg-zinc-800 border-zinc-700"
              />
            </div>
            <div>
              <Label className="text-zinc-400">Exit Price</Label>
              <Input
                type="number"
                step="0.01"
                value={closeForm.exit_price}
                onChange={(e) =>
                  setCloseForm((f) => ({ ...f, exit_price: e.target.value }))
                }
                className="bg-zinc-800 border-zinc-700"
              />
            </div>
            <div>
              <Label className="text-zinc-400">Exit Reason</Label>
              <Input
                value={closeForm.exit_reason}
                onChange={(e) =>
                  setCloseForm((f) => ({ ...f, exit_reason: e.target.value }))
                }
                placeholder="Target hit, stop loss, manual..."
                className="bg-zinc-800 border-zinc-700"
              />
            </div>
          </div>
          <Button
            onClick={handleClose}
            className="mt-4 w-full bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            Close Trade
          </Button>
        </DialogContent>
      </Dialog>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="flex h-32 items-center justify-center text-zinc-500">
          No trades recorded yet.
        </div>
      ) : (
        <div className="max-h-[600px] overflow-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800">
                <TableHead className="text-zinc-400">Date</TableHead>
                <TableHead className="text-zinc-400">Symbol</TableHead>
                <TableHead className="text-zinc-400">Entry $</TableHead>
                <TableHead className="text-zinc-400">Strike</TableHead>
                <TableHead className="text-zinc-400">Expiry</TableHead>
                <TableHead className="text-zinc-400">Exit $</TableHead>
                <TableHead className="text-zinc-400">P/L</TableHead>
                <TableHead className="text-zinc-400">Status</TableHead>
                <TableHead className="text-zinc-400">Tags</TableHead>
                <TableHead className="text-zinc-400"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((entry) => (
                <TableRow key={entry.id} className="border-zinc-800">
                  <TableCell className="text-zinc-300 font-mono text-xs">
                    {entry.entry_date}
                  </TableCell>
                  <TableCell className="font-bold text-zinc-100">
                    {entry.symbol}
                  </TableCell>
                  <TableCell className="text-zinc-300 font-mono">
                    ${formatPrice(entry.entry_price)}
                  </TableCell>
                  <TableCell className="text-zinc-300 font-mono">
                    {entry.strike != null ? `$${formatPrice(entry.strike)}` : "--"}
                  </TableCell>
                  <TableCell className="text-zinc-300 font-mono text-xs">
                    {entry.expiry || "--"}
                  </TableCell>
                  <TableCell className="text-zinc-300 font-mono">
                    {entry.exit_price != null
                      ? `$${formatPrice(entry.exit_price)}`
                      : "--"}
                  </TableCell>
                  <TableCell
                    className={`font-mono font-bold ${
                      entry.pnl != null
                        ? entry.pnl >= 0
                          ? "text-emerald-400"
                          : "text-rose-400"
                        : "text-zinc-500"
                    }`}
                  >
                    {entry.pnl != null ? `$${formatPrice(entry.pnl)}` : "--"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={entry.status === "open" ? "default" : "secondary"}
                      className={
                        entry.status === "open"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-zinc-700 text-zinc-300"
                      }
                    >
                      {entry.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {entry.tags.map((tag) => (
                        <Badge
                          key={tag}
                          variant="outline"
                          className="text-xs border-zinc-700 text-zinc-400"
                        >
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    {entry.status === "open" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-zinc-400 hover:text-zinc-100"
                        onClick={() => {
                          setClosingId(entry.id);
                          setCloseOpen(true);
                        }}
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
