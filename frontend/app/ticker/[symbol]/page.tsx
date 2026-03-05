import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TechnicalChart } from "@/components/technical-chart";

interface TickerPageProps {
  params: Promise<{ symbol: string }>;
}

export default async function TickerPage({ params }: TickerPageProps) {
  const { symbol } = await params;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">
        {symbol.toUpperCase()}
      </h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Price Chart</CardTitle>
          </CardHeader>
          <CardContent>
            <TechnicalChart symbol={symbol} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Signal Details</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Signal and options data will appear here.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
