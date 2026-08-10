import { RedocStandalone } from "redoc";
import openApiUrl from "../../../server/src/reindex_server/openapi/reindex-http-v1.yaml?url";
import { useI18n } from "../i18n";

const options = {
  expandResponses: "200,201",
  hideDownloadButton: false,
  nativeScrollbars: true,
  pathInMiddlePanel: true,
  scrollYOffset: 78,
  theme: {
    colors: { primary: { main: "#002e4f" } },
    sidebar: { backgroundColor: "#f7f9fa", textColor: "#52616c" },
    typography: {
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      headings: { fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" },
    },
  },
};

export function ApiDocPage() {
  const { t } = useI18n();
  return (
    <section className="api-doc-page">
      <div className="doc-subnav">
        <a href="/#/doc">Docs</a><span>/</span><strong>HTTP API</strong>
        <a className="doc-switch" href="/#/doc/cli">{t("api.switchCli")}</a>
      </div>
      <div className="api-doc-redoc">
        <RedocStandalone options={options} specUrl={openApiUrl} />
      </div>
    </section>
  );
}
