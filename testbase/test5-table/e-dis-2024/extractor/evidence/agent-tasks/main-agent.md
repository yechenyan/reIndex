# Main Agent

## Request

对 e_dis_netz_gmbh_netzausbauplan_2024_aktualisiert.pdf 进行全新、无历史产物的 PDF 表格提取泛化基准；提取全部可见表格，保留德文专有名词、数值、表头、跨页边界和逐行 provenance；独立 Finder/Extractor/QA，QA 使用 40 候选式（以实际候选数为准）的 keep/remove 断行决策。

## Objective

Own requirements, ambiguity decisions, merge decisions, and final review.

## Allowed inputs

All project evidence and reports.

## Prohibited inputs

Do not author QA source values.

## Repair scope

Process only these table IDs: table-16. Do not inspect or change other tables. Fixed validation protects unaffected outputs.

## Project boundary

Write only under `/Users/maxiao/Documents/code2/reIndex/testbase/test5-table/e-dis-2024`; final tables go in `output/` and all other artifacts in `extractor/`.
