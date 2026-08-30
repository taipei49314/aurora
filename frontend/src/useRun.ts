import { useQuery } from "@tanstack/react-query";
import { getRuns, getHypotheses } from "./api";

// Shared hook: the current (latest) run and its hypotheses.
export function useCurrentRun() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: getRuns });
  const incompatibleBackend =
    runs.isSuccess &&
    (runs.data ?? []).some(
      (run) =>
        typeof run.is_active !== "boolean" ||
        typeof run.is_current_snapshot !== "boolean" ||
        typeof run.snapshot_id !== "string" ||
        typeof run.input_manifest_hash !== "string",
    );
  const currentRun =
    incompatibleBackend
      ? undefined
      : runs.data?.find((run) => run.is_active && run.is_current_snapshot) ??
        runs.data?.find((run) => run.is_current_snapshot);
  const runId = currentRun?.run_id;
  const hyps = useQuery({
    queryKey: ["hyps", runId],
    queryFn: () => getHypotheses(runId!),
    enabled: !!runId,
  });
  return { runId, currentRun, incompatibleBackend, runs, hyps };
}
