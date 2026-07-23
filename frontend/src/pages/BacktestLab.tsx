import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runBacktest, STATUS_COLORS } from "../api";

export function BacktestLab() {
  const [cutoffs, setCutoffs] = useState("2020-12-31, 2021-12-31, 2022-12-31, 2023-12-31, 2024-12-31, 2025-06-30");
  const bt = useMutation({ mutationFn: (cs: string[]) => runBacktest(cs) });

  return (
    <div>
      <h2>Backtest Lab</h2>
      <p style={{ fontSize: 13, color: "#57606a" }}>
        Runs the discovery engine at each historical cutoff using only data available then (leakage-checked),
        then measures early-discovery lead time and false positives against the full-data run.
      </p>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input value={cutoffs} onChange={(e) => setCutoffs(e.target.value)} style={{ flex: 1, padding: 6 }} />
        <button onClick={() => bt.mutate(cutoffs.split(",").map((s) => s.trim()))}>Run backtest</button>
      </div>
      {bt.isPending && <p>Running…</p>}
      {bt.data && (
        <div>
          <div style={{ display: "flex", gap: 20, marginBottom: 12, fontSize: 13 }}>
            <div><b>{bt.data.median_early_discovery_lead_days ?? "—"}</b> days median lead</div>
            <div><b>{bt.data.future_leakage_violations}</b> leakage violations</div>
            <div><b>{bt.data.false_positive_candidates?.length ?? 0}</b> false positives</div>
          </div>
          <table style={{ borderCollapse: "collapse", fontSize: 12, width: "100%" }}>
            <thead>
              <tr style={{ textAlign: "left", color: "#57606a", borderBottom: "1px solid #d0d7de" }}>
                <th style={{ padding: 6 }}>Final</th><th>Cluster</th><th>Lead (d)</th><th>History (year:status)</th>
              </tr>
            </thead>
            <tbody>
              {bt.data.tracks.map((t: any, i: number) => (
                <tr key={i} style={{ borderBottom: "1px solid #eaeef2" }}>
                  <td style={{ padding: 6 }}>
                    <span style={{ background: STATUS_COLORS[t.final_status] ?? "#57606a", color: "white", padding: "1px 6px", borderRadius: 10, fontSize: 10 }}>{t.final_status}</span>
                  </td>
                  <td>{t.name.slice(0, 24)}</td>
                  <td>{t.early_discovery_lead_days ?? "—"}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 11 }}>
                    {t.history.map((s: any) => `${s.cutoff.slice(0, 4)}:${s.status.slice(0, 4)}`).join(" ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
