type Props = { active: "explore" | "search" | "doc" };

export function SiteHeader({ active }: Props) {
  return (
    <header className="topbar">
      <a className="brand" href="#/explore" aria-label="ReIndex Explore">
        <span className="brand-mark" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span>reIndex</span>
      </a>
      <nav className="main-nav" aria-label="主要导航">
        <a className={active === "explore" ? "active" : ""} href="#/explore">
          Explore
        </a>
        <a className={active === "search" ? "active" : ""} href="#/search">
          Search
        </a>
        <a className={active === "doc" ? "active" : ""} href="#/doc">
          Docs
        </a>
        <a href="https://github.com/yechenyan/reIndex/tree/main/wiki" rel="noreferrer" target="_blank">Wiki ↗</a>
        <a href="https://github.com/yechenyan/reIndex" rel="noreferrer" target="_blank">
          GitHub ↗
        </a>
      </nav>
      <span className="protocol-badge">Protocol 1.0</span>
    </header>
  );
}
