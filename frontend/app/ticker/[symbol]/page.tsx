import { redirect } from "next/navigation";

interface TickerPageProps {
  params: Promise<{ symbol: string }>;
}

export default async function TickerPage({ params }: TickerPageProps) {
  const { symbol } = await params;
  redirect(`/signal/${symbol}`);
}
