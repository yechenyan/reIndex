# PaddleOCR SWS 表格提取（test5-table6）

- 状态：等待人工审核
- 日期：2026-08-09

## 用户原始请求

> 在这个项目 table-orc，使用 https://github.com/PADDLEPADDLE/PADDLEOCR 解析/Users/maxiao/Documents/code2/reIndex/testbase/test5-table6/sws-netze-solingen-2024/sws_netze_solingen_gmbh_netzausbauplan_2024_pdf.pdf 中 的表格，输出到reIndex/testbase/test5-table6/sws-netze-solingen-2024/output

## 范围与假设

- 使用本机已安装的 PaddleOCR 2.10.0 的 PP-Structure CPU 表格识别流程。
- 处理全部 17 页 PDF，将识别出的表格以 HTML、CSV、JSON 和页级证据图写入指定 `output/`。
- 这是生成测试数据的任务；不修改 ReIndex 的产品代码、API 或用户文档。

## 验收检查

- 目标输出目录包含可读取的汇总清单和每张检测到的表格产物。
- 汇总清单记录页码、坐标、表格尺寸和输出文件路径。
- 运行记录包含实际 PaddleOCR 版本、命令和结果。

## 实施结果

- 使用 PaddleOCR 2.10.0 / PaddlePaddle 3.3.1 的 CPU PP-Structure，在 200 DPI 下扫描全部 17 页。
- 识别出 4 张物理表：第 4 页（25x2）、第 6 页（5x3）、第 14 页（7x4）和第 16 页（9x15）。
- 每张表均输出为 `output/tables/` 下的 HTML 和 UTF-8 CSV；`output/tables.json` 是页码、坐标、尺寸与相对文件路径的汇总清单。`output/pages/` 保留全部页级 PNG 证据。
- 第 16 页的宽表可能在第 17 页续页，但 PP-Structure 本次没有在第 17 页检出独立表格；本次结果忠实保留 PaddleOCR 的检测输出，未做跨页推断或人工补录。

## 后续优化请求（2026-08-09）

> 感觉效果不是很好，表格有很多问题，有办法优化么？

- 重新比对 PDF 原页与 PaddleOCR 产物，定位检测、版面、单元格结构、OCR 与跨页拼接问题；在不更换用户指定 PaddleOCR 路线的前提下，制定并在合适时实施改进提取。

## PP-OCRv6 核对

- 首轮没有使用 PP-OCRv6：实际环境为 PaddleOCR 2.10.0 的旧 `PPStructure` API。
- PP-OCRv6 是当前 3.x 系列的文本检测/识别能力；要改善本任务还应一并升级到 PP-StructureV3 的表格结构管线。仅替换文字 OCR 不能独立修复宽表的行列和跨页结构错误。

## PP-OCRv6 升级重试（2026-08-09）

- 在独立的 `reIndex/.venv-paddleocr3` 中安装官方 `main` 开发版 PaddleOCR 3.8.0.dev11+g2661c7c0、PaddlePaddle 3.3.1 和 `paddlex[ocr]`；保留原有 2.10 环境不变。
- 以 300 DPI 重渲染第 6、14、16、17 页，使用 PP-StructureV3，并显式传入 `PP-OCRv6_medium_det`、`PP-OCRv6_medium_rec`、`SLANeXt_wired` 和 `RT-DETR-L_wired_table_cell_det`。运行日志确认四个模型均实际加载。
- 新结果写入 `testbase/test5-table6/sws-netze-solingen-2024/output/ppstructurev3/results-v6/`，每页含 JSON、HTML、XLSX、布局/OCR/单元格可视化证据；旧 2.x 结果未覆盖。
- 第 6 页恢复为完整 5x3（15 个非空单元格）；第 14 页恢复为正确的 7x4 表，保留 `Maßnahme`、`Geschätzte` 和欧元符号。第 16、17 页均被检出，分别为 9x15 和 6x15，因而不再漏掉续页。
- 限制：超宽表的结构仍非完全正确：`Nr.` 被移到末列且仍为 15 列，不是源表的 16 列。因此 v6 已解决文字识别问题、V3 已解决第 17 页漏检，但不能单靠模型完成宽表的列顺序/跨页业务合并；若需要可用的最终总表，后续应按 PDF 网格和文字坐标进行确定性后处理。

## Bielefelder 对比请求（2026-08-09）

> 试试 reIndex/testbase/test5-table6/bielefelder-netz-2022/2022_07_28_netzausbauplan_bielefelder_netz_gmbh_2022_inkl_anhang_pdf.pdf 这个的效果

- 使用同一 PP-StructureV3 + PP-OCRv6 medium + 有线表格模型流程，单独输出并报告检测、结构和跨页表现。
- PDF 共 5 页；第 5 页是一个极宽的嵌入式电子表格页面。以 300 DPI 单页运行，输入尺寸 4963x3509 超过模型 4000 像素上限，管线按比例缩小后推理。
- 检出 3 个区域：`17x14` 的说明/汇总区、`4x2` 的说明区，以及 `9x16` 的主措施区。第 3 个区域对应主表，但视觉源表实际有远多于 9 行和 16 列；结果将大量内容合并到单元格，不能作为可用的行级措施表。
- 结论：PP-OCRv6 对文字读取有帮助，但此类把完整 Excel 工作表缩小嵌入 A4 PDF 的极宽、极密网格超过 PP-StructureV3 的可恢复范围。应优先取得原始 XLSX；若只能使用 PDF，需要对主表单独高分辨率分块裁切，再依据矢量网格做拼接。

## 验证记录

- `/Users/maxiao/Documents/code2/nap_gridextractor/.venv/bin/python -u output/extract_tables.py`：完成，生成 4 张表和汇总清单。
- `/Users/maxiao/Documents/code2/nap_gridextractor/.venv/bin/python -m py_compile output/extract_tables.py`：通过。
- 逐项读取 `tables.json` 以及所有 CSV：汇总的 4 个 CSV/HTML 路径均存在，声明的行列数分别与 CSV 实际行列数一致。
- 升级运行命令（按单页重跑）：`paddleocr pp_structurev3 -i <page>.png --text_detection_model_name PP-OCRv6_medium_det --text_recognition_model_name PP-OCRv6_medium_rec --wired_table_structure_recognition_model_name SLANeXt_wired --wired_table_cells_detection_model_name RT-DETR-L_wired_table_cell_det`，其余非表格模块禁用。
- 读取全部 4 个升级 XLSX：页 6=`5x3`、页 14=`7x4`、页 16=`9x15`、页 17=`6x15`；结果文件均存在且可由 `openpyxl` 打开。
- Bielefelder 第 5 页输出的 3 个 XLSX 均可由 `openpyxl` 打开，尺寸为 `17x14`、`4x2`、`9x16`；对应布局、OCR 和单元格可视化证据均已写入该 PDF 自己的 `output/ppstructurev3/results-v6/`。

## 文档审查

- 仅新增测试数据和可复跑的提取脚本；未改变产品行为、API、CLI 或当前用户文档，因此 README 与 wiki 无需更新。
