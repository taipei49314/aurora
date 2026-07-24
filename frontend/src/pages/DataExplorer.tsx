import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getDocument,
  getDocuments,
  getEntities,
  getObservations,
  getSources,
  getStats,
  resolveEntity,
} from "../api";

type Tab = "entities" | "observations" | "sources" | "documents";
type Tier = "A" | "B" | "C" | "D";

const TIER_COLORS: Record<Tier, { bg: string; fg: string; label: string }> = {
  A: { bg: "#dafbe1", fg: "#1a7f37", label: "official / primary legal" },
  B: { bg: "#ddf4ff", fg: "#0969da", label: "peer-reviewed / technical" },
  C: { bg: "#fff8c5", fg: "#9a6700", label: "news / secondary" },
  D: { bg: "#ffebe9", fg: "#cf222e", label: "unverified / social" },
};

function formatExternalIds(row: any): string {
  const ids = row.external_ids;
  if (!Array.isArray(ids) || ids.length === 0) return "—";
  return ids
    .map((x: any) => `${x.system ?? "?"}:${x.id ?? "?"}`)
    .join(" · ");
}

function TierBadge({ tier }: { tier: string }) {
  const t = (tier || "C").toUpperCase() as Tier;
  const style = TIER_COLORS[t] ?? TIER_COLORS.C;
  return (
    <span
      title={style.label}
      style={{
        display: "inline-block",
        minWidth: 18,
        textAlign: "center",
        fontWeight: 700,
        fontSize: 11,
        padding: "1px 6px",
        borderRadius: 10,
        background: style.bg,
        color: style.fg,
      }}
    >
      {t}
    </span>
  );
}

function cellValue(tab: Tab, col: string, row: any): ReactNode {
  if (tab === "entities" && col === "external_ids") return formatExternalIds(row);
  if (tab === "sources" && col === "reliability_tier") {
    return <TierBadge tier={String(row.reliability_tier || "C")} />;
  }
  if (tab === "sources" && col === "independence_group") {
    return String(row.independence_group || "—");
  }
  if (tab === "sources" && col === "family_id") {
    return String(row.family_id || row.metadata?.family_id || "—");
  }
  if (tab === "sources" && (col === "event_date" || col === "published_at")) {
    return String(row[col] || (col === "event_date" ? row.metadata?.event_date : "") || "—");
  }
  if (col === "event_id") {
    return String(row.event_id || row.metadata?.event_id || "—");
  }
  if (col === "outlet_domain") {
    return String(row.outlet_domain || row.metadata?.outlet_domain || "—");
  }
  if (col === "wire_id") {
    return String(row.wire_id || row.metadata?.wire_id || "—");
  }
  if (col === "geo") {
    const g = row.geo || row.metadata?.geo;
    if (!g || (typeof g === "object" && !Object.keys(g).length)) return "—";
    if (typeof g === "object") {
      const parts = [g.country, g.region, g.city, g.jurisdiction, g.raw].filter(Boolean);
      return parts.length ? parts.join(" · ") : JSON.stringify(g);
    }
    return String(g);
  }
  if (col === "license") {
    return String(row.license || row.metadata?.license || "—");
  }
  if (col === "document_id") {
    return String(row.document_id || row.metadata?.document_id || "—");
  }
  if (col === "char_span") {
    const sp = row.char_span || row.metadata?.char_span;
    if (sp == null) return "—";
    const label =
      Array.isArray(sp) && sp.length >= 2
        ? `[${sp[0]}, ${sp[1]}]`
        : String(JSON.stringify(sp));
    if (row.metadata?.char_span_auto) {
      return (
        <span title="Auto-aligned from text_excerpt (engine 0.1.20+)">
          {label}{" "}
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#9a6700",
              background: "#fff8c5",
              borderRadius: 8,
              padding: "0 5px",
            }}
          >
            auto
          </span>
        </span>
      );
    }
    return label;
  }
  if (tab === "documents" && col === "stub") {
    return row.stub ? "stub" : "full";
  }
  if (tab === "documents" && col === "text") {
    const t = String(row.text || "");
    if (!t) return "—";
    return t.length > 80 ? `${t.slice(0, 80)}…` : t;
  }
  const v = row[col];
  if (v == null || v === "") return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function looksLikeResolveRef(s: string): boolean {
  const t = s.trim();
  if (!t) return false;
  if (t.toLowerCase().startsWith("ext:")) return true;
  // system:id with a single colon (lei:…, domain:…)
  if (t.split(":").length === 2 && !t.includes("://")) return true;
  return false;
}

