---
spec: "reindex/node@1.0"
id: "0d08c3e5-fc02-4614-9666-ca73f35b9211"
kind: "table"
order: 6
title: "Maßnahmenplan aller Spannungsebenen für zehn Jahre"
description: "52 geplante Netzmaßnahmen mit Projekt-, Termin-, Kosten- und Statusangaben."
source:
  uri: "raw://2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf"
  sha256: "3dc36a9917ac29b387c8fcc6e1a856f26e4fc0660d4e847a5070ee7dca0af497"
  locator:
    pages: [5, 5]
content:
  uri: "./00006--massnahmenplan-aller-spannungsebenen.csv"
  media_type: "text/csv"
  sha256: "f7549ec86d3a4cf2fef64173bb85c85adcbfa348d349163d323e145e35cf2db5"
assets:
  - uri: "./00006--massnahmenplan-aller-spannungsebenen.assets001.png"
    media_type: "image/png"
    sha256: "ba5ca0692acffa22f00fbc6d2a5f1d627bc6cedd20041de38e29711effc075f3"
    role: "visual_reference"
    description: "Originalansicht der aus dem PDF extrahierten Tabelle."
table:
  row_count: 52
  grain: "Eine Zeile entspricht einer Maßnahme mit eindeutiger laufender Nummer."
  columns:
    - name: "lfd. Nr."
      type: "string"
      description: "Vom Betreiber vergebene laufende Identifikation der Maßnahme."
    - name: "Maßnahme"
      type: "string"
      description: "Bezeichnung der Maßnahme oder Anlage."
    - name: "Betroffener Netzknoten im überlagerten HöS-Netz"
      type: "string"
      description: "Betroffenheit im vorgelagerten Höchstspannungsnetz."
    - name: "Kurze Projektbeschreibung"
      type: "string"
      description: "Kurzbeschreibung des geplanten Projekts."
    - name: "Projektkategorie"
      type: "string"
      description: "Neubau-, Ersatz-, Optimierungs- oder Rückbaukategorie."
    - name: "Betriebsmittel"
      type: "string"
      description: "Betroffenes technisches Betriebsmittel."
    - name: "Länge Leitungsabschnitt [km]"
      type: "string"
      description: "Länge des betroffenen Leitungsabschnitts laut PDF."
    - name: "Änderung Übertragungskapazität [+/- MVA]"
      type: "string"
      description: "Änderung der Übertragungskapazität laut PDF."
    - name: "Netztechnische Begründung"
      type: "string"
      description: "Technische Begründung für die Maßnahme."
    - name: "Überwiegender Ausbaugrund"
      type: "string"
      description: "Überwiegender erzeugungs- oder verbrauchsbezogener Grund."
    - name: "Bestehenden Engpass beheben"
      type: "string"
      description: "Angabe zur Behebung eines bestehenden Engpasses."
    - name: "Prognostiziertem Engpass vorbeugen"
      type: "string"
      description: "Angabe zur Vorbeugung eines prognostizierten Engpasses."
    - name: "Voraussichtlicher Baubeginn [MM/JJJJ]"
      type: "string"
      description: "Geplanter Beginn im Originalformat."
    - name: "Voraussichtliche Inbetriebnahme [MM/JJJJ]"
      type: "string"
      description: "Geplante Inbetriebnahme im Originalformat."
    - name: "Verzögerungsgrund"
      type: "string"
      description: "Angegebener Grund einer Verzögerung."
    - name: "Kosten (geschätzt) in Euro"
      type: "string"
      description: "Kostenschätzung einschließlich Originalformat und Währungssymbol."
    - name: "Projektstatus"
      type: "string"
      description: "Projektstatus zum Dokumentstand."
    - name: "Stand Genehmigungsverfahren"
      type: "string"
      description: "Stand des Genehmigungsverfahrens."
    - name: "Geprüfte Alternativen"
      type: "string"
      description: "Vom Betreiber angegebene geprüfte Alternative."
    - name: "Vorrangige Netz- oder Umspannebene"
      type: "string"
      description: "Vorrangig betroffene Netz- oder Umspannebene."
  primary_key: ["lfd. Nr."]
warnings:
  - "Zeilenumbrüche innerhalb der PDF-Zellen wurden zu einfachen Leerzeichen normalisiert."
---
## Überblick

52 geplante Netzmaßnahmen mit Projekt-, Termin-, Kosten- und Statusangaben. Die vollständigen 52 Zeilen liegen in der unter `content.uri` referenzierten CSV-Datei.

## Preview

| lfd. Nr. | Maßnahme | Projektkategorie | Voraussichtlicher Baubeginn [MM/JJJJ] | Voraussichtliche Inbetriebnahme [MM/JJJJ] | Kosten (geschätzt) in Euro | Projektstatus | Vorrangige Netz- oder Umspannebene |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4aa | UW Universität - UW Zwinger | Neubau | 04/2021 | 06/2023 | 3.593.000 € | im Bau | HS |
| 5a | UW Kraftwerk | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | XX/2017 | XX/2018 | 1.800.000 € | abgeschlossen | UW HS auf MS |
| 6aa | UW Zwinger | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | xx/2019 | xx/2020 | 820.000 € | abgeschlossen | UW HS auf MS |
| 7a | UW Sennestadt | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | XX/2017 | 06/2019 | 775.000 € | abgeschlossen | UW HS auf MS |
| 8aa | UW Stieghorst | Ersatz(neubau) ohne Erhöhung der Übertragungskapazität | 12/2020 | 06/2021 | 850.000 € | abgeschlossen | UW HS auf MS |
