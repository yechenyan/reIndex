---
spec: "reindex/node@1.0"
id: "333563cf-1334-45a5-9d19-55f53f79757f"
kind: "table"
order: 5
title: "Aggregierte 10-Jahresplanung der unteren Netzebenen"
description: "Investitionen nach Netzebene und Investitionsart in Euro."
source:
  uri: "raw://2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
  sha256: "3dc36a9917ac29b387c8fcc6e1a856f26e4fc0660d4e847a5070ee7dca0af497"
  locator:
    pages: [5, 5]
content:
  uri: "./00005--aggregierte-10-jahresplanung-untere-netzebenen.csv"
  media_type: "text/csv"
  sha256: "277478aeacb22bedd13facd01f40194de136a1dfba3639c24e61e81a286d59be"
assets:
  - uri: "./00005--aggregierte-10-jahresplanung-untere-netzebenen.assets001.png"
    media_type: "image/png"
    sha256: "3671980aa67aa6b38a3e5eab0b2069de68a83718dd203c0847ef57176cd700f0"
    role: "visual_reference"
    description: "Originalansicht der aus dem PDF extrahierten Tabelle."
table:
  row_count: 24
  grain: "Eine Zeile entspricht einer Netzebene und einer Investitionsart."
  columns:
    - name: "Netzebene"
      type: "string"
      description: "Betroffene untere Netzebene."
    - name: "Investitionsart"
      type: "string"
      description: "Kategorie der Zehnjahresinvestition."
    - name: "Betrag_EUR"
      type: "integer"
      description: "Im PDF ausgewiesener Betrag."
      unit: "EUR"
warnings:
  - "CSV ist deterministisch in ein langes, maschinenlesbares Format normalisiert."
---
## Überblick

Investitionen nach Netzebene und Investitionsart in Euro. Die vollständigen 24 Zeilen liegen in der unter `content.uri` referenzierten CSV-Datei.

## Preview

| Netzebene | Investitionsart | Betrag_EUR |
| --- | --- | --- |
| Mittelspannung | Neubau | 3242160 |
| Mittelspannung | Ersatz(neubau) mit Erhöhung der Übertragungskapazität | 19452960 |
| Mittelspannung | Netzoptimierung und -verstärkung | 8105400 |
| Mittelspannung | Summe Netzausbau | 30800520 |
| Mittelspannung | davon überwiegend erzeugungsgetrieben | 6160104 |
