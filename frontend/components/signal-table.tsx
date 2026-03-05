import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function SignalTable() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Symbol</TableHead>
          <TableHead>Score</TableHead>
          <TableHead>Breakout Prob</TableHead>
          <TableHead>Pattern</TableHead>
          <TableHead>Options Score</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell colSpan={5} className="text-center text-muted-foreground">
            No signals yet. Run the pipeline to generate signals.
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  );
}
