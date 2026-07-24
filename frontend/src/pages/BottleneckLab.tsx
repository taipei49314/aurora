import { Link } from "react-router-dom";
import { useCurrentRun } from "../useRun";

// Compares bottleneck candidates across every hypothesis that has them.
export function BottleneckLab() {
  const { hyps } = useCurrentRun();
  if (!hyps.data) return <p>Loading…</p>;
  const rows: {
    hypothesis_id: string;
    cluster: string;
    status: string;
    entity_id: string;
    bottleneck_score: number;
    centrality: number;
    substitutability: number;
    supplier_concentration: number;
    lead_time: number;
    capacity_constraint: number;
    cross_cluster_dependency: number;
    failure_impact: number;
  }[] = [];
  for (const h of hyps.data) {
    for (const b of h.score_explanation?.bottlenecks ?? []) {
      rows.push({
        hypothesis_id: h.hypothesis_id,
        cluster: h.human_name ?? h.generated_name,
        status: h.status,
        ...b,
      });
    }
  }
  rows.sort((a, b) => b.bottleneck_score - a.bottleneck_score);

  const cols = [
    "bottleneck_score",
    "centrality",
    "substitutability",
    "supplier_concentration",
    "lead_time",
    "capacity_constraint",
    "cross_cluster_dependency",
    "failure_impact",
  ] as const;

  return (
    <div>
      <h2>Bottleneck Lab</h2>
      <p style={{ fontSize: 13, color: "#57606a" }}>
        Ranked by structural criticality — never by company size or news volume. A small, rarely-mentioned
        supplier on many dependency paths outranks large integrators. Cluster names open Hypothesis Explorer
        with the same <code>?id=</code>.
      </p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 12, minWidth: 800 }}>
          <thead>
            <tr style={{ textAlign: "right", color: "#57606a", borderBottom: "1px solid #d0d7de" }}>
              <th style={{ textAlign: "left", padding: 6 }}>Cluster</th>
              <th style={{ textAlign: "left" }}>Entity</th>
              {cols.map((c) => (
                <th key={c} style={{ padding: 6 }}>
                  {c.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 20).map((r, i) => {
              const explorerHref = `/hypotheses?status=${encodeURIComponent(r.status)}&id=${encodeURIComponent(r.hypothesis_id)}`;
              const mapHref = `/map?id=${encodeURIComponent(r.hypothesis_id)}`;
              return (
                <tr key={`${r.hypothesis_id}-${r.entity_id}-${i}`} style={{ borderBottom: "1px solid #eaeef2" }}>
                  <td style={{ padding: 6, maxWidth: 200 }}>
                    <Link
                      to={explorerHref}
                      title="Open hypothesis in Explorer"
                      style={{ color: "#0969da", textDecoration: "none", fontWeight: 600 }}
                    >
                      {r.cluster.slice(0, 28)}
                      <span style={{ marginLeft: 3, fontSize: 10 }} aria-hidden>
                        ↗
                      </span>
                    </Link>
                    <div style={{ marginTop: 2 }}>
                      <Link
                        to={mapHref}
                        title="Open Discovery Map for this cluster"
                        style={{ color: "#57606a", fontSize: 10, textDecoration: "none" }}
                      >
                        map ↗
                      </Link>
                      {" · "}
                      <Link
                        to={`/timeline?id=${encodeURIComponent(r.hypothesis_id)}`}
                        title="Open Timeline for this cluster"
                        style={{ color: "#57606a", fontSize: 10, textDecoration: "none" }}
                      >
                        timeline ↗
                      </Link>
                    </div>
                  </td>
                  <td title={r.entity_id}>
                    <Link
                      to={`/data?tab=entities&q=${encodeURIComponent(r.entity_id)}`}
                      title="Search entity in Data Explorer"
                      style={{ color: "#0969da", textDecoration: "none", fontFamily: "ui-monospace, monospace" }}
                    >
                      {r.entity_id.slice(0, 12)}
                    </Link>
                  </td>
                  {cols.map((c) => (
                    <td
                      key={c}
                      style={{
                        textAlign: "right",
                        padding: 6,
                        fontWeight: c === "bottleneck_score" ? 700 : 400,
                      }}
                    >
                      {Number(r[c]).toFixed(2)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
