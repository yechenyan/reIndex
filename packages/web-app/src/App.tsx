import { lazy, Suspense, useEffect, useState } from "react";
import { SiteHeader } from "./components/SiteHeader";
import { ExplorePage } from "./pages/ExplorePage";
import { CliDocPage } from "./pages/CliDocPage";
import { DocHomePage } from "./pages/DocHomePage";
import { SearchPage } from "./pages/SearchPage";

const ApiDocPage = lazy(() =>
  import("./pages/ApiDocPage").then((module) => ({ default: module.ApiDocPage })),
);

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || "#/explore");

  useEffect(() => {
    if (!window.location.hash) window.location.hash = "/explore";
    const update = () => setHash(window.location.hash || "#/explore");
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  return hash;
}

export function App() {
  const hash = useHashRoute();
  const path = hash.slice(1).split("?")[0];
  const active = path.startsWith("/doc")
    ? "doc"
    : path === "/search"
      ? "search"
      : "explore";

  const page = () => {
    if (path === "/search") return <SearchPage />;
    if (path === "/doc/cli") return <CliDocPage />;
    if (path === "/doc/api") return <ApiDocPage />;
    if (path.startsWith("/doc")) return <DocHomePage />;
    return <ExplorePage />;
  };

  return (
    <main className="app-shell">
      <SiteHeader active={active} />
      <Suspense fallback={<section className="doc-state">正在加载文档…</section>}>
        {page()}
      </Suspense>
    </main>
  );
}