export function DataExplorer() {
  const [tab, setTab] = useState<Tab>("entities");
  const [q, setQ] = useState("");
  const [tierFilter, setTierFilter] = useState<"" | Tier>("");
  const [sourceType, setSourceType] = useState("");
  const [entityType, setEntityType] = useState("");
  const [obsType, setObsType] = useState("");
  /** "" | "with" | "auto" | "none" | "missing_on_doc" — char_span filter (0.1.21+ / 0.1.28) */
  const [spanFilter, setSpanFilter] = useState<
    "" | "with" | "auto" | "none" | "missing_on_doc"
  >("");
  const [resolveRef, setResolveRef] = useState("");
  const [resolveStatus, setResolveStatus] = useState<string | null>(null);
  const [selected, setSelected] = useState<any | null>(null);

  const stats = useQuery({ queryKey: ["stats"], queryFn: getStats, staleTime: 30_000 });

  // Server-side filter for entities (?q= / ?entity_type=)
  const serverQ = tab === "entities" && q.trim() && !looksLikeResolveRef(q) ? q.trim() : undefined;
  const entities = useQuery({
    queryKey: ["entities", serverQ ?? "", entityType],
    queryFn: () => getEntities(serverQ, entityType || undefined),
    enabled: tab === "entities" || !!selected,
  });
  const observations = useQuery({
    queryKey: ["observations", q, obsType, spanFilter],
    queryFn: () =>
      getObservations({
        q: q.trim() || undefined,
        observation_type: obsType || undefined,
        has_char_span:
          spanFilter === "with" || spanFilter === "auto"
            ? true
            : spanFilter === "none"
              ? false
              : undefined,
        char_span_auto: spanFilter === "auto" ? true : undefined,
        missing_char_span: spanFilter === "missing_on_doc" ? true : undefined,
      }),
    enabled: tab === "observations",
  });
  const sources = useQuery({
    queryKey: ["sources", tierFilter, sourceType, q],
    queryFn: () =>
      getSources({
        reliability_tier: tierFilter || undefined,
        source_type: sourceType || undefined,
        q: q.trim() || undefined,
      }),
    enabled: tab === "sources",
  });
  const documents = useQuery({
    queryKey: ["documents", q],
    queryFn: () => getDocuments({ q: q.trim() || undefined, include_stubs: true }),
    enabled: tab === "documents",
  });

  const data =
    tab === "entities"
      ? entities.data
      : tab === "observations"
        ? observations.data
        : tab === "sources"
          ? sources.data
          : documents.data;
  const cols =
    tab === "entities"
      ? ["entity_type", "canonical_name", "country", "external_ids", "entity_id"]
      : tab === "observations"
        ? ["observation_type", "subject_entity", "observed_at", "document_id", "char_span", "geo", "event_id", "confidence", "observation_id"]
        : tab === "sources"
          ? ["source_type", "publisher", "reliability_tier", "license", "outlet_domain", "wire_id", "geo", "event_date", "published_at", "event_id", "family_id", "independence_group", "source_id"]
          : ["document_id", "title", "stub", "observation_count", "license", "source_id", "text"];

  // entities / sources / observations use server-side filters when possible
  const filtered = useMemo(() => {
    const rows = data ?? [];
    if (tab === "entities" && looksLikeResolveRef(q)) {
      const needle = q.trim().toLowerCase();
      return rows.filter((row: any) => JSON.stringify(row).toLowerCase().includes(needle));
    }
    return rows;
  }, [data, q, tab]);

  // Tier histogram for sources tab (from current server response before text filter)
  const tierCounts = useMemo(() => {
    if (tab !== "sources") return null;
    const counts: Record<string, number> = { A: 0, B: 0, C: 0, D: 0 };
    for (const row of sources.data ?? []) {
      const t = String(row.reliability_tier || "C").toUpperCase();
      if (t in counts) counts[t] += 1;
      else counts.C += 1;
    }
    return counts;
  }, [tab, sources.data]);

  async function runResolve(ref?: string) {
    const target = (ref ?? resolveRef).trim();
    if (!target) {
      setResolveStatus("Enter a name or ext:system:id");
      return;
    }
    setResolveStatus("Resolving…");
    try {
      const hit = await resolveEntity(target);
      // Prefer full entity row from list when available
      const full = (entities.data ?? []).find((e: any) => e.entity_id === hit.entity_id);
      setSelected(full ?? hit);
      setTab("entities");
      setQ(hit.canonical_name || target);
      setResolveRef(target);
      setResolveStatus(`OK → ${hit.canonical_name} (${hit.entity_id.slice(0, 12)}…)`);
    } catch (e: any) {
      setResolveStatus(`MISS: ${e?.message || "not found"}`);
    }
  }

  return (
    <div>
      <h2>Data Explorer</h2>

      {/* Entity resolve bar (uses POST /api/resolve) */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 12,
          flexWrap: "wrap",
          alignItems: "center",
          padding: 10,
          background: "#f6f8fa",
          border: "1px solid #d0d7de",
          borderRadius: 8,
        }}
      >
        <b style={{ fontSize: 12 }}>Resolve</b>
        <input
          value={resolveRef}
          onChange={(e) => setResolveRef(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void runResolve();
          }}
          placeholder="Name or ext:lei:… / lei:…"
          style={{ padding: "4px 8px", minWidth: 260, border: "1px solid #d0d7de", borderRadius: 6 }}
        />
        <button type="button" onClick={() => void runResolve()}>
          Resolve
        </button>
        {resolveStatus && (
          <span style={{ fontSize: 12, color: resolveStatus.startsWith("OK") ? "#1a7f37" : "#57606a" }}>
            {resolveStatus}
          </span>
        )}
        <span style={{ fontSize: 11, color: "#8c959f" }}>POST /api/resolve</span>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        {(["entities", "observations", "sources", "documents"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              if (t !== "entities") setSelected(null);
            }}
            style={{ fontWeight: tab === t ? 700 : 400 }}
          >
            {t}
            {t === "documents" && stats.data?.document_ids_referenced != null
              ? ` (${stats.data.document_ids_referenced})`
              : ""}
          </button>
        ))}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && tab === "entities" && looksLikeResolveRef(q)) {
              void runResolve(q);
            }
          }}
          placeholder={
            tab === "entities"
              ? "Filter table… (Enter on lei:… also resolves)"
              : tab === "sources"
                ? "Filter sources (title, publisher…)"
                : tab === "documents"
                  ? "Filter documents (id, title, text…)"
                  : "Filter…"
          }
          style={{ marginLeft: 8, padding: "4px 8px", minWidth: 260, border: "1px solid #d0d7de", borderRadius: 6 }}
        />
        <span style={{ fontSize: 12, color: "#57606a" }}>
          {filtered.length} rows
          {q ||
          (tab === "sources" && (tierFilter || sourceType)) ||
          (tab === "observations" && (obsType || spanFilter)) ||
          (tab === "entities" && entityType)
            ? " (filtered)"
            : ""}
        </span>
      </div>

      {tab === "entities" && (
        <div
          style={{
            display: "flex",
            gap: 6,
            marginBottom: 12,
            flexWrap: "wrap",
            alignItems: "center",
            padding: 10,
            background: "#f6f8fa",
            border: "1px solid #d0d7de",
            borderRadius: 8,
          }}
        >
          <b style={{ fontSize: 12 }}>entity_type</b>
          <button
            type="button"
            onClick={() => setEntityType("")}
            style={{
              fontWeight: entityType === "" ? 700 : 400,
              border: entityType === "" ? "1px solid #0969da" : "1px solid #d0d7de",
              borderRadius: 6,
              padding: "2px 8px",
              background: entityType === "" ? "#ddf4ff" : "white",
              cursor: "pointer",
              fontSize: 11,
            }}
          >
            All
          </button>
          {Object.entries(stats.data?.entity_type_counts || {})
            .sort((a, b) => b[1] - a[1])
            .map(([t, n]) => {
              const active = entityType === t;
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => setEntityType(active ? "" : t)}
                  style={{
                    fontWeight: active ? 700 : 400,
                    border: active ? "1px solid #0969da" : "1px solid #d0d7de",
                    borderRadius: 6,
                    padding: "2px 8px",
                    background: active ? "#ddf4ff" : "white",
                    cursor: "pointer",
                    fontSize: 11,
                  }}
                >
                  {t} ({n})
                </button>
              );
            })}
          <span style={{ fontSize: 11, color: "#8c959f" }}>GET /api/entities?entity_type=</span>
        </div>
      )}

      {tab === "observations" && (
        <div
          style={{
            display: "flex",
            gap: 6,
            marginBottom: 12,
            flexWrap: "wrap",
            alignItems: "center",
            padding: 10,
            background: "#f6f8fa",
            border: "1px solid #d0d7de",
            borderRadius: 8,
          }}
        >
          <b style={{ fontSize: 12 }}>observation_type</b>
          <button
            type="button"
            onClick={() => setObsType("")}
            style={{
              fontWeight: obsType === "" ? 700 : 400,
              border: obsType === "" ? "1px solid #0969da" : "1px solid #d0d7de",
              borderRadius: 6,
              padding: "2px 8px",
              background: obsType === "" ? "#ddf4ff" : "white",
              cursor: "pointer",
              fontSize: 11,
            }}
          >
            All
          </button>
          {Object.entries(stats.data?.observation_type_counts || {})
            .sort((a, b) => b[1] - a[1])
            .map(([t, n]) => {
              const active = obsType === t;
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => setObsType(active ? "" : t)}
                  style={{
                    fontWeight: active ? 700 : 400,
                    border: active ? "1px solid #0969da" : "1px solid #d0d7de",
                    borderRadius: 6,
                    padding: "2px 8px",
                    background: active ? "#ddf4ff" : "white",
                    cursor: "pointer",
                    fontSize: 11,
                  }}
                >
                  {t} ({n})
                </button>
              );
            })}
          <span style={{ fontSize: 11, color: "#8c959f" }}>GET /api/observations?observation_type=</span>
        </div>
      )}

      {tab === "observations" && (
        <div
          style={{
            display: "flex",
            gap: 6,
            marginBottom: 12,
            flexWrap: "wrap",
            alignItems: "center",
            padding: 10,
            background: "#f6f8fa",
            border: "1px solid #d0d7de",
            borderRadius: 8,
          }}
        >
          <b style={{ fontSize: 12 }}>char_span</b>
          {(
            [
              { id: "" as const, label: "All", n: undefined as number | undefined },
              {
                id: "with" as const,
                label: "with span",
                n: stats.data?.observations_with_char_span,
              },
              {
                id: "auto" as const,
                label: "auto",
                n: stats.data?.observations_with_char_span_auto,
              },
              {
                id: "missing_on_doc" as const,
                label: "missing on doc",
                n: stats.data?.observations_missing_char_span,
              },
              {
                id: "none" as const,
                label: "no span",
                n:
                  typeof stats.data?.counts?.observations === "number" &&
                  typeof stats.data?.observations_with_char_span === "number"
                    ? Math.max(
                        0,
                        (stats.data.counts.observations as number) -
                          (stats.data.observations_with_char_span as number),
                      )
                    : undefined,
              },
            ] as const
          ).map(({ id, label, n }) => {
            const active = spanFilter === id;
            const accent =
              id === "auto"
                ? { border: "#9a6700", bg: "#fff8c5", color: "#9a6700" }
                : id === "missing_on_doc"
                  ? { border: "#cf222e", bg: "#ffebe9", color: "#cf222e" }
                  : { border: "#0969da", bg: "#ddf4ff", color: undefined as string | undefined };
            return (
              <button
                key={label}
                type="button"
                title={
                  id === "auto"
                    ? "Auto-aligned from text_excerpt (engine 0.1.20+)"
                    : id === "with"
                      ? "Observations with any char_span"
                      : id === "missing_on_doc"
                        ? "Has document_id but no char_span — provenance gap (0.1.28+)"
                        : id === "none"
                          ? "Observations without char_span"
                          : "All observations"
                }
                onClick={() => setSpanFilter(active && id !== "" ? "" : id)}
                style={{
                  fontWeight: active ? 700 : 400,
                  border: active ? `1px solid ${accent.border}` : "1px solid #d0d7de",
                  borderRadius: 6,
                  padding: "2px 8px",
                  background: active ? accent.bg : "white",
                  color: active ? accent.color : undefined,
                  cursor: "pointer",
                  fontSize: 11,
                }}
              >
                {label}
                {typeof n === "number" ? ` (${n})` : ""}
              </button>
            );
          })}
          <span style={{ fontSize: 11, color: "#8c959f" }}>
            GET /api/observations?missing_char_span=&amp;has_char_span=
          </span>
        </div>
      )}

      {tab === "sources" && (
        <div
          style={{
            display: "flex",
            gap: 8,
            marginBottom: 12,
            flexWrap: "wrap",
            alignItems: "center",
            padding: 10,
            background: "#f6f8fa",
            border: "1px solid #d0d7de",
            borderRadius: 8,
          }}
        >
          <b style={{ fontSize: 12 }}>reliability_tier</b>
          <button
            type="button"
            onClick={() => setTierFilter("")}
            style={{
              fontWeight: tierFilter === "" ? 700 : 400,
              border: tierFilter === "" ? "1px solid #0969da" : "1px solid #d0d7de",
              borderRadius: 6,
              padding: "2px 10px",
              background: tierFilter === "" ? "#ddf4ff" : "white",
              cursor: "pointer",
            }}
          >
            All
          </button>
          {(["A", "B", "C", "D"] as Tier[]).map((t) => {
            const active = tierFilter === t;
            const c = TIER_COLORS[t];
            const n = tierCounts?.[t];
            return (
              <button
                key={t}
                type="button"
                title={c.label}
                onClick={() => setTierFilter(active ? "" : t)}
                style={{
                  fontWeight: active ? 700 : 400,
                  border: active ? `1px solid ${c.fg}` : "1px solid #d0d7de",
                  borderRadius: 6,
                  padding: "2px 10px",
                  background: active ? c.bg : "white",
                  color: c.fg,
                  cursor: "pointer",
                }}
              >
                {t}
                {typeof n === "number" && tierFilter === t ? ` (${n})` : ""}
              </button>
            );
          })}
          <span style={{ fontSize: 11, color: "#8c959f" }}>
            GET /api/sources?reliability_tier=
          </span>
          <a
            href="https://github.com/taipei49314/aurora/blob/master/docs/scoring-model.md"
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: 11, color: "#0969da" }}
            title="data_quality_penalty uses A–D tiers"
          >
            scoring model · data_quality
          </a>
          <span style={{ fontSize: 11, color: "#8c959f" }}>·</span>
          <a
            href="https://github.com/taipei49314/aurora/blob/master/docs/import-schema.md"
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: 11, color: "#0969da" }}
          >
            import schema §6
          </a>
        </div>
      )}

      {tab === "sources" && (
        <div
          style={{
            display: "flex",
            gap: 6,
            marginBottom: 12,
            flexWrap: "wrap",
            alignItems: "center",
            padding: 10,
            background: "#f6f8fa",
            border: "1px solid #d0d7de",
            borderRadius: 8,
          }}
        >
          <b style={{ fontSize: 12 }}>source_type</b>
          <button
            type="button"
            onClick={() => setSourceType("")}
            style={{
              fontWeight: sourceType === "" ? 700 : 400,
              border: sourceType === "" ? "1px solid #0969da" : "1px solid #d0d7de",
              borderRadius: 6,
              padding: "2px 8px",
              background: sourceType === "" ? "#ddf4ff" : "white",
              cursor: "pointer",
              fontSize: 11,
            }}
          >
            All
          </button>
          {Object.entries(stats.data?.source_type_counts || {})
            .sort((a, b) => b[1] - a[1])
            .map(([t, n]) => {
              const active = sourceType === t;
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSourceType(active ? "" : t)}
                  style={{
                    fontWeight: active ? 700 : 400,
                    border: active ? "1px solid #0969da" : "1px solid #d0d7de",
                    borderRadius: 6,
                    padding: "2px 8px",
                    background: active ? "#ddf4ff" : "white",
                    cursor: "pointer",
                    fontSize: 11,
                  }}
                >
                  {t} ({n})
                </button>
              );
            })}
          <span style={{ fontSize: 11, color: "#8c959f" }}>GET /api/sources?source_type=</span>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: selected ? "1.4fr 1fr" : "1fr", gap: 16 }}>
        <div style={{ overflowX: "auto", maxHeight: 520, overflowY: "auto" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 12, minWidth: 700 }}>
            <thead>
              <tr
                style={{
                  textAlign: "left",
                  color: "#57606a",
                  borderBottom: "1px solid #d0d7de",
                  position: "sticky",
                  top: 0,
                  background: "white",
                }}
              >
                {cols.map((c) => (
                  <th key={c} style={{ padding: 6 }}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 300).map((row: any, i: number) => {
                const active =
                  selected &&
                  ((tab === "entities" && selected.entity_id === row.entity_id) ||
                    (tab === "sources" && selected.source_id === row.source_id) ||
                    (tab === "observations" && selected.observation_id === row.observation_id) ||
                    (tab === "documents" && selected.document_id === row.document_id));
                return (
                  <tr
                    key={i}
                    onClick={() => setSelected(row)}
                    style={{
                      borderBottom: "1px solid #eaeef2",
                      cursor: "pointer",
                      background: active ? "#ddf4ff" : undefined,
                    }}
                  >
                    {cols.map((c) => (
                      <td key={c} style={{ padding: 6, maxWidth: 280, wordBreak: "break-word" }}>
                        {cellValue(tab, c, row)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {selected && (
          <div
            style={{
              border: "1px solid #d0d7de",
              borderRadius: 8,
              padding: 12,
              fontSize: 12,
              maxHeight: 520,
              overflow: "auto",
              background: "#f6f8fa",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <b>Detail</b>
              <button type="button" onClick={() => setSelected(null)} style={{ fontSize: 11 }}>
                close
              </button>
            </div>
            {(tab === "entities" || selected.canonical_name) && (
              <>
                <div style={{ marginBottom: 6 }}>
                  <b>{selected.canonical_name}</b>
                  {selected.entity_type ? ` · ${selected.entity_type}` : ""}
                </div>
                <div style={{ color: "#57606a", marginBottom: 8 }}>{selected.entity_id}</div>
                <b>external_ids</b>
                <ul style={{ margin: "4px 0 10px", paddingLeft: 18 }}>
                  {(selected.external_ids || []).length === 0 && (
                    <li style={{ color: "#57606a" }}>none</li>
                  )}
                  {(selected.external_ids || []).map((x: any, i: number) => (
                    <li key={i}>
                      <code>
                        {x.system}:{x.id}
                      </code>
                      <button
                        type="button"
                        style={{ marginLeft: 6, fontSize: 10 }}
                        onClick={() => void runResolve(`ext:${x.system}:${x.id}`)}
                      >
                        resolve
                      </button>
                    </li>
                  ))}
                </ul>
                <b>aliases</b>
                <div style={{ color: "#57606a", marginBottom: 8 }}>
                  {(selected.aliases || []).join(", ") || "—"}
                </div>
                {selected.country && (
                  <div>
                    <b>country</b> {selected.country}
                  </div>
                )}
              </>
            )}
            {tab === "sources" && selected.source_id && (
              <>
                <div style={{ marginBottom: 6 }}>
                  <b>{selected.title || "(untitled)"}</b>
                </div>
                <div style={{ color: "#57606a", marginBottom: 8 }}>{selected.source_id}</div>
                <div style={{ marginBottom: 8, display: "flex", gap: 8, alignItems: "center" }}>
                  <b>reliability_tier</b>
                  <TierBadge tier={String(selected.reliability_tier || "C")} />
                  <span style={{ color: "#57606a" }}>
                    {TIER_COLORS[(String(selected.reliability_tier || "C").toUpperCase() as Tier)]?.label ??
                      "secondary"}
                  </span>
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b>type</b> {selected.source_type || "—"} · <b>publisher</b> {selected.publisher || "—"}
                </div>
                <div style={{ marginBottom: 6 }}>
                  <b>independence_group</b>{" "}
                  <code>{selected.independence_group || "—"}</code>
                </div>
                <div style={{ fontSize: 11, color: "#57606a", marginTop: 10 }}>
                  Weak tiers raise <code>data_quality_penalty</code> on hypotheses that cite this
                  source (see scoring model).
                </div>
              </>
            )}
            {tab === "observations" && selected.observation_id && (
              <ObservationDetail obs={selected} />
            )}
            {tab === "documents" && selected.document_id && (
              <DocumentDetail
                doc={selected}
                onOpenObservation={(obs) => {
                  setTab("observations");
                  setSelected(obs);
                  setObsType("");
                  setQ(obs.document_id || "");
                }}
              />
            )}
            {tab !== "entities" &&
              tab !== "sources" &&
              tab !== "documents" &&
              !selected.canonical_name &&
              !selected.observation_id && (
                <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 11 }}>
                  {JSON.stringify(selected, null, 2)}
                </pre>
              )}
          </div>
        )}
      </div>
      {!data && <p>Loading…</p>}
    </div>
  );
}

function DocumentDetail({
  doc,
  onOpenObservation,
}: {
  doc: any;
  onOpenObservation: (obs: any) => void;
}) {
  const linked = useQuery({
    queryKey: ["observations-by-doc", doc.document_id],
    queryFn: () => getObservations({ document_id: doc.document_id }),
    enabled: !!doc.document_id,
  });

  return (
    <div>
      <div style={{ marginBottom: 6 }}>
        <b>{doc.title || doc.document_id}</b>
        {doc.stub ? (
          <span
            style={{
              marginLeft: 8,
              fontSize: 10,
              padding: "1px 6px",
              borderRadius: 8,
              background: "#fff8c5",
              color: "#9a6700",
            }}
          >
            stub
          </span>
        ) : (
          <span
            style={{
              marginLeft: 8,
              fontSize: 10,
              padding: "1px 6px",
              borderRadius: 8,
              background: "#dafbe1",
              color: "#1a7f37",
            }}
          >
            full
          </span>
        )}
      </div>
      <div style={{ color: "#57606a", marginBottom: 8, fontSize: 11 }}>
        <code>{doc.document_id}</code>
      </div>
      <div style={{ marginBottom: 6 }}>
        <b>obs</b> {doc.observation_count ?? linked.data?.length ?? "—"} · <b>license</b>{" "}
        {doc.license || "—"} · <b>source</b>{" "}
        <code style={{ fontSize: 10 }}>{doc.source_id || "—"}</code>
      </div>
      {doc.url_or_local_path && (
        <div style={{ marginBottom: 8, fontSize: 11, color: "#57606a" }}>
          path: {doc.url_or_local_path}
        </div>
      )}
      <div
        style={{
          marginTop: 8,
          padding: 10,
          background: "white",
          border: "1px solid #d0d7de",
          borderRadius: 6,
          maxHeight: 180,
          overflow: "auto",
          fontSize: 12,
          whiteSpace: "pre-wrap",
        }}
      >
        {doc.text ? (
          doc.text
        ) : (
          <span style={{ color: "#8c959f" }}>
            {doc.stub
              ? "Stub document: referenced by observations but no full text in snapshot. Import a package with documents[] to attach body text."
              : "(empty text)"}
          </span>
        )}
      </div>
      <div style={{ marginTop: 12 }}>
        <b style={{ fontSize: 12 }}>Linked observations</b>
        <span style={{ fontSize: 11, color: "#8c959f", marginLeft: 6 }}>
          GET /api/observations?document_id=
        </span>
        {linked.isLoading && <p style={{ color: "#57606a" }}>Loading…</p>}
        {linked.data && linked.data.length === 0 && (
          <p style={{ color: "#57606a", fontSize: 12 }}>none</p>
        )}
        <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 12 }}>
          {(linked.data || []).slice(0, 40).map((o: any) => (
            <li key={o.observation_id} style={{ marginBottom: 4 }}>
              <button
                type="button"
                onClick={() => onOpenObservation(o)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#0969da",
                  cursor: "pointer",
                  padding: 0,
                  fontSize: 12,
                  textAlign: "left",
                }}
              >
                {o.observation_type}
              </button>
              {o.char_span != null && (
                <span style={{ color: "#57606a", marginLeft: 6 }}>
                  span{" "}
                  {Array.isArray(o.char_span)
                    ? `[${o.char_span[0]}, ${o.char_span[1]}]`
                    : JSON.stringify(o.char_span)}
                </span>
              )}
              <div style={{ color: "#57606a", fontSize: 11 }}>
                {(o.text_excerpt || "").slice(0, 100)}
                {(o.text_excerpt || "").length > 100 ? "…" : ""}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function highlightSpan(text: string, span: any): ReactNode {
  if (!text) return <span style={{ color: "#8c959f" }}>(no document text)</span>;
  let start = 0;
  let end = 0;
  if (Array.isArray(span) && span.length >= 2) {
    start = Number(span[0]) || 0;
    end = Number(span[1]) || 0;
  } else if (span && typeof span === "object") {
    start = Number(span.start) || 0;
    end = Number(span.end) || 0;
  } else {
    return <span style={{ whiteSpace: "pre-wrap" }}>{text}</span>;
  }
  if (start < 0) start = 0;
  if (end < start) end = start;
  if (end > text.length) end = text.length;
  if (start >= text.length) {
    return <span style={{ whiteSpace: "pre-wrap" }}>{text}</span>;
  }
  return (
    <span style={{ whiteSpace: "pre-wrap" }}>
      {text.slice(0, start)}
      <mark style={{ background: "#fff8c5", padding: "0 1px" }}>{text.slice(start, end)}</mark>
      {text.slice(end)}
    </span>
  );
}

function ObservationDetail({ obs }: { obs: any }) {
  const docId = obs.document_id || obs.metadata?.document_id || "";
  const span = obs.char_span || obs.metadata?.char_span;
  const doc = useQuery({
    queryKey: ["document", docId],
    queryFn: () => getDocument(docId),
    enabled: !!docId,
    retry: false,
  });

  return (
    <div>
      <div style={{ marginBottom: 6 }}>
        <b>{obs.observation_type}</b>
        {obs.subject_entity ? ` · subject ${String(obs.subject_entity).slice(0, 16)}…` : ""}
      </div>
      <div style={{ color: "#57606a", marginBottom: 8, fontSize: 11 }}>{obs.observation_id}</div>
      <div style={{ marginBottom: 6 }}>
        <b>observed_at</b> {obs.observed_at || "—"} · <b>event_id</b> {obs.event_id || "—"}
      </div>
      <div style={{ marginBottom: 6 }}>
        <b>document_id</b> <code>{docId || "—"}</code>
        {span != null && (
          <>
            {" "}
            · <b>char_span</b>{" "}
            <code>{Array.isArray(span) ? `[${span[0]}, ${span[1]}]` : JSON.stringify(span)}</code>
            {obs.metadata?.char_span_auto && (
              <span
                title="Auto-aligned from text_excerpt (engine 0.1.20+)"
                style={{
                  marginLeft: 6,
                  fontSize: 10,
                  fontWeight: 700,
                  color: "#9a6700",
                  background: "#fff8c5",
                  borderRadius: 8,
                  padding: "1px 6px",
                  verticalAlign: "middle",
                }}
              >
                auto
              </span>
            )}
          </>
        )}
      </div>
      <div style={{ marginBottom: 8 }}>
        <b>text_excerpt</b>
        <div style={{ color: "#57606a", marginTop: 2 }}>{obs.text_excerpt || "—"}</div>
      </div>
      {docId && (
        <div
          style={{
            marginTop: 10,
            padding: 10,
            background: "white",
            border: "1px solid #d0d7de",
            borderRadius: 6,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <b style={{ fontSize: 11 }}>
              Document text
              {obs.metadata?.char_span_auto && span != null ? (
                <span
                  style={{
                    marginLeft: 6,
                    fontSize: 10,
                    fontWeight: 700,
                    color: "#9a6700",
                    background: "#fff8c5",
                    borderRadius: 8,
                    padding: "1px 6px",
                  }}
                >
                  auto span
                </span>
              ) : null}
            </b>
            <span style={{ fontSize: 10, color: "#8c959f" }}>GET /api/documents/…</span>
          </div>
          {doc.isLoading && <span style={{ color: "#57606a" }}>Loading document…</span>}
          {doc.isError && (
            <span style={{ color: "#57606a" }}>
              No full document in snapshot (path-only or not imported). Span still recorded on
              observation.
            </span>
          )}
          {doc.data && (
            <>
              {doc.data.title && (
                <div style={{ marginBottom: 6, fontWeight: 600 }}>{doc.data.title}</div>
              )}
              {doc.data.license && (
                <div style={{ fontSize: 11, color: "#57606a", marginBottom: 6 }}>
                  license: {doc.data.license}
                </div>
              )}
              <div style={{ fontSize: 12, lineHeight: 1.45 }}>
                {highlightSpan(String(doc.data.text || ""), span)}
              </div>
            </>
          )}
        </div>
      )}
      <details style={{ marginTop: 10 }}>
        <summary style={{ cursor: "pointer", fontSize: 11, color: "#57606a" }}>raw JSON</summary>
        <pre style={{ whiteSpace: "pre-wrap", margin: "6px 0 0", fontSize: 11 }}>
          {JSON.stringify(obs, null, 2)}
        </pre>
      </details>
    </div>
  );
}
