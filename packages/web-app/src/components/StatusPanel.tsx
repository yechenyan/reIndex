export function StatusPanel({ title, message }: { title: string; message: string }) {
  return (
    <section className="status-panel" role="status">
      <span className="status-glyph">R</span>
      <h2>{title}</h2>
      <p>{message}</p>
    </section>
  );
}
