const entries = [
  {
    href: "#/doc/cli",
    label: "CLI Reference",
    title: "命令行协议",
    description: "从 reindex/cli@1.0 契约自动生成的命令、参数、约束与示例。",
  },
  {
    href: "/docs/api",
    label: "HTTP API Reference",
    title: "服务接口协议",
    description: "从 reindex-http-v1 OpenAPI 契约自动生成的可检索 API 参考文档。",
  },
];

export function DocHomePage() {
  return (
    <section className="doc-home">
      <div className="doc-hero">
        <p className="eyebrow">CONTRACT REFERENCES</p>
        <h1>ReIndex Docs</h1>
        <p>CLI 与 HTTP API 的人类可读入口；实现、校验和文档使用同一份契约。</p>
      </div>
      <div className="doc-entry-grid">
        {entries.map((entry) => (
          <a className="doc-entry" href={entry.href} key={entry.href}>
            <span>{entry.label}</span>
            <h2>{entry.title}</h2>
            <p>{entry.description}</p>
            <strong>打开文档 →</strong>
          </a>
        ))}
      </div>
    </section>
  );
}
