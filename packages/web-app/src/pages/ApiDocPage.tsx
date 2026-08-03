import { ApiReferenceReact } from "@scalar/api-reference-react";
import "@scalar/api-reference-react/style.css";

export function ApiDocPage() {
  return (
    <section className="api-doc-page">
      <div className="doc-subnav">
        <a href="#/doc">Docs</a><span>/</span><strong>HTTP API</strong>
        <a className="doc-switch" href="#/doc/cli">查看 CLI 文档</a>
      </div>
      <ApiReferenceReact
        configuration={{
          url: "/openapi.json",
          hideClientButton: true,
          showSidebar: true,
          theme: "default",
        }}
      />
    </section>
  );
}
