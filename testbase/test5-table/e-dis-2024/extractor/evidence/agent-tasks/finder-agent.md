# Finder Agent

## Request

对 e_dis_netz_gmbh_netzausbauplan_2024_aktualisiert.pdf 进行全新、无历史产物的 PDF 表格提取泛化基准；提取全部可见表格，保留德文专有名词、数值、表头、跨页边界和逐行 provenance；独立 Finder/Extractor/QA，QA 使用 40 候选式（以实际候选数为准）的 keep/remove 断行决策。

## Objective

Inspect every PDF page and draft the complete logical-table Inventory.

## Allowed inputs

Finder packet, rolling contact sheets, pre-rendered candidate pages, and targeted uncertain pages.

## Prohibited inputs

Do not read extractor code, output, or prior answers. Start with finder-packet.json; do not rerender pages already supplied.

## Repair scope

Process only these table IDs: table-16. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/e-dis-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
