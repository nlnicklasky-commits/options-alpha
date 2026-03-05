import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TradeJournal } from "@/components/trade-journal";

export default function JournalPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Trade Journal</h2>
      <Card>
        <CardHeader>
          <CardTitle>Recent Trades</CardTitle>
        </CardHeader>
        <CardContent>
          <TradeJournal />
        </CardContent>
      </Card>
    </div>
  );
}
