---
spec: reindex/node@1.0
id: c94ee20f-ef4c-4344-8241-ae2c22324357
kind: table
order: 4
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
  uri: ./00004--massnahmenplan-aller-spannungsebenen-fur-zehn-jahre.csv
  media_type: text/csv
  sha256: f7549ec86d3a4cf2fef64173bb85c85adcbfa348d349163d323e145e35cf2db5
assets:
- uri: ./00004--massnahmenplan-aller-spannungsebenen-fur-zehn-jahre.assets001.png
  media_type: image/png
  sha256: 4297fa342cf5a6d897961a37b900230cbf26895ef67b344f1714580bf953ffe4
  role: visual_reference
  description: PDF page 5 view associated with this external table.
table:
  row_count: 52
  grain: One row from the source table.
  columns:
  - name: lfd. Nr.
    type: string
    description: Values for lfd. Nr..
  - name: Maßnahme
    type: string
    description: Values for Maßnahme.
  - name: Betroffener Netzknoten im überlagerten HöS-Netz
    type: string
    description: Values for Betroffener Netzknoten im überlagerten HöS-Netz.
  - name: Kurze Projektbeschreibung
    type: string
    description: Values for Kurze Projektbeschreibung.
  - name: Projektkategorie
    type: string
    description: Values for Projektkategorie.
  - name: Betriebsmittel
    type: string
    description: Values for Betriebsmittel.
  - name: Länge Leitungsabschnitt [km]
    type: string
    description: Values for Länge Leitungsabschnitt [km].
  - name: Änderung Übertragungskapazität [+/- MVA]
    type: string
    description: Values for Änderung Übertragungskapazität [+/- MVA].
  - name: Netztechnische Begründung
    type: string
    description: Values for Netztechnische Begründung.
  - name: Überwiegender Ausbaugrund
    type: string
    description: Values for Überwiegender Ausbaugrund.
  - name: Bestehenden Engpass beheben
    type: string
    description: Values for Bestehenden Engpass beheben.
  - name: Prognostiziertem Engpass vorbeugen
    type: string
    description: Values for Prognostiziertem Engpass vorbeugen.
  - name: Voraussichtlicher Baubeginn [MM/JJJJ]
    type: string
    description: Values for Voraussichtlicher Baubeginn [MM/JJJJ].
  - name: Voraussichtliche Inbetriebnahme [MM/JJJJ]
    type: string
    description: Values for Voraussichtliche Inbetriebnahme [MM/JJJJ].
  - name: Verzögerungsgrund
    type: string
    description: Values for Verzögerungsgrund.
  - name: Kosten (geschätzt) in Euro
    type: string
    description: Values for Kosten (geschätzt) in Euro.
  - name: Projektstatus
    type: string
    description: Values for Projektstatus.
  - name: Stand Genehmigungsverfahren
    type: string
    description: Values for Stand Genehmigungsverfahren.
  - name: Geprüfte Alternativen
    type: string
    description: Values for Geprüfte Alternativen.
  - name: Vorrangige Netz- oder Umspannebene
    type: string
    description: Values for Vorrangige Netz- oder Umspannebene.
---
## Overview

52 项电网措施及项目、时间、成本和状态信息。

## Preview

| lfd. Nr. | Maßnahme | Betroffener Netzknoten im überlagerten HöS-Netz | Kurze Projektbeschreibung | Projektkategorie | Betriebsmittel | Länge Leitungsabschnitt [km] | Änderung Übertragungskapazität [+/- MVA] | Netztechnische Begründung | Überwiegender Ausbaugrund | Bestehenden Engpass beheben | Prognostiziertem Engpass vorbeugen | Voraussichtlicher Baubeginn [MM/JJJJ] | Voraussichtliche Inbetriebnahme [MM/JJJJ] | Verzögerungsgrund | Kosten (geschätzt) in Euro | Projektstatus | Stand Genehmigungsverfahren | Geprüfte Alternativen | Vorrangige Netz- oder Umspannebene |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4aa | UW Universität - UW Zwinger | keine Betroffenheit | Kabelneubau / Netzverstärkung zur Optimierung des 110kV-Kabelnetzes | Neubau | 110-kV-Kabel | 3,3 | +152 | Änderung der Versorgungsaufgabe durch Umbau der 380kV-Kuppelstellen und Änderung der n-1-Versorgung des UW Universität von 10kV- auf 110kV | Kein Zubau (reiner Ersatz) | Nein | Ja, um einem verbrauchsbedingten Engpass vorzubeugen | 04/2021 | 06/2023 | b) Genehmigungsprozess | 3.593.000 € | im Bau | abgeschlossen | alternativlos | HS |
| 5a | UW Kraftwerk | keine Betroffenheit | Austausch konventioneller Technik | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | Leittechnik u. Netzschutz | k.A. |  | Altersbedingte Erneuerung | Kein Zubau (reiner Ersatz) | Nein | Nein | XX/2017 | XX/2018 |  | 1.800.000 € | abgeschlossen | Bitte auswählen! | alternativlos | UW HS auf MS |
| 6aa | UW Zwinger | keine Betroffenheit | Austausch konventioneller Technik | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | Leittechnik u. Netzschutz | k.A. |  | Altersbedingte Erneuerung | Kein Zubau (reiner Ersatz) | Nein | Nein | xx/2019 | xx/2020 | d) intern | 820.000 € | abgeschlossen | Bitte auswählen! | alternativlos | UW HS auf MS |
| 7a | UW Sennestadt | keine Betroffenheit | Austausch konventioneller Technik | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | Leittechnik u. Netzschutz | k.A. |  | Altersbedingte Erneuerung | Kein Zubau (reiner Ersatz) | Nein | Nein | XX/2017 | 06/2019 |  | 775.000 € | abgeschlossen | Bitte auswählen! | alternativlos | UW HS auf MS |
| 8aa | UW Stieghorst | keine Betroffenheit | Austausch konventioneller Technik | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | Leittechnik u. Netzschutz | k.A. |  | Altersbedingte Erneuerung | Kein Zubau (reiner Ersatz) | Nein | Nein | 12/2020 | 06/2021 |  | 850.000 € | abgeschlossen | Bitte auswählen! | alternativlos | UW HS auf MS |
