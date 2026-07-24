import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
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
          <StatCard
            label="outlet/wire"
            value={st.sources_with_outlet_domain ?? "—"}
            sub={`${st.sources_with_wire_id ?? 0} with wire_id`}
          />
          <StatCard
            label="geo"
            value={st.sources_with_geo ?? "—"}
            sub={`${st.observations_with_geo ?? 0} obs · ${st.entities_with_country ?? 0} ents w/ country`}
          />
          <StatCard
            label="license"
            value={st.sources_with_license ?? "—"}
            sub={
              st.license_counts
                ? Object.entries(st.license_counts)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 2)
                    .map(([k, n]) => `${k}×${n}`)
                    .join(" · ") || "no licenses declared"
                : "coverage"
            }
          />
          <StatCard
            label="documents"
            value={st.document_ids_referenced ?? st.documents_total ?? "—"}
            sub={`${st.documents_total ?? 0} full · ${st.observations_with_document_id ?? 0} obs · ${st.observations_with_char_span ?? 0} spans${
              st.observations_with_char_span_auto
                ? ` (${st.observations_with_char_span_auto} auto)`
                : ""
            }`}
          />
        </div>
      )}

      {st && <ProvenanceQualityPanel stats={st} />}

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

/** Document / char_span coverage quality panel (engine 0.1.27+; deep-links 0.1.29+). */
function ProvenanceQualityPanel({ stats }: { stats: import("../api").CorpusStats }) {
  const nObs = Number(stats.counts?.observations ?? 0);
  const withDoc = stats.observations_with_document_id ?? 0;
  const withSpan = stats.observations_with_char_span ?? 0;
  const autoSpan = stats.observations_with_char_span_auto ?? 0;
  const missingSpan = stats.observations_missing_char_span ?? Math.max(0, withDoc - withSpan);
  const docsTotal = stats.documents_total ?? 0;
  const docsText = stats.documents_with_text ?? docsTotal;
  const refs = stats.document_ids_referenced ?? 0;
  const spanRatio =
    typeof stats.char_span_ratio === "number"
      ? stats.char_span_ratio
      : nObs
        ? withSpan / nObs
        : 0;
  const docLinkRatio =
    typeof stats.document_link_ratio === "number"
      ? stats.document_link_ratio
      : nObs
        ? withDoc / nObs
        : 0;
  const textRatio = refs ? Math.min(1, docsText / Math.max(refs, 1)) : docsTotal ? 1 : 0;

  const rows: {
    label: string;
    ratio: number;
    detail: string;
    good: number;
    warn: number;
    to?: string;
    title?: string;
  }[] = [
    {
      label: "document_id link",
      ratio: docLinkRatio,
      detail: `${withDoc}/${nObs || "—"} observations`,
      good: 0.8,
      warn: 0.4,
      to: "/data?tab=observations&has_document_id=true",
      title: "Open observations that have a document_id",
    },
    {
      label: "char_span coverage",
      ratio: spanRatio,
      detail: `${withSpan}/${nObs || "—"} obs · ${autoSpan} auto · ${missingSpan} missing on doc`,
      good: 0.7,
      warn: 0.35,
      to:
        missingSpan > 0
          ? "/data?tab=observations&span=missing_on_doc"
          : "/data?tab=observations&span=with",
      title:
        missingSpan > 0
          ? "Open observations with document_id but no char_span"
          : "Open observations with char_span",
    },
    {
      label: "documents with text",
      ratio: textRatio,
      detail: `${docsText} with text · ${docsTotal} full rows · ${refs} referenced`,
      good: 0.9,
      warn: 0.5,
      to: "/data?tab=documents",
      title: "Open documents tab in Data Explorer",
    },
  ];

  return (
    <div
      style={{
        border: "1px solid #d0d7de",
        borderRadius: 8,
        padding: "12px 14px",
        margin: "0 0 16px",
        background: "#ffffff",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
        <b style={{ fontSize: 13 }}>Provenance quality</b>
        <span style={{ fontSize: 11, color: "#8c959f" }}>
          documents · char_span · GET /api/stats
        </span>
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {rows.map((r) => (
          <CoverageBar key={r.label} {...r} />
        ))}
      </div>
      <p style={{ margin: "10px 0 0", fontSize: 11, color: "#57606a" }}>
        Improve span coverage with adapter <code>ensure_documents</code> and progressive
        char_span align; lint with <code>--require-char-spans</code> /{" "}
        <code>--min-char-span-ratio</code>. Drill into gaps via{" "}
        <Link
          to="/data?tab=observations&span=missing_on_doc"
          style={{ color: "#cf222e", fontWeight: 600 }}
          title="Observations with document_id but no char_span"
        >
          missing on doc
        </Link>{" "}
        (<code>/data?tab=observations&amp;span=missing_on_doc</code>
        {missingSpan > 0 ? ` · ${missingSpan} rows` : ""}).
      </p>
    </div>
  );
}

function CoverageBar({
  label,
  ratio,
  detail,
  good,
  warn,
  to,
  title,
}: {
  label: string;
  ratio: number;
  detail: string;
  good: number;
  warn: number;
  to?: string;
  title?: string;
}) {
  const pct = Math.max(0, Math.min(100, Math.round(ratio * 100)));
  const color =
    ratio >= good ? "#1a7f37" : ratio >= warn ? "#9a6700" : ratio > 0 ? "#cf222e" : "#8c959f";
  const bg =
    ratio >= good ? "#dafbe1" : ratio >= warn ? "#fff8c5" : ratio > 0 ? "#ffebe9" : "#eaeef2";
  const labelNode = to ? (
    <Link to={to} title={title || label} style={{ color: "inherit", textDecoration: "none" }}>
      <b style={{ borderBottom: "1px dashed #0969da" }}>{label}</b>
    </Link>
  ) : (
    <b>{label}</b>
  );
  const barInner = (
    <div
      style={{
        width: `${pct}%`,
        height: "100%",
        background: color,
        borderRadius: 4,
        transition: "width 0.2s ease",
      }}
    />
  );
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
        <span>
          {labelNode} <span style={{ color: "#57606a" }}>{detail}</span>
        </span>
        <span style={{ fontWeight: 700, color }}>{pct}%</span>
      </div>
      <div
        style={{
          height: 8,
          borderRadius: 4,
          background: "#eaeef2",
          overflow: "hidden",
        }}
        title={title || `${label}: ${pct}%`}
      >
        {to ? (
          <Link
            to={to}
            title={title || `${label}: ${pct}%`}
            style={{ display: "block", width: "100%", height: "100%", textDecoration: "none" }}
          >
            {barInner}
          </Link>
        ) : (
          barInner
        )}
      </div>
      <div
        style={{
          display: "inline-block",
          marginTop: 4,
          fontSize: 10,
          fontWeight: 600,
          color,
          background: bg,
          borderRadius: 8,
          padding: "0 6px",
        }}
      >
        {ratio >= good ? "good" : ratio >= warn ? "fair" : ratio > 0 ? "low" : "empty"}
      </div>
    </div>
  );
}
