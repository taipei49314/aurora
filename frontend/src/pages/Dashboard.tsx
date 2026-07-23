import { useCurrentRun } from "../useRun";
import { STATUS_COLORS, Hypothesis } from "../api";

function Badge({ status }: { status: string }) {
  return (
    <span style={{ background: STATUS_COLORS[status] ?? "#57606a", color: "white",
      padding: "2px 8px", borderRadius: 12, fontSize: 11, fontWeight: 600 }}>{status}</span>
  );
}

function counts(hyps: Hypothesis[]) {
  const c: Record<string, number> = {};
  for (const h of hyps) c[h.status] = (c[h.status] ?? 0) + 1;
  return c;
}

export function Dashboard() {
  const { runs, hyps } = useCurrentRun();
  if (runs.isError) return <p style={{ color: "#cf222e" }}>API not reachable — run <code>make api</code>.</p>;
  if (!hyps.data) return <p>Loading…</p>;
  const c = counts(hyps.data);
  const run = runs.data![0];
  return (
    <div>
      <h2>Latest research run</h2>
      <p style={{ color: "#57606a", fontSize: 13 }}>
        run {run.run_id} · cutoff {run.cutoff_date ?? "none (full corpus)"} · {run.n_hypotheses} hypotheses · reproducible ✔
      </p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", margin: "12px 0 20px" }}>
        {Object.entries(c).map(([s, n]) => (
          <div key={s} style={{ border: "1px solid #d0d7de", borderRadius: 8, padding: "8px 12px" }}>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{n}</div>
            <Badge status={s} />
          </div>
        ))}
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#57606a", borderBottom: "1px solid #d0d7de" }}>
            <th style={{ padding: 6 }}>Status</th><th>Name</th>
            <th style={{ textAlign: "right" }}>Overall</th>
            <th style={{ textAlign: "right" }}>Hype</th>
            <th style={{ textAlign: "right" }}>Contra</th>
            <th style={{ textAlign: "right" }}>Sim</th>
          </tr>
        </thead>
        <tbody>
          {hyps.data.map((h) => (
            <tr key={h.hypothesis_id} style={{ borderBottom: "1px solid #eaeef2" }}>
              <td style={{ padding: 6 }}><Badge status={h.status} /></td>
              <td>{h.human_name ?? h.generated_name}</td>
              <td style={{ textAlign: "right", fontWeight: 700 }}>{h.overall_score.toFixed(1)}</td>
              <td style={{ textAlign: "right" }}>{h.hype_risk_score.toFixed(0)}</td>
              <td style={{ textAlign: "right" }}>{h.contradiction_score.toFixed(0)}</td>
              <td style={{ textAlign: "right" }}>{(h.existing_industry_similarity?.similarity ?? 0).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
