---
spec: "reindex/input@1.0"

items:
  "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf":
    parse:
      text: auto
      images: auto
      tables: supplied
    description: "Bielefelder Netz GmbH 2022 年配电网扩建计划及附录。"

  "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv":
    part_of: "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    pages: [5, 5]
    title: "Aggregierte 10-Jahresplanung der unteren Netzebenen"
    description: "按电压层级和投资类型整理的十年投资计划。"
    quality:
      expected_rows: 24
      expected_columns:
        - "Netzebene"
        - "Investitionsart"
        - "Betrag_EUR"
      primary_key: ["Netzebene", "Investitionsart"]

  "00006--massnahmenplan-aller-spannungsebenen.csv":
    part_of: "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    pages: [5, 5]
    title: "Maßnahmenplan aller Spannungsebenen für zehn Jahre"
    description: "52 项电网措施及项目、时间、成本和状态信息。"
    quality:
      expected_rows: 52
      expected_columns:
        - "lfd. Nr."
        - "Maßnahme"
        - "Betroffener Netzknoten im überlagerten HöS-Netz"
        - "Kurze Projektbeschreibung"
        - "Projektkategorie"
        - "Betriebsmittel"
        - "Länge Leitungsabschnitt [km]"
        - "Änderung Übertragungskapazität [+/- MVA]"
        - "Netztechnische Begründung"
        - "Überwiegender Ausbaugrund"
        - "Bestehenden Engpass beheben"
        - "Prognostiziertem Engpass vorbeugen"
        - "Voraussichtlicher Baubeginn [MM/JJJJ]"
        - "Voraussichtliche Inbetriebnahme [MM/JJJJ]"
        - "Verzögerungsgrund"
        - "Kosten (geschätzt) in Euro"
        - "Projektstatus"
        - "Stand Genehmigungsverfahren"
        - "Geprüfte Alternativen"
        - "Vorrangige Netz- oder Umspannebene"
      primary_key: ["lfd. Nr."]

  "costs_2020.csv":
    title: "Technology costs 2020"
    description: "独立于 PDF 的技术成本数据，作为 Collection 根级 table Node。"
    quality:
      expected_rows: 1091
      expected_columns:
        - "technology"
        - "parameter"
        - "value"
        - "unit"
        - "source"
        - "further description"
        - "currency_year"

  "README.md":
    ignore: true
---

## 处理说明

这里省略了 `collection`，所以 Collection title 默认使用目录名 `test2`，description 由 `rei` 自动生成。

两张德文 CSV 是 PDF 第 5 页表格的权威提取结果，应放进 PDF 对应的 document group。PDF 的通用正文和
图片解析保持开启，通用表格解析关闭，避免再次生成重复或错误的表格。

`costs_2020.csv` 没有 `part_of` 或 `derived_from`，因此保持为 Collection 根级的独立数据表。
