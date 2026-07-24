import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useCurrentRun } from "../useRun";
import { getTimeline } from "../api";

/** Shareable hypothesis id from URL (`id`, `hypothesis_id`, or short `h`). */
function parseHypId(params: URLSearchParams): string | null {
  return params.get("id") || params.get("hypothesis_id") || params.get("h") || null;
}

export function Timeline() {
  const { hyps } = useCurrentRun();
  const [searchParams, setSearchParams] = useSearchParams();
  const fromUrl = parseHypId(searchParams);
  const known = fromUrl && hyps.data?.some((h) => h.hypothesis_id === fromUrl);
  const id = (known ? fromUrl : null) ?? hyps.data?.[0]?.hypothesis_id ?? null;
  const tl = useQuery({ queryKey: ["timeline", id], queryFn: () => getTimeline(id!), enabled: !!id });

  const setId = (nextId: string) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("hypothesis_id");
        next.delete("h");
        next.set("id", nextId);
        return next;
      },
      { replace: true },
    );
  };

  if (!hyps.data) return <p>Loading…</p>;
  const rows = tl.data?.timeline ?? [];
  const max = Math.max(1, ...rows.map((r: any) => r.total));

  return (
    <div>
      <h2>Timeline — signal acceleration</h2>
      {fromUrl && !known && (
        <p style={{ fontSize: 12, color: "#9a6700", marginBottom: 8 }}>
          No hypothesis matches <code>?id={fromUrl}</code> for this run — showing first hypothesis.
        </p>
      )}
      <select
        value={id ?? ""}
        onChange={(e) => setId(e.target.value)}
        style={{ marginBottom: 16 }}
        title="Selection is stored in ?id= for sharing"
      >
        {hyps.data.map((h) => (
          <option key={h.hypothesis_id} value={h.hypothesis_id}>
            {h.generated_name}
          </option>
        ))}
      </select>
      {id && (
        <span style={{ marginLeft: 10, fontSize: 11, color: "#8c959f" }}>
          <code>?id={id.slice(0, 12)}…</code>
          {" · "}
          <Link
            to={`/hypotheses?id=${encodeURIComponent(id)}`}
            style={{ color: "#0969da", fontWeight: 600, textDecoration: "none" }}
            title="Open this hypothesis in Hypothesis Explorer"
          >
            Explorer ↗
          </Link>
          {" · "}
          <Link
            to={`/map?id=${encodeURIComponent(id)}`}
            style={{ color: "#0969da", fontWeight: 600, textDecoration: "none" }}
            title="Open Discovery Map for this hypothesis"
          >
            Map ↗
          </Link>
        </span>
      )}
      <div style={{ display: "flex", alignItems: "flex-end", gap: 12, height: 240, borderBottom: "1px solid #d0d7de", paddingBottom: 4 }}>
        {rows.map((r: any) => (
          <div key={r.year} style={{ textAlign: "center" }}>
            <div title={JSON.stringify(r.by_type)} style={{ width: 44, height: `${(r.total / max) * 200}px`,
              background: "#0969da", borderRadius: "4px 4px 0 0" }} />
            <div style={{ fontSize: 12, marginTop: 4 }}>{r.year}</div>
            <div style={{ fontSize: 11, color: "#57606a" }}>{r.total}</div>
          </div>
        ))}
      </div>
      <p style={{ fontSize: 12, color: "#57606a", marginTop: 10 }}>
        Bar height = observation count per year (hover for the observation-type breakdown). A genuine forming
        industry shows rising real-investment activity; a hype cluster spikes then fades.
      </p>
    </div>
  );
}
