---
spec: reindex/node@1.0
id: 3ac3c9ee-8a14-4f2d-9885-a6ed0aa69f72
kind: table
order: 3
title: Aggregierte 10-Jahresplanung der unteren Netzebenen
description: 按电压层级和投资类型整理的十年投资计划。
source:
  uri: raw://2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf
  sha256: 3dc36a9917ac29b387c8fcc6e1a856f26e4fc0660d4e847a5070ee7dca0af497
  locator:
    pages:
    - 5
    - 5
content:
  uri: ./00003--aggregierte-10-jahresplanung-der-unteren-netzebenen.csv
  media_type: text/csv
  sha256: 277478aeacb22bedd13facd01f40194de136a1dfba3639c24e61e81a286d59be
assets:
- uri: ./00003--aggregierte-10-jahresplanung-der-unteren-netzebenen.assets001.png
  media_type: image/png
  sha256: 4297fa342cf5a6d897961a37b900230cbf26895ef67b344f1714580bf953ffe4
  role: visual_reference
  description: PDF page 5 view associated with this external table.
table:
  columns:
  - description: Values for Netzebene.
    name: Netzebene
    type: string
  - description: Values for Investitionsart.
    name: Investitionsart
    type: string
  - description: Values for Betrag_EUR.
    name: Betrag_EUR
    type: integer
  grain: One row from the source table.
  row_count: 24
---
## Overview

按电压层级和投资类型整理的十年投资计划。

## Preview

| Netzebene | Investitionsart | Betrag_EUR |
| --- | --- | --- |
| Mittelspannung | Neubau | 3242160 |
| Mittelspannung | Ersatz(neubau) mit Erhöhung der Übertragungskapazität | 19452960 |
| Mittelspannung | Netzoptimierung und -verstärkung | 8105400 |
| Mittelspannung | Summe Netzausbau | 30800520 |
| Mittelspannung | davon überwiegend erzeugungsgetrieben | 6160104 |
