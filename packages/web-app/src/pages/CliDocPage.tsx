import { useEffect, useMemo, useState } from "react";
import type { CliCommand, CliContract, CliParameter } from "../docTypes";

function parameterLabel(parameter: CliParameter) {
  return parameter.flags?.join(", ") || parameter.name;
}

function detail(parameter: CliParameter) {
  const parts = [parameter.type];
  if (parameter.required) parts.push("required");
  if (parameter.default !== undefined) parts.push(`default: ${parameter.default}`);
  if (parameter.choices) parts.push(`one of: ${parameter.choices.join(" | ")}`);
  if (parameter.minimum !== undefined) {
    parts.push(`range: ${parameter.minimum}–${parameter.maximum}`);
  }
  return parts.join(" · ");
}

function CommandDetail({ command }: { command: CliCommand }) {
  return (
    <article className="cli-command">
      <p className="eyebrow">COMMAND</p>
      <h1><code>rei {command.path.join(" ")}</code></h1>
      <p className="cli-summary">{command.summary}</p>
      <h2>Parameters</h2>
      <div className="parameter-list">
        {command.parameters.length === 0 && <p>No parameters.</p>}
        {command.parameters.map((parameter) => (
          <div className="parameter" key={parameter.name}>
            <code>{parameterLabel(parameter)}</code>
            <span>{detail(parameter)}</span>
            <p>{parameter.description}</p>
          </div>
        ))}
      </div>
      {command.constraints && <>
        <h2>Constraints</h2>
        <ul>{command.constraints.map((item) => <li key={item.message}>{item.message}</li>)}</ul>
      </>}
      <h2>Examples</h2>
      {command.examples.map((example) => <pre key={example}><code>{example}</code></pre>)}
      <h2>Side effects</h2>
      <p>{command.side_effects.length ? command.side_effects.join(" ") : "Read-only."}</p>
      <h2>Success response</h2>
      <p><code>{command.output_schema.$ref.split("/").at(-1)}</code> JSON Schema</p>
    </article>
  );
}

function OutputProtocol({ values }: { values: Record<string, string> }) {
  return (
    <section className="output-protocol">
      <h2>Output protocol</h2>
      <dl>
        {Object.entries(values).map(([name, description]) => (
          <div key={name}><dt>{name.replaceAll("_", " ")}</dt><dd>{description}</dd></div>
        ))}
      </dl>
    </section>
  );
}

export function CliDocPage() {
  const [contract, setContract] = useState<CliContract | null>(null);
  const [selected, setSelected] = useState("init");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/doc/cli-v1.json")
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then(setContract)
      .catch((reason) => setError(String(reason)));
  }, []);

  const commands = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (contract?.commands || []).filter((command) =>
      `${command.path.join(" ")} ${command.summary}`.toLowerCase().includes(needle),
    );
  }, [contract, query]);
  const command = contract?.commands.find((item) => item.id === selected);

  if (error) return <section className="doc-state">CLI contract 加载失败：{error}</section>;
  if (!contract) return <section className="doc-state">正在加载 CLI 契约…</section>;
  return (
    <section className="cli-doc-page">
      <aside className="cli-sidebar">
        <div className="doc-subnav"><a href="#/doc">Docs</a><span>/</span><strong>CLI</strong></div>
        <label><span className="sr-only">搜索命令</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索命令…" />
        </label>
        <nav aria-label="CLI 命令">
          {commands.map((item) => (
            <button className={item.id === selected ? "active" : ""} key={item.id} onClick={() => setSelected(item.id)}>
              <code>rei {item.path.join(" ")}</code><span>{item.summary}</span>
            </button>
          ))}
        </nav>
      </aside>
      <div className="cli-content">
        <div className="cli-contract-badge">{contract.spec} · 自动生成</div>
        <OutputProtocol values={contract.program.output} />
        {command && <CommandDetail command={command} />}
      </div>
    </section>
  );
}
