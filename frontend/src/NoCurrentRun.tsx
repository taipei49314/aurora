export function NoCurrentRun() {
  return (
    <div>
      <h2>Current snapshot has no research run</h2>
      <p style={{ color: "#57606a", fontSize: 13 }}>
        The corpus was imported successfully, but it has not been analyzed yet. Create a run with{" "}
        <code>POST /api/research-runs</code> to make its hypotheses active.
      </p>
    </div>
  );
}
