import { useI18n } from "../i18n";

export function DocHomePage() {
  const { t } = useI18n();
  const entries = [
    { href: "#/doc/cli", label: "CLI Reference", title: t("docs.cli.title"), description: t("docs.cli.desc") },
    { href: "#/doc/api", label: "HTTP API Reference", title: t("docs.api.title"), description: t("docs.api.desc") },
  ];
  return (
    <section className="doc-home">
      <div className="doc-hero">
        <p className="eyebrow">CONTRACT REFERENCES</p>
        <h1>ReIndex Docs</h1>
        <p>{t("docs.intro")}</p>
      </div>
      <div className="doc-entry-grid">
        {entries.map((entry) => (
          <a className="doc-entry" href={entry.href} key={entry.href}>
            <span>{entry.label}</span>
            <h2>{entry.title}</h2>
            <p>{entry.description}</p>
            <strong>{t("docs.open")}</strong>
          </a>
        ))}
      </div>
    </section>
  );
}
