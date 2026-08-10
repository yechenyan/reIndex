import { useI18n } from "../i18n";

type Board = {
  eyebrow: string;
  title: string;
  description: string;
  details: string[];
  kind: "ingest" | "discover" | "agent";
  href: string;
  action: string;
};

export function HomePage() {
  const { t } = useI18n();
  const boards: Board[] = [
    {
      eyebrow: t("home.ingest.eyebrow"), title: t("home.ingest.title"), description: t("home.ingest.description"),
      details: t("home.ingest.details").split("|"), kind: "ingest", href: "#/doc", action: t("home.ingest.action"),
    },
    {
      eyebrow: t("home.discover.eyebrow"), title: t("home.discover.title"), description: t("home.discover.description"),
      details: t("home.discover.details").split("|"), kind: "discover", href: "#/search", action: t("home.discover.action"),
    },
    {
      eyebrow: t("home.agent.eyebrow"), title: t("home.agent.title"), description: t("home.agent.description"),
      details: t("home.agent.details").split("|"), kind: "agent", href: "#/doc/cli", action: t("home.agent.action"),
    },
  ];
  const steps = t("home.steps.items").split("|").map((item) => item.split(";"));
  const proofPoints = t("home.proof.items").split("|").map((item) => item.split(";"));

  return <div className="home-page">
    <section className="home-hero">
      <p className="eyebrow">{t("home.eyebrow")}</p>
      <h1>{t("home.title")}</h1>
      <p>{t("home.description")}</p>
      <div className="home-actions">
        <a className="button-primary" href="#/explore">{t("home.explore")}</a>
        <a className="button-secondary" href="#/search">{t("home.search")}</a>
      </div>
    </section>
    <section className="board-section" aria-label={t("home.boardsLabel")}>
      <div className="board-section-heading">
        <p className="eyebrow">{t("home.boardsEyebrow")}</p>
        <p>{t("home.boardsDescription")}</p>
      </div>
      <div className="feature-boards">
        {boards.map((board) => <article className="feature-board" key={board.kind}>
          <div className={`board-visual ${board.kind}`} aria-hidden="true"><span /><span /><span /></div>
          <div className="board-body">
            <p className="board-eyebrow">{board.eyebrow}</p>
            <h2>{board.title}</h2>
            <p className="board-description">{board.description}</p>
            <ul>{board.details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
            <a className="board-link" href={board.href}>{board.action} <span aria-hidden="true">→</span></a>
          </div>
        </article>)}
      </div>
    </section>
    <section className="workflow-section" aria-labelledby="workflow-title">
      <div className="workflow-copy">
        <p className="eyebrow">{t("home.steps.eyebrow")}</p>
        <h2 id="workflow-title">{t("home.steps.title")}</h2>
        <p>{t("home.steps.description")}</p>
      </div>
      <ol className="workflow-steps">
        {steps.map(([number, title, description]) => <li key={number}>
          <span>{number}</span><h3>{title}</h3><p>{description}</p>
        </li>)}
      </ol>
    </section>
    <section className="proof-section" aria-labelledby="proof-title">
      <div className="proof-heading">
        <p className="eyebrow">{t("home.proof.eyebrow")}</p>
        <h2 id="proof-title">{t("home.proof.title")}</h2>
      </div>
      <div className="proof-points">
        {proofPoints.map(([title, description], index) => <article key={title}>
          <span aria-hidden="true">0{index + 1}</span><h3>{title}</h3><p>{description}</p>
        </article>)}
      </div>
    </section>
    <section className="home-cta">
      <div><p className="eyebrow">{t("home.cta.eyebrow")}</p><h2>{t("home.cta.title")}</h2><p>{t("home.cta.description")}</p></div>
      <div className="cta-actions"><a className="button-primary" href="#/doc/cli">{t("home.cta.cli")}</a><a className="button-secondary" href="#/doc/api">{t("home.cta.api")}</a></div>
    </section>
  </div>;
}
