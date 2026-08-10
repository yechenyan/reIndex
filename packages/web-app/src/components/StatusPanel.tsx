import { useI18n } from "../i18n";
import type { ReactNode } from "react";

const ISSUE_URL = "https://github.com/yechenyan/reIndex/issues/new?title=%E8%AF%B7%E6%B1%82%E5%90%AF%E5%8A%A8%20ReIndex%20%E6%9C%8D%E5%8A%A1&body=%E6%88%91%E5%B8%8C%E6%9C%9B%E4%BD%BF%E7%94%A8%20ReIndex%20%E7%9A%84%E6%9C%8D%E5%8A%A1%EF%BC%8C%E8%AF%B7%E5%90%AF%E5%8A%A8%E5%90%8E%E7%AB%AF%E3%80%82";

export function ServiceStartRequest() {
  const { t } = useI18n();
  return <a className="button-primary service-request" href={ISSUE_URL} rel="noreferrer" target="_blank">{t("service.requestStart")}</a>;
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
