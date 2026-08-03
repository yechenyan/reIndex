---
spec: "reindex/input@1.0"

items:
  "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf":
    parse:
      text: auto
      images: auto
      tables: "off"
    description: "Bielefelder Netz GmbH 2022 年配电网扩建计划及附录。"

  "00005--aggregierte-10-jahresplanung-untere-netzebenen.csv":
    part_of: "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    pages: [5, 5]
    title: "Aggregierte 10-Jahresplanung der unteren Netzebenen"
    description: "按电压层级和投资类型整理的十年投资计划。"


  "00006--massnahmenplan-aller-spannungsebenen.csv":
    part_of: "2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
    pages: [5, 5]
    title: "Maßnahmenplan aller Spannungsebenen für zehn Jahre"
    description: "52 项电网措施及项目、时间、成本和状态信息。"

  "costs_2020.csv":
    title: "Technology costs 2020"
    description: "独立于 PDF 的技术成本数据，作为 Collection 根级 table Node。"

---
