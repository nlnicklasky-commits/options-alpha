import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ScannerPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Scanner</h2>
      <Card>
        <CardHeader>
          <CardTitle>Stock Screener</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            Screener filters and results will appear here.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
