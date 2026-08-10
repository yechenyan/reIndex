import { useI18n } from "../i18n";
import type { ReactNode } from "react";

export function ServiceStartRequest() {
  const { t } = useI18n();
  const issueUrl = new URL("https://github.com/yechenyan/reIndex/issues/new");
  issueUrl.searchParams.set("title", "Request to start ReIndex service");
  issueUrl.searchParams.set("body", "I would like to use the ReIndex service. Please start the backend.");
  return <a className="button-primary service-request" href={issueUrl.toString()} rel="noreferrer" target="_blank">{t("service.requestStart")}</a>;
}

export function StatusPanel({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <section className="status-panel" role="status">
      <span className="status-glyph">R</span>
      <h2>{title}</h2>
      <p>{message}</p>
      {action}
    </section>
  );
}
