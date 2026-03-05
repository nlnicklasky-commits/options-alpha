import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreCard } from "@/components/score-card";
import { SignalTable } from "@/components/signal-table";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <ScoreCard title="Active Signals" value="--" />
        <ScoreCard title="Win Rate" value="--" />
        <ScoreCard title="Avg Return" value="--" />
        <ScoreCard title="Model Version" value="--" />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Top Signals</CardTitle>
        </CardHeader>
        <CardContent>
          <SignalTable />
        </CardContent>
      </Card>
    </div>
  );
}
