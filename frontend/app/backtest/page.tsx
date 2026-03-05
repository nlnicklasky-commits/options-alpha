import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BacktestResults } from "@/components/backtest-results";

export default function BacktestPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Backtest</h2>
      <Card>
        <CardHeader>
          <CardTitle>Backtest Results</CardTitle>
        </CardHeader>
        <CardContent>
          <BacktestResults />
        </CardContent>
      </Card>
    </div>
  );
}
