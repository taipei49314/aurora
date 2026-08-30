export function LoadError({
  resource,
  detail,
}: {
  resource: string;
  detail?: string;
}) {
  return (
    <section
      role="alert"
      style={{
        border: "1px solid #ff8182",
        borderRadius: 8,
        padding: "14px 16px",
        background: "#ffebe9",
        color: "#82071e",
      }}
    >
      <h2 style={{ margin: "0 0 6px", fontSize: 18 }}>Could not load {resource}</h2>
      <p style={{ margin: 0 }}>
        {detail ?? "Check that the AURORA API is running, then retry this page."}
      </p>
    </section>
  );
}
