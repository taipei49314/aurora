import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { createRun, getDivergence } from "../api";
import { useCurrentRun } from "../useRun";

export function RunComparison() {
  const { runId } = useCurrentRun();
  const [cutoff, setCutoff] = useState("2022-12-31");
  const [result, setResult] = useState<any>(null);

  const compare = useMutation({
    mutationFn: async () => {
      const other = await createRun(cutoff);
      return getDivergence(runId!, other.run_id);
    },
    onSuccess: setResult,
  });

  return (
    <div>
      <h2>Run Comparison — first divergence</h2>
      <p style={{ fontSize: 13, color: "#57606a" }}>
        Creates a cutoff run and finds the <b>first explainable stage</b> where it diverges from the full-data
        run — never just "scores differ".
      </p>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <span style={{ fontSize: 13, alignSelf: "center" }}>Compare full run vs cutoff:</span>
        <input value={cutoff} onChange={(e) => setCutoff(e.target.value)} style={{ padding: 6 }} />
        <button onClick={() => compare.mutate()} disabled={!runId}>Compare</button>
      </div>
      {compare.isPending && <p>Comparing…</p>}
      {result && (
        <div style={{ border: "1px solid #d0d7de", borderRadius: 8, padding: 14, fontSize: 13 }}>
          <div><b>First divergence stage:</b> {result.first_divergence_stage ?? "none (identical)"}</div>
          {result.changed_input && <div><b>Changed input:</b> {result.changed_input}</div>}
          {result.affected_entities?.length > 0 &&
            <div><b>Affected entities:</b> {result.affected_entities.join(", ")}</div>}
          {result.detail && (
            <div style={{ marginTop: 8 }}>
              <div>{result.detail.status_changes?.length ?? 0} status changes · {result.detail.score_changes?.length ?? 0} score changes</div>
              <div>{result.detail.clusters_added?.length ?? 0} clusters added · {result.detail.clusters_removed?.length ?? 0} removed</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
