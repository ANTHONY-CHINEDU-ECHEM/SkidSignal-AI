# Data card

## Sources

All records are published by the National Highway Traffic Safety Administration (NHTSA), Office of Defects Investigation, on the page "NHTSA Datasets and APIs": https://www.nhtsa.gov/nhtsa-datasets-and-apis

| Group | File pattern on static.nhtsa.gov/odi/ffdd | Layout document | Used in the reference run |
|---|---|---|---|
| Complaints | cmpl/COMPLAINTS_RECEIVED_YYYY-YYYY.zip (five year sets) or cmpl/FLAT_CMPL.zip | cmpl/CMPL.txt | Yes: 2020 to 2024 and 2025 to 2026 sets |
| Recall documents | rcl/RCL_FROM_YYYY_YYYY.zip | none published, header row in file | Yes: 2020 to 2024 |
| Recalls flat file | rcl/FLAT_RCL_POST_2010.zip | rcl/RCL.txt | No (parser included) |
| Investigations | inv/FLAT_INV.zip | inv/INV.txt | No (parser included) |
| Manufacturer communications | tsbs/TSBS_RECEIVED_YYYY-YYYY.zip | tsbs/TSBS.txt | No (parser included) |

The download step (`make download`) fetches every group from the official host and writes `data/raw/manifest.json` with the URL, byte size, SHA 256 and retrieval time of each archive.

## Snapshot used for the published results

The build environment could not reach nhtsa.gov, so the reference run used unmodified copies of three official archives mirrored in a public GitHub repository (DavisM1212/NHTSA-ODI-Complaint-Analytics, commit 8b0d8371, folder data/raw). The files inside carry NHTSA timestamps from February 2026.

| File | Rows | Notes |
|---|---|---|
| COMPLAINTS_RECEIVED_2020-2024.txt | 418,867 | 49 tab separated fields |
| COMPLAINTS_RECEIVED_2025-2026.txt | 126,478 | received up to 19 February 2026 |
| RCL_FROM_2020_2024.csv | 216,260 | recall document index: campaign, document name, make, model, model year, summary |

Anyone repeating the work should run `make download` to take a fresh official snapshot. Counts will then differ, because NHTSA updates the files daily and, in April 2026, added two fields to the complaint layout (state of incident and vehicle operator). The complaint parser assigns names by position and accepts 49, 50 or 51 fields.

## Processing

1. **Complaints.** Rows are one per complaint and component. They are collapsed to one record per ODI number and vehicle, with the component descriptions joined. Model year 9999 becomes missing. Exact duplicate narratives for the same vehicle are dropped (2,242 in the reference run). Only complaints with product type V (vehicle) enter the signal panel.
2. **ABS flag.** A complaint is ABS related if a component description contains ANTILOCK or the narrative matches the core patterns in `config/abs_taxonomy.yaml`. In the reference run 12,370 vehicle complaints were flagged, 127 of them by component code only.
3. **Braking domain.** ABS related complaints plus any complaint coded to service brakes, electronic stability control, parking brake or traction control (42,647). These narratives are indexed for retrieval.
4. **Recall documents.** Rows are one per campaign, document and vehicle. They are rolled up to one record per campaign with up to three of its longest distinct summaries, and a separate campaign to vehicle table. A campaign is ABS related when at least 25 percent of its distinct summaries match the ABS patterns.
5. **Recall dates.** The recall document file has no dates. The filing date is estimated from the campaign number, because NHTSA numbers campaigns sequentially within a year and type. Spot checks against well known campaigns put the error within a few weeks. When the recalls flat file is present its exact report received date replaces the estimate.

## Fields kept and fields dropped

Kept from complaints: ODI number, manufacturer, make, model, model year, crash and fire flags, injuries, deaths, component description, received date, incident date, mileage, narrative, complaint source code, speed, product type.

Never loaded: city, state, partial VIN, purchase date, dealer name, telephone, city, state and ZIP, vehicle operator name, and all tyre and child seat fields. The bundled sample in `data/sample` also has city, VIN stub and dealer fields blanked in the raw file.

Narratives are published by NHTSA after its own redaction. They can still contain personal details that a complainant chose to include. Briefs quote short excerpts for analysis. Do not use the corpus to identify or contact individuals.

## Known data limitations

* Complaints are voluntary, unverified and filed by a small, self selected share of owners.
* Component coding is inconsistent. Most ABS complaints are filed under generic codes.
* One complaint can describe several unrelated problems.
* There is no exposure data (vehicles in service or miles driven), so rates cannot be computed.
* The recall document file starts in 2020 and ends in 2024. Recalls before or after are not visible to the backtest.
* Make and model strings follow NHTSA usage. Replacement part campaigns are filed under equipment brands such as Mopar and are not linked to vehicle families.

## Reference notes

The four files in `knowledge/` were written for this project. They summarise ABS operation, failure modes, the United States regulatory framework and the statistics used. They are orientation material, not legal or engineering authority, and each regulatory note tells the reader to consult the current regulation.
