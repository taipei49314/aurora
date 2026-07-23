import { useQuery } from "@tanstack/react-query";
import { useCurrentRun } from "../useRun";
import { STATUS_COLORS, Hypothesis, getStats } from "../api";

function Badge({ status }: { status: string }) {
  return (
    <span
      style={{
        background: STATUS_COLORS[status] ?? "#57606a",
        color: "white",
        padding: "2px 8px",
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      {status}
    </span>
  );
}

function counts(hyps: Hypothesis[]) {
  const c: Record<string, number> = {};
  for (const h of hyps) c[h.status] = (c[h.status] ?? 0) + 1;
  return c;
}

export function Dashboard() {
  const { runs, hyps } = useCurrentRun();
  const stats = useQuery({ queryKey: ["stats"], queryFn: getStats, staleTime: 30_000 });

  if (runs.isError) {
    return (
      <p style={{ color: "#cf222e" }}>
        API not reachable — run <code>make api</code>.
      </p>
    );
  }
  if (!hyps.data) return <p>Loading…</p>;
  const c = counts(hyps.data);
  const run = runs.data![0];
  const st = stats.data;

  return (
    <div>
      <h2>Latest research run</h2>
      <p style={{ color: "#57606a", fontSize: 13 }}>
        run {run.run_id} · cutoff {run.cutoff_date ?? "none (full corpus)"} · {run.n_hypotheses}{" "}
        hypotheses · reproducible ✔
      </p>

      {st && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
            gap: 10,
            margin: "12px 0 16px",
          }}
        >
          <StatCard label="entities" value={st.entities_total} sub={`${st.entities_with_external_ids} with external_ids`} />
          <StatCard label="sources" value={st.counts?.sources ?? "—"} sub={tierLine(st.reliability_tier_counts)} />
          <StatCard label="observations" value={st.counts?.observations ?? "—"} sub={`${Object.keys(st.observation_type_counts || {}).length} types`} />
          <StatCard
            label="independent"
            value={st.counts?.independent_source_count ?? "—"}
            sub={`of ${st.counts?.raw_source_count ?? "—"} raw`}
          />
          <StatCard
            label="family_id"
            value={st.sources_with_family_id ?? "—"}
            sub={`of ${st.sources_total ?? st.counts?.sources ?? "—"} sources`}
          />
          <StatCard
            label="event_date"
            value={st.sources_with_event_date ?? "—"}
            sub="dual-date coverage"
          />
          <StatCard
            label="event_id"
            value={st.unique_event_ids ?? "—"}
            sub={`${st.observations_with_event_id ?? 0} obs tagged`}
          />
        </div>
      )}

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
            <th style={{ padding: 6 }}>Status</th>
            <th>Name</th>
            <th style={{ textAlign: "right" }}>Overall</th>
            <th style={{ textAlign: "right" }}>Hype</th>
            <th style={{ textAlign: "right" }}>Contra</th>
            <th style={{ textAlign: "right" }}>DQ</th>
            <th style={{ textAlign: "right" }}>Sim</th>
          </tr>
        </thead>
        <tbody>
          {hyps.data.map((h) => (
            <tr key={h.hypothesis_id} style={{ borderBottom: "1px solid #eaeef2" }}>
              <td style={{ padding: 6 }}>
                <Badge status={h.status} />
              </td>
              <td>{h.human_name ?? h.generated_name}</td>
              <td style={{ textAlign: "right", fontWeight: 700 }}>{h.overall_score.toFixed(1)}</td>
              <td style={{ textAlign: "right" }}>{h.hype_risk_score.toFixed(0)}</td>
              <td style={{ textAlign: "right" }}>{h.contradiction_score.toFixed(0)}</td>
              <td style={{ textAlign: "right" }}>{(h.data_quality_penalty ?? 0).toFixed(0)}</td>
              <td style={{ textAlign: "right" }}>
                {(h.existing_industry_similarity?.similarity ?? 0).toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div style={{ border: "1px solid #d0d7de", borderRadius: 8, padding: "10px 12px", background: "#f6f8fa" }}>
      <div style={{ fontSize: 11, color: "#57606a", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "#8c959f" }}>{sub}</div>}
    </div>
  );
}

function tierLine(tiers?: Record<string, number>) {
  if (!tiers || !Object.keys(tiers).length) return "tiers —";
  return Object.entries(tiers)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}:${v}`)
    .join(" ");
}
