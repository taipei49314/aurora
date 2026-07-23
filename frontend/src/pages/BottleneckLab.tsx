import { useCurrentRun } from "../useRun";

// Compares bottleneck candidates across every hypothesis that has them.
export function BottleneckLab() {
  const { hyps } = useCurrentRun();
  if (!hyps.data) return <p>Loading…</p>;
  const rows: any[] = [];
  for (const h of hyps.data) {
    for (const b of h.score_explanation?.bottlenecks ?? []) {
      rows.push({ cluster: h.generated_name, ...b });
    }
  }
  rows.sort((a, b) => b.bottleneck_score - a.bottleneck_score);

  const cols = ["bottleneck_score", "centrality", "substitutability", "supplier_concentration",
    "lead_time", "capacity_constraint", "cross_cluster_dependency", "failure_impact"];
  return (
    <div>
      <h2>Bottleneck Lab</h2>
      <p style={{ fontSize: 13, color: "#57606a" }}>
        Ranked by structural criticality — never by company size or news volume. A small, rarely-mentioned
        supplier on many dependency paths outranks large integrators.
      </p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 12, minWidth: 800 }}>
          <thead>
            <tr style={{ textAlign: "right", color: "#57606a", borderBottom: "1px solid #d0d7de" }}>
              <th style={{ textAlign: "left", padding: 6 }}>Cluster</th>
              <th style={{ textAlign: "left" }}>Entity</th>
              {cols.map((c) => <th key={c} style={{ padding: 6 }}>{c.replace(/_/g, " ")}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 20).map((r, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #eaeef2" }}>
                <td style={{ padding: 6 }}>{r.cluster.slice(0, 22)}</td>
                <td>{r.entity_id.slice(0, 10)}</td>
                {cols.map((c) => (
                  <td key={c} style={{ textAlign: "right", padding: 6,
                    fontWeight: c === "bottleneck_score" ? 700 : 400 }}>{Number(r[c]).toFixed(2)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
