import { memo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface ScoreCardProps {
  title: string;
  value: string;
  description?: string;
  loading?: boolean;
}

export const ScoreCard = memo(function ScoreCard({ title, value, description, loading }: ScoreCardProps) {
  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardContent className="pt-6">
        <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
          {title}
        </p>
        {loading ? (
          <Skeleton className="mt-2 h-8 w-20 bg-zinc-800" />
        ) : (
          <p className="mt-2 text-2xl font-bold text-zinc-100">{value}</p>
        )}
        {description && (
          <p className="mt-1 text-xs text-zinc-500">{description}</p>
        )}
      </CardContent>
    </Card>
  );
});
