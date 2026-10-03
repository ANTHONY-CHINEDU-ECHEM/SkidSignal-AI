# Evaluation notes

All numbers below come from files in `reports/` produced by `make all` on the snapshot described in the data card.

## 1. Signal backtest

**Protocol.** For each month from December 2020 to January 2026 the detector is run with only the complaints received up to the end of that month. A trailing window of up to 24 months is used (12 months at the first replayed month). An alert is the first month a vehicle family is on any tier. Ground truth is the set of ABS related vehicle recall campaigns in the 2020 to 2024 recall document file, linked to families by exact make and model.

**Population.** 38 ABS vehicle campaigns. 27 are dated January 2021 or later and affect at least one family present in the complaint panel. 11 of these had five or more ABS complaints for the affected families before the recall month ("detectable").

| Rule | Detectable alerted (of 11) | All alerted (of 27) | Median lead, months | Families ever alerted | Mean active alerts per month | Alerts with full horizon: recall followed / prior recall / none on file |
|---|---|---|---|---|---|---|
| SkidSignal, both channels | 8 | 8 | 12.5 | 100 | 29.7 | 11 / 2 / 46 |
| Surge channel | 7 | 7 | 7.0 | 63 | 5.8 | 8 / 0 / 18 |
| Disproportionality channel | 4 | 4 | 14.5 | 66 | 26.5 | 6 / 2 / 36 |
| Volume rule, 3 in six months | 10 | 11 | 12.5 | 184 | 61.6 | 14 / 3 / 101 |
| Volume rule, 5 | 8 | 8 | 10.5 | 103 | 35.0 | 11 / 3 / 56 |
| Volume rule, 8 | 8 | 8 | 9.5 | 59 | 21.1 | 9 / 1 / 29 |
| Volume rule, 10 | 8 | 8 | 9.0 | 45 | 15.8 | 7 / 0 / 25 |

Per recall results are in `reports/backtest_recalls.csv` and per alert outcomes in `reports/backtest_alerts.csv`.

**Design iteration log.** This matters for how much weight the table can bear.

1. *First design.* The emerging tier required disproportionality and a surge together, and an alert required disproportionality. Result: 4 of 11 detectable recalls, against 8 of 11 for a volume rule of five.
2. *Diagnosis.* The four extra recalls caught by the volume rule were for Kia and General Motors families. One month before each recall, those families had proportional reporting ratios below 2 (Kia Sorento 1.36 and later 0.56, Kia Optima 0.59 and 0.61, Kia Sportage 1.36 and 0.96, Kia Soul 0.34, Kia Forte 0.44, Chevrolet Tahoe 1.07, GMC Yukon 0.67) because ABS complaints were a small share of very large complaint volumes about other components. This is the masking effect known from drug safety surveillance.
3. *Second design (shipped).* The surge channel was made independent of disproportionality, with a minimum of five recent complaints. Result: 8 of 11.
4. *Rejected variant.* Signals at model year level instead of family level left only 4 recalls detectable, because counts became too sparse.

Because step 3 was chosen after seeing step 1, the shipped numbers are an in sample description, not an out of sample estimate. A clean test needs recalls that played no part in the design, for example the 2025 and 2026 recall files or the years before 2020.

**Other threats to validity.**

* Eleven detectable recalls is a very small sample, dominated by one series of Hyundai and Kia ABS module fire campaigns.
* Recall dates are estimates. An error of a few weeks can move a lead time by one month.
* A family level alert is not proof that the alert concerned the same defect as the later recall. The 33 month leads for campaigns 23V651 and 23V652 are alerts first raised in December 2020, around earlier campaigns in the same series.
* The complaint file starts in January 2020, so alerts cannot precede December 2020 and recalls in 2020 cannot be evaluated.
* "None on file" alerts are not false positives. They include families with documented problems and no recall (Ram 2500 is the clearest case), replacement part campaigns filed under an equipment brand, and recalls outside the 2020 to 2024 file.

## 2. Retrieval benchmark

**Task.** Owner narrative to cited recall campaign. Queries are braking domain complaints whose narrative cites exactly one campaign number that exists in the knowledge base and covers the complainant's make. The campaign number is masked in the query. The pool is all 3,574 campaigns. 233 queries over 65 campaigns, split by campaign hash into 87 development queries (35 campaigns) and 146 test queries (30 campaigns).

**Weight selection on the development split (MRR at 10).** BM25 only 0.355; BM25 to dense 10:1 0.337; 5:1 0.325; 3:1 0.316; 1:1 0.307; 1:3 0.285. Selected: BM25 weight 1, dense weight 0.

**Test split.**

| Method | Recall at 1 | Recall at 5 | Recall at 10 | MRR at 10 (95% bootstrap interval) |
|---|---|---|---|---|
| BM25 | 0.199 | 0.322 | 0.425 | 0.255 (0.195 to 0.316) |
| Dense, LSA 256 dimensions | 0.055 | 0.158 | 0.219 | 0.105 |
| Hybrid, equal weights | 0.130 | 0.226 | 0.329 | 0.173 |
| Selected, with make filter | 0.315 | 0.575 | 0.671 | 0.427 (0.358 to 0.494) |

Paired MRR differences on the test split: BM25 minus dense 0.150 (0.092 to 0.211); BM25 minus equal hybrid 0.082 (0.030 to 0.136); make filter minus no filter 0.172 (0.129 to 0.219).

**Reading.** The task is hard: many campaigns for one manufacturer describe near identical defects, and a citation is a noisy label. Long narrative queries with specific model names and part terms favour exact matching. LSA vectors capture topic, not the specific campaign. The result says nothing about a transformer encoder, which could not be downloaded in the build environment. The settings keep the fusion architecture so that a stronger encoder can be dropped in and its weight selected on the same development split.

**Limits.** Labels are incomplete (other complaints may relate to the same campaign without citing it, and are not used as queries or targets here). Queries come only from owners who knew their recall number, who may write differently from other owners. One benchmark of long queries does not characterise short conceptual questions.

## 3. Guardrail mutation tests

For each of the 27 flagged families a clean extractive brief was generated and four faults were injected separately into its narrative: a fabricated citation key, an altered count, an overstated sentence, and removal of all citations from two sections. Clean pass rate 27 of 27. Detection 27 of 27 for each fault, and each was caught by the intended check.

This verifies the checks. It does not measure a language model. The numeric check is strict by design: a model that writes "about 200" for 204 fails, and that is intended. Known gap: the checks do not test whether a cited record actually supports the sentence that cites it. That needs an entailment model or human review and is listed on the roadmap.

## 4. Narrative clustering

K means on LSA vectors of 12,274 ABS narratives, with k chosen by silhouette on a 4,000 narrative sample: 0.111 (k = 6), 0.079 (8), 0.070 (10), 0.064 (12), 0.069 (14). Structure is weak. Clusters and top terms are in `reports/failure_clusters.csv`. One cluster of 2,397 narratives is defined by hotline transcript phrasing, not by failure mode. The clustering is exploratory and is not used in signal detection or in briefs.

## 5. Software tests

29 tests in `tests/`: hand calculated statistics, taxonomy matches and near misses, complaint collapsing and duplicate removal, campaign date ordering, chunking, retrieval filters including the as of date filter, index persistence, an end to end pipeline run on the bundled sample, the draft, repair and fallback path with a stand in language model, and the API. Writing the tests exposed two real defects that were then fixed: the last campaign of a year was dated to the following January, and the lexicon missed "no part is available".
