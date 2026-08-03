---
spec: reindex/node@1.0
id: c94ee20f-ef4c-4344-8241-ae2c22324357
kind: table
order: 9
title: Maßnahmenplan aller Spannungsebenen für zehn Jahre
description: 52 项电网措施及项目、时间、成本和状态信息。
source:
  uri: raw://2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf
  sha256: 3dc36a9917ac29b387c8fcc6e1a856f26e4fc0660d4e847a5070ee7dca0af497
  locator:
    pages:
    - 5
    - 5
content:
  uri: ./00009--massnahmenplan-aller-spannungsebenen-fur-zehn-jahre.csv
  media_type: text/csv
  sha256: f7549ec86d3a4cf2fef64173bb85c85adcbfa348d349163d323e145e35cf2db5
assets:
- uri: ./00009--massnahmenplan-aller-spannungsebenen-fur-zehn-jahre.assets001.png
  media_type: image/png
  sha256: 4297fa342cf5a6d897961a37b900230cbf26895ef67b344f1714580bf953ffe4
  role: visual_reference
  description: PDF page 5 view associated with this external table.
table:
  columns:
  - description: Values recorded in the lfd. Nr. column.
    name: lfd. Nr.
    type: string
  - description: Values recorded in the Maßnahme column.
    name: Maßnahme
    type: string
  - description: Values recorded in the Betroffener Netzknoten im überlagerten HöS-Netz
      column.
    name: Betroffener Netzknoten im überlagerten HöS-Netz
    type: string
  - description: Values recorded in the Kurze Projektbeschreibung column.
    name: Kurze Projektbeschreibung
    type: string
  - description: Values recorded in the Projektkategorie column.
    name: Projektkategorie
    type: string
  - description: Values recorded in the Betriebsmittel column.
    name: Betriebsmittel
    type: string
  - description: Values recorded in the Länge Leitungsabschnitt [km] column.
    name: Länge Leitungsabschnitt [km]
    type: string
  - description: Values recorded in the Änderung Übertragungskapazität [+/- MVA] column.
    name: Änderung Übertragungskapazität [+/- MVA]
    type: string
  - description: Values recorded in the Netztechnische Begründung column.
    name: Netztechnische Begründung
    type: string
  - description: Values recorded in the Überwiegender Ausbaugrund column.
    name: Überwiegender Ausbaugrund
    type: string
  - description: Values recorded in the Bestehenden Engpass beheben column.
    name: Bestehenden Engpass beheben
    type: string
  - description: Values recorded in the Prognostiziertem Engpass vorbeugen column.
    name: Prognostiziertem Engpass vorbeugen
    type: string
  - description: Values recorded in the Voraussichtlicher Baubeginn [MM/JJJJ] column.
    name: Voraussichtlicher Baubeginn [MM/JJJJ]
    type: string
  - description: Values recorded in the Voraussichtliche Inbetriebnahme [MM/JJJJ]
      column.
    name: Voraussichtliche Inbetriebnahme [MM/JJJJ]
    type: string
  - description: Values recorded in the Verzögerungsgrund column.
    name: Verzögerungsgrund
    type: string
  - description: Values recorded in the Kosten (geschätzt) in Euro column.
    name: Kosten (geschätzt) in Euro
    type: string
  - description: Values recorded in the Projektstatus column.
    name: Projektstatus
    type: string
  - description: Values recorded in the Stand Genehmigungsverfahren column.
    name: Stand Genehmigungsverfahren
    type: string
  - description: Values recorded in the Geprüfte Alternativen column.
    name: Geprüfte Alternativen
    type: string
  - description: Values recorded in the Vorrangige Netz- oder Umspannebene column.
    name: Vorrangige Netz- oder Umspannebene
    type: string
  grain: One row from the source table.
  row_count: 52
---
## Overview

52 项电网措施及项目、时间、成本和状态信息。

## Document position

- Pages: 5

## Data profile

