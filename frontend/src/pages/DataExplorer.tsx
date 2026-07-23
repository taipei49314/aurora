import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEntities, getObservations, getSources, getStats, resolveEntity } from "../api";

type Tab = "entities" | "observations" | "sources";
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
  const [obsType, setObsType] = useState("");
  const [resolveRef, setResolveRef] = useState("");
  const [resolveStatus, setResolveStatus] = useState<string | null>(null);
  const [selected, setSelected] = useState<any | null>(null);

  const stats = useQuery({ queryKey: ["stats"], queryFn: getStats, staleTime: 30_000 });

  // Server-side filter for entities (?q=); client filter for other tabs
  const serverQ = tab === "entities" && q.trim() && !looksLikeResolveRef(q) ? q.trim() : undefined;
  const entities = useQuery({
    queryKey: ["entities", serverQ ?? ""],
    queryFn: () => getEntities(serverQ),
    enabled: tab === "entities" || !!selected,
  });
  const observations = useQuery({
    queryKey: ["observations", q, obsType],
    queryFn: () =>
      getObservations({
        q: q.trim() || undefined,
        observation_type: obsType || undefined,
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

  const data = tab === "entities" ? entities.data : tab === "observations" ? observations.data : sources.data;
  const cols =
    tab === "entities"
      ? ["entity_type", "canonical_name", "country", "external_ids", "entity_id"]
      : tab === "observations"
        ? ["observation_type", "subject_entity", "observed_at", "event_id", "confidence", "observation_id"]
        : ["source_type", "publisher", "reliability_tier", "event_date", "published_at", "event_id", "family_id", "independence_group", "source_id"];

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
        {(["entities", "observations", "sources"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              if (t !== "entities") setSelected(null);
            }}
            style={{ fontWeight: tab === t ? 700 : 400 }}
          >
            {t}
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
                : "Filter…"
          }
          style={{ marginLeft: 8, padding: "4px 8px", minWidth: 260, border: "1px solid #d0d7de", borderRadius: 6 }}
        />
        <span style={{ fontSize: 12, color: "#57606a" }}>
          {filtered.length} rows
          {q ||
          (tab === "sources" && (tierFilter || sourceType)) ||
          (tab === "observations" && obsType)
            ? " (filtered)"
            : ""}
        </span>
      </div>

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
                    (tab === "observations" && selected.observation_id === row.observation_id));
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
              <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 11 }}>
                {JSON.stringify(selected, null, 2)}
              </pre>
            )}
            {tab !== "entities" &&
              tab !== "sources" &&
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
