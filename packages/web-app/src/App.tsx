import { lazy, Suspense, useEffect, useState } from "react";
import { SiteHeader } from "./components/SiteHeader";
import { ExplorePage } from "./pages/ExplorePage";
import { HomePage } from "./pages/HomePage";
import { CliDocPage } from "./pages/CliDocPage";
import { DocHomePage } from "./pages/DocHomePage";
import { SearchPage } from "./pages/SearchPage";
import { TableQueryPage } from "./pages/TableQueryPage";
import { normalizeHash, readAppPath } from "./route";
import { I18nProvider, useI18n } from "./i18n";

const ApiDocPage = lazy(() =>
  import("./pages/ApiDocPage").then((module) => ({ default: module.ApiDocPage })),
);

function useRoute() {
  const [path, setPath] = useState(readAppPath);

  useEffect(() => {
    const update = () => {
      const normalized = normalizeHash(window.location.hash);
      if (window.location.pathname === "/" && normalized !== window.location.hash) {
        window.history.replaceState(null, "", normalized);
      }
      setPath(readAppPath());
    };
    update();
    window.addEventListener("hashchange", update);
    window.addEventListener("popstate", update);
    return () => {
      window.removeEventListener("hashchange", update);
      window.removeEventListener("popstate", update);
    };
  }, []);

  return path;
}

export function App() {
  return <I18nProvider><AppContent /></I18nProvider>;
}

function AppContent() {
  const path = useRoute();
  const { t } = useI18n();
  const active = path === "/"
    ? "home"
    : path.startsWith("/doc")
    ? "doc"
    : path === "/tables/query"
      ? "tables"
    : path === "/search"
      ? "search"
      : "explore";

  const page = () => {
    if (path === "/search") return <SearchPage />;
    if (path === "/tables/query") return <TableQueryPage />;
    if (path === "/doc/cli") return <CliDocPage />;
    if (path === "/doc/api") return <ApiDocPage />;
    if (path.startsWith("/doc")) return <DocHomePage />;
    if (path === "/") return <HomePage />;
    return <ExplorePage />;
  };

  return (
    <main className="app-shell">
      <SiteHeader active={active} />
      <Suspense fallback={<section className="doc-state">{t("app.loadingDocs")}</section>}>
        {page()}
      </Suspense>
    </main>
  );
}