| Field | Type | Non-empty | Missing | Missing rate | Unique | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| lfd. Nr. | string | 52 | 0 | 0.0% | 52 |  |  |
| Maßnahme | string | 52 | 0 | 0.0% | 40 |  |  |
| Betroffener Netzknoten im überlagerten HöS-Netz | string | 52 | 0 | 0.0% | 1 |  |  |
| Kurze Projektbeschreibung | string | 52 | 0 | 0.0% | 20 |  |  |
| Projektkategorie | string | 52 | 0 | 0.0% | 3 |  |  |
| Betriebsmittel | string | 52 | 0 | 0.0% | 12 |  |  |
| Länge Leitungsabschnitt [km] | string | 52 | 0 | 0.0% | 4 |  |  |
| Änderung Übertragungskapazität [+/- MVA] | string | 14 | 38 | 73.1% | 5 |  |  |
| Netztechnische Begründung | string | 52 | 0 | 0.0% | 14 |  |  |
| Überwiegender Ausbaugrund | string | 52 | 0 | 0.0% | 2 |  |  |
| Bestehenden Engpass beheben | string | 52 | 0 | 0.0% | 1 |  |  |
| Prognostiziertem Engpass vorbeugen | string | 52 | 0 | 0.0% | 2 |  |  |
| Voraussichtlicher Baubeginn [MM/JJJJ] | string | 52 | 0 | 0.0% | 36 |  |  |
| Voraussichtliche Inbetriebnahme [MM/JJJJ] | string | 52 | 0 | 0.0% | 35 |  |  |
| Verzögerungsgrund | string | 13 | 39 | 75.0% | 3 |  |  |
| Kosten (geschätzt) in Euro | string | 52 | 0 | 0.0% | 34 |  |  |
| Projektstatus | string | 52 | 0 | 0.0% | 5 |  |  |
| Stand Genehmigungsverfahren | string | 52 | 0 | 0.0% | 5 |  |  |
| Geprüfte Alternativen | string | 52 | 0 | 0.0% | 3 |  |  |
| Vorrangige Netz- oder Umspannebene | string | 51 | 1 | 1.9% | 4 |  |  |

## Preview

| lfd. Nr. | Maßnahme | Betroffener Netzknoten im überlagerten HöS-Netz | Kurze Projektbeschreibung | Projektkategorie | Betriebsmittel | Länge Leitungsabschnitt [km] | Änderung Übertragungskapazität [+/- MVA] | Netztechnische Begründung | Überwiegender Ausbaugrund | Bestehenden Engpass beheben | Prognostiziertem Engpass vorbeugen | Voraussichtlicher Baubeginn [MM/JJJJ] | Voraussichtliche Inbetriebnahme [MM/JJJJ] | Verzögerungsgrund | Kosten (geschätzt) in Euro | Projektstatus | Stand Genehmigungsverfahren | Geprüfte Alternativen | Vorrangige Netz- oder Umspannebene |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4aa | UW Universität - UW Zwinger | keine Betroffenheit | Kabelneubau / Netzverstärkung zur Optimierung des 110kV-Kabelnetzes | Neubau | 110-kV-Kabel | 3,3 | +152 | Änderung der Versorgungsaufgabe durch Umbau der 380kV-Kuppelstellen und Änderung der n-1-Versorgung des UW Universität von 10kV- auf 110kV | Kein Zubau (reiner Ersatz) | Nein | Ja, um einem verbrauchsbedingten Engpass vorzubeugen | 04/2021 | 06/2023 | b) Genehmigungsprozess | 3.593.000 € | im Bau | abgeschlossen | alternativlos | HS |
| 5a | UW Kraftwerk | keine Betroffenheit | Austausch konventioneller Technik | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | Leittechnik u. Netzschutz | k.A. |  | Altersbedingte Erneuerung | Kein Zubau (reiner Ersatz) | Nein | Nein | XX/2017 | XX/2018 |  | 1.800.000 € | abgeschlossen | Bitte auswählen! | alternativlos | UW HS auf MS |
| 6aa | UW Zwinger | keine Betroffenheit | Austausch konventioneller Technik | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | Leittechnik u. Netzschutz | k.A. |  | Altersbedingte Erneuerung | Kein Zubau (reiner Ersatz) | Nein | Nein | xx/2019 | xx/2020 | d) intern | 820.000 € | abgeschlossen | Bitte auswählen! | alternativlos | UW HS auf MS |
| 7a | UW Sennestadt | keine Betroffenheit | Austausch konventioneller Technik | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | Leittechnik u. Netzschutz | k.A. |  | Altersbedingte Erneuerung | Kein Zubau (reiner Ersatz) | Nein | Nein | XX/2017 | 06/2019 |  | 775.000 € | abgeschlossen | Bitte auswählen! | alternativlos | UW HS auf MS |
| 8aa | UW Stieghorst | keine Betroffenheit | Austausch konventioneller Technik | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | Leittechnik u. Netzschutz | k.A. |  | Altersbedingte Erneuerung | Kein Zubau (reiner Ersatz) | Nein | Nein | 12/2020 | 06/2021 |  | 850.000 € | abgeschlossen | Bitte auswählen! | alternativlos | UW HS auf MS |
