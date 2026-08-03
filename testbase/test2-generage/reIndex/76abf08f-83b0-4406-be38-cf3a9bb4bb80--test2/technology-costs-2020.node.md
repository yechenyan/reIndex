---
spec: reindex/node@1.0
id: 91156259-ea05-4ee5-9a87-6ddf8ea9ae3e
kind: table
order: 2
title: Technology costs 2020
description: 独立于 PDF 的技术成本数据，作为 Collection 根级 table Node。
source:
  uri: raw://costs_2020.csv
  sha256: 44275688aa97dbc5f9f675ed07dfa3708f84651b74cc036c2eb28fe5aaf19532
content:
  uri: ./technology-costs-2020.csv
  media_type: text/csv
  sha256: 44275688aa97dbc5f9f675ed07dfa3708f84651b74cc036c2eb28fe5aaf19532
table:
  columns:
  - description: Values recorded in the technology column.
    name: technology
    type: string
  - description: Values recorded in the parameter column.
    name: parameter
    type: string
  - description: Values recorded in the value column.
    name: value
    type: decimal
  - description: Values recorded in the unit column.
    name: unit
    type: string
  - description: Values recorded in the source column.
    name: source
    type: string
  - description: Values recorded in the further description column.
    name: further description
    type: string
  - description: Values recorded in the currency_year column.
    name: currency_year
    type: decimal
  grain: One row from the source table.
  row_count: 1091
---
## Overview

独立于 PDF 的技术成本数据，作为 Collection 根级 table Node。

## Data profile

| Field | Type | Non-empty | Missing | Missing rate | Unique | Min | Max |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| technology | string | 1091 | 0 | 0.0% | 271 |  |  |
| parameter | string | 1091 | 0 | 0.0% | 47 |  |  |
| value | decimal | 1091 | 0 | 0.0% | 594 | 0 | 393737000 |
| unit | string | 1091 | 0 | 0.0% | 130 |  |  |
| source | string | 1083 | 8 | 0.7% | 207 |  |  |
| further description | string | 933 | 158 | 14.5% | 586 |  |  |
| currency_year | decimal | 1010 | 81 | 7.4% | 14 | 2004 | 2023 |

## Preview

| technology | parameter | value | unit | source | further description | currency_year |
| --- | --- | --- | --- | --- | --- | --- |
| Ammonia cracker | FOM | 4.3 | %/year | Ishimoto et al. (2020): 10.1016/j.ijhydene.2020.09.017 , table 7. | Estimated based on Labour cost rate, Maintenance cost rate, Insurance rate, Admin. cost rate and Chemical & other consumables cost rate. | 2015.0 |
| Ammonia cracker | ammonia-input | 1.46 | MWh_NH3/MWh_H2 | ENGIE et al (2020): Ammonia to Green Hydrogen Feasibility Study (https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/880826/HS420_-_Ecuity_-_Ammonia_to_Green_Hydrogen.pdf), Fig. 10. | Assuming a integrated 200t/d cracking and purification facility. Electricity demand (316 MWh per 2186 MWh_LHV H2 output) is assumed to also be ammonia LHV input which seems a fair assumption as the facility has options for a higher degree of integration according to the report). |  |
| Ammonia cracker | investment | 1123945.3807 | EUR/MW_H2 | Ishimoto et al. (2020): 10.1016/j.ijhydene.2020.09.017 , table 6. | Calculated. For a small (200 t_NH3/d input) facility. Base cost for facility: 51 MEUR at capacity 20 000m^3_NH3/h = 339 t_NH3/d input. Cost scaling exponent 0.67. Ammonia density 0.7069 kg/m^3. Conversion efficiency of cracker: 0.685. Ammonia LHV: 5.167 MWh/t_NH3.; and
Calculated. For a large (2500 t_NH3/d input) facility. Base cost for facility: 51 MEUR at capacity 20 000m^3_NH3/h = 339 t_NH3/d input. Cost scaling exponent 0.67. Ammonia density 0.7069 kg/m^3. Conversion efficiency of cracker: 0.685. Ammonia LHV: 5.167 MWh/t_NH3. | 2015.0 |
| Ammonia cracker | lifetime | 25.0 | years | Ishimoto et al. (2020): 10.1016/j.ijhydene.2020.09.017 , table 7. |  | 2015.0 |
| BEV Bus city | FOM | 0.0001 | %/year | Danish Energy Agency, inputs/data_sheets_for_commercial_freight_and_passenger_transport_0.xlsx | BEV B1 | 2022.0 |
