import { useQuery } from "@tanstack/react-query";
import { getRuns, getHypotheses } from "./api";

// Shared hook: the current (latest) run and its hypotheses.
export function useCurrentRun() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: getRuns });
  const runId = runs.data?.[0]?.run_id;
  const hyps = useQuery({
    queryKey: ["hyps", runId],
    queryFn: () => getHypotheses(runId!),
    enabled: !!runId,
  });
  return { runId, runs, hyps };
}
