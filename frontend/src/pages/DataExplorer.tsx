import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEntities, getObservations, getSources, resolveEntity } from "../api";

type Tab = "entities" | "observations" | "sources";

function formatExternalIds(row: any): string {
  const ids = row.external_ids;
  if (!Array.isArray(ids) || ids.length === 0) return "—";
  return ids
    .map((x: any) => `${x.system ?? "?"}:${x.id ?? "?"}`)
    .join(" · ");
}

function cellValue(tab: Tab, col: string, row: any): string {
  if (tab === "entities" && col === "external_ids") return formatExternalIds(row);
  if (tab === "sources" && col === "independence_group") {
    return String(row.independence_group || "—");
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
  const [resolveRef, setResolveRef] = useState("");
  const [resolveStatus, setResolveStatus] = useState<string | null>(null);
  const [selected, setSelected] = useState<any | null>(null);

  const entities = useQuery({
    queryKey: ["entities"],
    queryFn: getEntities,
    enabled: tab === "entities" || !!selected,
  });
  const observations = useQuery({
    queryKey: ["observations"],
    queryFn: getObservations,
    enabled: tab === "observations",
  });
  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: getSources,
    enabled: tab === "sources",
  });

  const data = tab === "entities" ? entities.data : tab === "observations" ? observations.data : sources.data;
  const cols =
    tab === "entities"
      ? ["entity_type", "canonical_name", "country", "external_ids", "entity_id"]
      : tab === "observations"
        ? ["observation_type", "subject_entity", "observed_at", "confidence", "observation_id"]
        : ["source_type", "publisher", "reliability_tier", "independence_group", "source_id"];

  const filtered = useMemo(() => {
    const rows = data ?? [];
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row: any) => {
      const blob = JSON.stringify(row).toLowerCase();
      return blob.includes(needle);
    });
  }, [data, q]);

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
          placeholder='Name or ext:lei:… / lei:…'
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
              : "Filter…"
          }
          style={{ marginLeft: 8, padding: "4px 8px", minWidth: 260, border: "1px solid #d0d7de", borderRadius: 6 }}
        />
        <span style={{ fontSize: 12, color: "#57606a" }}>
          {filtered.length} rows{q ? " (filtered)" : ""}
        </span>
      </div>

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
            {tab !== "entities" && !selected.canonical_name && (
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
