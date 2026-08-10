import { useI18n, type Language } from "../i18n";

type Props = { active: "explore" | "search" | "tables" | "doc" };

export function SiteHeader({ active }: Props) {
  const { language, setLanguage, t } = useI18n();
  return (
    <header className="topbar">
      <a className="brand" href="/#/explore" aria-label="ReIndex Explore">
        <span className="brand-mark" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span>reIndex</span>
      </a>
      <nav className="main-nav" aria-label={t("nav.label")}>
        <a className={active === "explore" ? "active" : ""} href="/#/explore">
          {t("nav.explore")}
        </a>
        <a className={active === "search" ? "active" : ""} href="/#/search">
          {t("nav.search")}
        </a>
        <a className={active === "tables" ? "active" : ""} href="/v1/tables/query">
          {t("nav.tables")}
        </a>
        <a className={active === "doc" ? "active" : ""} href="/#/doc">
          {t("nav.docs")}
        </a>
        <a href="https://github.com/yechenyan/reIndex/tree/main/wiki" rel="noreferrer" target="_blank">{t("nav.wiki")}</a>
        <a href="https://github.com/yechenyan/reIndex" rel="noreferrer" target="_blank">
          {t("nav.github")}
        </a>
      </nav>
      <label className="language-picker"><span className="sr-only">{t("language.label")}</span><select aria-label={t("language.label")} onChange={(event) => setLanguage(event.target.value as Language)} value={language}><option value="de">DE</option><option value="en">EN</option><option value="zh">中文</option></select></label>
      <span className="protocol-badge">Protocol 1.0</span>
    </header>
  );
}
