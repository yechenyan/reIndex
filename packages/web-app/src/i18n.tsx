import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Language = "de" | "en" | "zh";
type Dictionary = Record<string, Record<Language, string>>;

const messages: Dictionary = {
  "nav.home": { de: "Start", en: "Home", zh: "首页" },
  "nav.explore": { de: "Erkunden", en: "Explore", zh: "浏览" },
  "nav.search": { de: "Suche", en: "Search", zh: "搜索" },
  "nav.tables": { de: "Tabellen", en: "Tables", zh: "表格" },
  "nav.docs": { de: "Dokumentation", en: "Docs", zh: "文档" },
  "nav.wiki": { de: "Wiki ↗", en: "Wiki ↗", zh: "Wiki ↗" },
  "nav.github": { de: "GitHub ↗", en: "GitHub ↗", zh: "GitHub ↗" },
  "nav.label": { de: "Hauptnavigation", en: "Main navigation", zh: "主要导航" },
  "language.label": { de: "Sprache", en: "Language", zh: "语言" },
  "app.loadingDocs": { de: "Dokumentation wird geladen…", en: "Loading documentation…", zh: "正在加载文档…" },
  "home.eyebrow": { de: "PORTABLES WISSEN FÜR AGENTEN", en: "PORTABLE KNOWLEDGE FOR AGENTS", zh: "面向智能体的可移植知识" },
  "home.title": { de: "Aus lokalen Dateien wird verlässliches Wissen.", en: "Turn local files into dependable knowledge.", zh: "将本地文件转化为可信知识。" },
  "home.description": { de: "ReIndex bringt Dateien, Struktur und Evidenz in ein tragbares Wissenspaket – damit Menschen und Agenten Quellen sicher finden, prüfen und nutzen können.", en: "ReIndex turns files, structure, and evidence into a portable knowledge package, so people and agents can find, verify, and use sources with confidence.", zh: "ReIndex 将文件、结构与证据组织为可移植的知识包，让人和智能体都能可靠地查找、核验和使用来源。" },
  "home.explore": { de: "Collections erkunden", en: "Explore Collections", zh: "浏览 Collection" },
  "home.search": { de: "Evidenz suchen", en: "Search evidence", zh: "搜索证据" },
  "home.boardsLabel": { de: "ReIndex Funktionen", en: "ReIndex features", zh: "ReIndex 功能" },
  "home.boardsEyebrow": { de: "DER REINDEX-FLUSS", en: "THE REINDEX FLOW", zh: "REINDEX 工作流" },
  "home.boardsDescription": { de: "Von rohen Dateien zur nachvollziehbaren Antwort – jede Stufe bleibt mit ihren Quellen verbunden.", en: "From raw files to traceable answers: every stage stays connected to its sources.", zh: "从原始文件到可追溯的答案，每个阶段都与来源保持关联。" },
  "home.ingest.eyebrow": { de: "01 · AUFBEREITEN", en: "01 · PREPARE", zh: "01 · 准备" },
  "home.ingest.title": { de: "Dateien in Wissen verwandeln", en: "Turn files into knowledge", zh: "把文件变成知识" },
  "home.ingest.description": { de: "Bauen Sie aus PDFs, Markdown, CSV und weiteren lokalen Quellen eine stabile Collection mit nachvollziehbarer Struktur.", en: "Build a stable Collection from PDFs, Markdown, CSV, and other local sources with a traceable structure.", zh: "从 PDF、Markdown、CSV 和其他本地来源构建结构可追溯、稳定的 Collection。" },
  "home.ingest.details": { de: "Deterministische Packages|Node-Karten und Herkunft|Versioniert veröffentlichen", en: "Deterministic packages|Node cards and provenance|Versioned publishing", zh: "确定性知识包|Node 卡片与溯源|版本化发布" },
  "home.ingest.action": { de: "Dokumentation öffnen", en: "Open documentation", zh: "查看文档" },
  "home.discover.eyebrow": { de: "02 · FINDEN", en: "02 · DISCOVER", zh: "02 · 发现" },
  "home.discover.title": { de: "Evidenz statt bloßer Treffer", en: "Evidence, not just results", zh: "不仅是结果，更是证据" },
  "home.discover.description": { de: "Durchsuchen Sie Karten, Texte und Tabellen mit Keyword-, semantischer oder hybrider Suche und springen Sie zur Quelle.", en: "Search cards, text, and tables with keyword, semantic, or hybrid search, then jump straight to the source.", zh: "使用关键词、语义或混合搜索查询卡片、正文和表格，并直接定位到来源。" },
  "home.discover.details": { de: "BM25, Vektoren und Reranking|Durchsuchbare Tabellen|Aktive Version als Quelle", en: "BM25, vectors, and reranking|Searchable tables|Active version as source", zh: "BM25、向量与重排序|可检索的表格|以当前版本为来源" },
  "home.discover.action": { de: "Suche öffnen", en: "Open search", zh: "打开搜索" },
  "home.agent.eyebrow": { de: "03 · NUTZEN", en: "03 · USE", zh: "03 · 使用" },
  "home.agent.title": { de: "Für Menschen und Agenten", en: "For people and agents", zh: "服务于人和智能体" },
  "home.agent.description": { de: "Browsen Sie im Web, nutzen Sie die CLI oder verbinden Sie Agent Skills mit einem klaren Protokoll und präzisen Abrufen.", en: "Browse in the web app, use the CLI, or connect Agent skills with a clear protocol and precise retrieval.", zh: "在 Web 应用中浏览、使用 CLI，或通过清晰协议和精确获取连接 Agent Skills。" },
  "home.agent.details": { de: "CLI und HTTP API|Exaktes rei get|Portable Agent Skills", en: "CLI and HTTP API|Precise rei get|Portable Agent Skills", zh: "CLI 与 HTTP API|精确的 rei get|可移植 Agent Skills" },
  "home.agent.action": { de: "CLI ansehen", en: "View the CLI", zh: "查看 CLI" },
  "home.steps.eyebrow": { de: "VOM DATEISYSTEM ZUR ANTWORT", en: "FROM FILESYSTEM TO ANSWER", zh: "从文件系统到答案" },
  "home.steps.title": { de: "Ein Arbeitsfluss, der Quellen nicht verliert.", en: "A workflow that never loses the source.", zh: "不丢失来源的工作流。" },
  "home.steps.description": { de: "ReIndex trennt Struktur, Inhalt und Ressourcen, damit jede Antwort zu ihrem Ursprung zurückführt.", en: "ReIndex separates structure, content, and resources so every answer can lead back to its origin.", zh: "ReIndex 分离结构、内容与资源，使每个答案都能回溯到它的原始出处。" },
  "home.steps.items": { de: "01;Collection anlegen;Lokale Dateien erkennen und eindeutig beschreiben.|02;Package erzeugen;Nodes, Karten und Ressourcen deterministisch zusammenstellen.|03;Veröffentlichen;Inhalte prüfen, indexieren und als neue aktive Version bereitstellen.|04;Evidenz abrufen;Im Web, per CLI oder mit Agent Skills präzise Quellen verwenden.", en: "01;Create a Collection;Discover and describe local files with stable identities.|02;Build a package;Assemble Nodes, cards, and resources deterministically.|03;Publish a version;Validate, index, and make a new active version available.|04;Retrieve evidence;Use precise sources in the web app, CLI, or Agent skills.", zh: "01;创建 Collection;识别本地文件，并用稳定的身份描述它们。|02;构建知识包;确定性地组织 Node、卡片与资源。|03;发布版本;校验、索引并提供新的当前版本。|04;获取证据;在 Web、CLI 或 Agent Skills 中精确使用来源。" },
  "home.proof.eyebrow": { de: "GEBAUT FÜR VERTRAUEN", en: "BUILT FOR TRUST", zh: "为可信而构建" },
  "home.proof.title": { de: "Antworten bleiben überprüfbar, weil Wissen seine Herkunft behält.", en: "Answers remain verifiable because knowledge keeps its provenance.", zh: "知识保留其溯源，答案就始终可核验。" },
  "home.proof.items": { de: "Stabile Node-Identität;UUIDs, Reihenfolge und explizite Beziehungen machen Strukturen langfristig robust.|Präzise Ressourcen;rei get holt genau Karte, Content oder Asset statt einer unklaren Kopie.|Versionierte Collections;Die aktive Version ist durchsuchbar, ältere Stände lassen sich vergleichen oder zurückholen.", en: "Stable Node identity;UUIDs, ordering, and explicit relationships keep structures durable.|Precise resources;rei get retrieves the exact card, content, or asset instead of an ambiguous copy.|Versioned Collections;Search the active version, compare earlier states, or recover a previous release.", zh: "稳定的 Node 身份;UUID、顺序与显式关系使结构长期稳定。|精确的资源;rei get 精确获取卡片、内容或资源，而非模糊的复制品。|版本化 Collection;检索当前版本、比对历史状态，或恢复此前发布。" },
  "home.cta.eyebrow": { de: "BEREIT ZUM START", en: "READY TO START", zh: "准备开始" },
  "home.cta.title": { de: "Wissen aufbauen, das Menschen und Agenten wirklich nutzen können.", en: "Build knowledge that people and agents can genuinely use.", zh: "构建人和智能体都能真正使用的知识。" },
  "home.cta.description": { de: "Beginnen Sie mit dem CLI-Vertrag oder verbinden Sie Ihre Systeme über die dokumentierte HTTP API.", en: "Start with the CLI contract, or connect your systems through the documented HTTP API.", zh: "从 CLI 协议开始，或通过已文档化的 HTTP API 连接你的系统。" },
  "home.cta.cli": { de: "CLI-Dokumentation", en: "CLI documentation", zh: "CLI 文档" },
  "home.cta.api": { de: "API-Referenz", en: "API reference", zh: "API 参考" },
  "explore.loading.title": { de: "Verbindung zu ReIndex", en: "Connecting to ReIndex", zh: "连接 ReIndex" },
  "explore.loading.message": { de: "Collection-Verzeichnis wird gelesen…", en: "Reading the Collection directory…", zh: "正在读取 Collection 目录…" },
  "explore.empty.title": { de: "Noch keine Collections", en: "No Collections yet", zh: "还没有 Collection" },
  "explore.empty.message": { de: "Veröffentlichen Sie die erste Collection mit rei push – sie erscheint dann hier.", en: "Publish your first Collection with rei push and it will appear here.", zh: "使用 rei push 发布第一个 Collection 后，它会出现在这里。" },
  "explore.unavailable": { de: "Erkunden nicht verfügbar", en: "Explore unavailable", zh: "Explore 暂不可用" },
  "explore.title": { de: "Durchsuchen Sie nachvollziehbare Wissensstrukturen.", en: "Browse traceable knowledge structures.", zh: "浏览可追溯的知识结构。" },
  "tree.filter": { de: "Node-Namen filtern", en: "Filter Node names", zh: "筛选 Node 名称" },
  "tree.empty": { de: "Keine passenden Nodes", en: "No matching Nodes", zh: "没有匹配的 Node" },
  "node.choose.title": { de: "Node auswählen", en: "Select a Node", zh: "选择一个 Node" },
  "node.choose.message": { de: "Wählen Sie links im Collection-Baum die anzuzeigenden Daten aus.", en: "Choose the data to view from the Collection tree on the left.", zh: "从左侧 Collection tree 中选择需要查看的数据。" },
  "node.loading.title": { de: "Datenkarte wird gelesen", en: "Reading data card", zh: "读取数据卡" },
  "node.loading.message": { de: "{title} wird geladen…", en: "Loading {title}…", zh: "正在加载 {title}…" },
  "node.error": { de: "Node kann nicht gelesen werden", en: "Unable to read Node", zh: "无法读取 Node" },
  "node.copy": { de: "rei get kopieren", en: "Copy rei get", zh: "复制 rei get" },
  "node.copied": { de: "Kopiert", en: "Copied", zh: "已复制" },
  "node.tabs": { de: "Datenkarte|Inhaltsvorschau|Ressourcen", en: "Data card|Content preview|Resources", zh: "数据卡|内容预览|资源" },
  "node.noCard": { de: "Dieser Node hat noch keinen Datenkartentext.", en: "This Node has no data card body yet.", zh: "这个 Node 暂无数据卡正文。" },
  "content.loading": { de: "content wird gelesen…", en: "Reading content…", zh: "正在读取 content…" },
  "content.empty": { de: "Ein Group-Node hat keinen eigenen content. Wählen Sie links einen Kind-Node.", en: "A Group Node has no independent content. Select one of its children on the left.", zh: "Group Node 没有独立 content，请从左侧选择它的子节点。" },
  "content.tableEmpty": { de: "Die Tabelle ist leer.", en: "The table is empty.", zh: "表格为空。" },
  "content.rows": { de: "Erste {count} Zeilen", en: "First {count} rows", zh: "显示前 {count} 行" },
  "resources.empty": { de: "Dieser Group-Node hat keine eigenen Ressourcen.", en: "This Group Node has no independent resources.", zh: "这个 Group Node 没有独立资源。" },
  "resources.download": { de: "Herunterladen", en: "Download", zh: "下载" },
  "search.title": { de: "Antworten aus echten Quellen finden.", en: "Find answers in real sources.", zh: "从真实来源中找到答案。" },
  "search.description": { de: "Durchsuchen Sie Datenkarten, Text und Tabellenzeilen und springen Sie direkt zum passenden Node.", en: "Search data cards, text, and table rows, then jump directly to the matching Node.", zh: "搜索数据卡、正文与表格行，并直接回到对应 Node。" },
  "search.placeholder": { de: "z. B.: Wie sieht der Netzinvestitionsplan für die nächsten zehn Jahre aus?", en: "For example: What is the grid investment plan for the next ten years?", zh: "例如：未来十年的电网投资计划是什么？" },
  "search.submit": { de: "Suchen", en: "Search", zh: "搜索" },
  "search.searching": { de: "Suche läuft", en: "Searching", zh: "搜索中" },
  "search.reset": { de: "Zurücksetzen", en: "Reset", zh: "重置" },
  "search.mode": { de: "Suchmodus", en: "Search mode", zh: "搜索模式" },
  "search.types": { de: "Node-Typ", en: "Node type", zh: "Node 类型" },
  "search.hybrid": { de: "Volltext und Semantik kombiniert", en: "Full text and semantic search combined", zh: "全文与语义融合" },
  "search.lexical": { de: "Exakte Schlüsselwortsuche", en: "Exact keyword matching", zh: "精确关键词匹配" },
  "search.semantic": { de: "Ähnlichkeit natürlicher Sprache", en: "Natural-language similarity", zh: "自然语言相似度" },
  "search.scope": { de: "Die Suche umfasst eine Collection; Ergebnisse stammen immer aus der aktiven Version.", en: "Search is scoped to one Collection; results always come from the active version.", zh: "搜索范围是一个 Collection，结果始终读取 active version。" },
  "search.failed": { de: "Suche fehlgeschlagen", en: "Search failed", zh: "搜索失败" },
  "search.progress": { de: "Passende Evidenz wird zusammengestellt.", en: "Combining matching evidence.", zh: "正在组合匹配的 Evidence。" },
  "search.prompt": { de: "Vertrauenswürdige Evidenz durchsuchen", en: "Search trusted evidence", zh: "搜索可信证据" },
  "search.promptText": { de: "Wählen Sie eine Collection, geben Sie eine Frage ein und durchsuchen Sie Datenkarten, Text und Tabellenzeilen.", en: "Choose a Collection, enter a question, then search data cards, text, and table rows.", zh: "选择 Collection，输入问题，然后从数据卡、正文和表格行中查找结果。" },
  "search.none": { de: "Keine Ergebnisse", en: "No results found", zh: "没有找到结果" },
  "search.noneText": { de: "Versuchen Sie kürzere Schlüsselwörter, einen anderen Modus oder entfernen Sie den Node-Typfilter.", en: "Try shorter keywords, another mode, or remove the Node type filter.", zh: "尝试更短的关键词、其他模式或移除 Node 类型筛选。" },
  "search.sorted": { de: "Nach Relevanz sortiert", en: "Sorted by relevance", zh: "按相关性排序" },
  "search.open": { de: "In Explore öffnen →", en: "Open in Explore →", zh: "在 Explore 中打开 →" },
  "search.more": { de: "Weitere Ergebnisse laden", en: "Load more results", zh: "加载更多结果" },
  "search.moreLoading": { de: "Wird geladen…", en: "Loading…", zh: "加载中…" },
  "docs.intro": { de: "Menschenlesbarer Einstieg für CLI und HTTP API; Implementierung, Validierung und Dokumentation basieren auf demselben Vertrag.", en: "Human-readable entry point for the CLI and HTTP API; implementation, validation, and documentation share one contract.", zh: "CLI 与 HTTP API 的人类可读入口；实现、校验和文档使用同一份契约。" },
  "docs.cli.title": { de: "Befehlszeilenvertrag", en: "Command-line contract", zh: "命令行协议" },
  "docs.cli.desc": { de: "Automatisch aus dem reindex/cli@1.0-Vertrag erzeugte Befehle, Parameter, Einschränkungen und Beispiele.", en: "Commands, parameters, constraints, and examples generated from the reindex/cli@1.0 contract.", zh: "从 reindex/cli@1.0 契约自动生成的命令、参数、约束与示例。" },
  "docs.api.title": { de: "Service-Schnittstellenvertrag", en: "Service interface contract", zh: "服务接口协议" },
  "docs.api.desc": { de: "Durchsuchbare API-Referenz, automatisch aus dem reindex-http-v1-OpenAPI-Vertrag erzeugt.", en: "Searchable API reference generated from the reindex-http-v1 OpenAPI contract.", zh: "从 reindex-http-v1 OpenAPI 契约自动生成的可检索 API 参考文档。" },
  "docs.open": { de: "Dokumentation öffnen →", en: "Open documentation →", zh: "打开文档 →" },
  "cli.loadError": { de: "CLI-Vertrag konnte nicht geladen werden", en: "Failed to load CLI contract", zh: "CLI contract 加载失败" },
  "cli.loading": { de: "CLI-Vertrag wird geladen…", en: "Loading CLI contract…", zh: "正在加载 CLI 契约…" },
  "cli.search": { de: "Befehle suchen…", en: "Search commands…", zh: "搜索命令…" },
  "cli.commandNav": { de: "CLI-Befehle", en: "CLI commands", zh: "CLI 命令" },
  "cli.generated": { de: "automatisch erzeugt", en: "generated", zh: "自动生成" },
  "api.switchCli": { de: "CLI-Dokumentation anzeigen", en: "View CLI documentation", zh: "查看 CLI 文档" },
};

function defaultLanguage(): Language {
  const saved = localStorage.getItem("reindex-language");
  if (saved === "de" || saved === "en" || saved === "zh") return saved;
  return "de";
}

const I18nContext = createContext<{ language: Language; setLanguage: (value: Language) => void; t: (key: string, values?: Record<string, string | number>) => string } | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState(defaultLanguage);
  useEffect(() => { localStorage.setItem("reindex-language", language); document.documentElement.lang = language; }, [language]);
  const t = (key: string, values: Record<string, string | number> = {}) => (messages[key]?.[language] || key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
  return <I18nContext.Provider value={{ language, setLanguage, t }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used within I18nProvider");
  return context;
}
