# SkidSignal brief: HYUNDAI PALISADE

| As of | Tier | Priority score | Rank among flagged families | Writer | Guardrails |
|---|---|---|---|---|---|
| 2026-01 | emerging | 59.3 | 1 of 27 | extractive | passed |

## 1. Signal summary

HYUNDAI PALISADE is on the emerging tier as of 2026-01 with a priority score of 59.3, rank 1 of 27 flagged families [S]. Between 2024-02 and 2026-01, 204 of its 1,122 complaints were ABS related, a share of 18.2 percent against 3.6 percent across all vehicles [S]. The proportional reporting ratio is 5.19 with a 95 percent interval of 4.57 to 5.90, and the lower credibility bound of the information component (IC025) is 2.11 [S]. The most recent 6 months brought 77 ABS complaints against 44.9 expected from the earlier rate, a rate ratio of 1.71 that stays significant after false discovery control (q 0.0003) [S].

## 2. Statistical evidence

Window: 2024-02 to 2026-01 (24 months). All figures are computed by the signal engine.

| Metric | Value | How to read it |
|---|---|---|
| ABS related complaints | 204 of 1,122 (18.2%) | Database wide share is 3.6% |
| Expected ABS complaints | 40.6 | If this family matched the database mix |
| Proportional reporting ratio | 5.19 (4.57 to 5.90) | Signal criterion: at least 2 |
| Reporting odds ratio | 6.12 (5.25 to 7.15) | Interval excluding 1 supports an excess |
| Chi square | 683.3 | Signal criterion: at least 4 |
| Information component | 2.31 (IC025 2.11) | Signal criterion: IC025 above 0 |
| Last 6 months | 77 observed, 44.9 expected | Rate ratio 1.71, adjusted q 0.0003 |
| CUSUM peak | 23.0 | In alarm |
| Severe outcomes | 10 (4.9%) | 9 crash, 0 fire, 1 injured, 0 deaths |

## 3. Failure mode profile

The most frequent failure mode tag is "ABS activation without demand or abnormal pedal pulsation" (126 narratives, 61.8 percent), followed by "Loss of braking or extended stopping distance" (34, 16.7 percent) [S]. Complaints concentrate in model years 2024 (109), 2025 (57), 2023 (35) [S]. An owner report for a 2024 HYUNDAI PALISADE states: "The Palisade has been intermittently acting up approaching a stop and the pedal pulsates and pedal travel is much longer, stopping distance is lengthened but when all of" [C:11674735]. An owner report for a 2024 HYUNDAI PALISADE states: "There is a known issue documented online regarding the 2024 Hyundai Palisade and the ABS system; On multiple occasions we have noticed that when driving at slow speeds" [C:11690674]. An owner report for a 2022 HYUNDAI PALISADE states: "To Whom It May Concern, I am writing to formally report a serious safety issue involving my Hyundai Palisade related to brake failure; While driving my Hyundai Palisade" [C:11706647]. Reference note "Unintended activation and pedal pulsation": ABS activation when no wheel is near lock lengthens low speed stopping distance because the controller releases pressure the driver needs [K:failure_modes.unintended_activation_and_pedal_pulsation].

| Failure mode | Narratives | Share |
|---|---|---|
| ABS activation without demand or abnormal pedal pulsation | 126 | 61.8% |
| Loss of braking or extended stopping distance | 34 | 16.7% |
| ABS or brake warning lamp illuminated | 18 | 8.8% |
| Stability or traction control affected together with ABS | 3 | 1.5% |
| Electrical short, wiring, fuse, corrosion or software | 2 | 1.0% |
| ABS module, pump or hydraulic control unit failure | 1 | 0.5% |
| Wheel speed sensor, tone ring or wiring fault | 1 | 0.5% |

## 4. Complaint evidence

- **[C:11674735]** 2024 HYUNDAI PALISADE | SERVICE BRAKES (received 2025-07-19, retrieved): "The Palisade has been intermittently acting up approaching a stop and the pedal pulsates and pedal travel is much longer, stopping distance is lengthened but when all of this is going on, not one light or warning is shown. No ABS light, TRAC light or Skid light is illuminated."
- **[C:11690674]** 2024 HYUNDAI PALISADE | SERVICE BRAKES | FORWARD COLLISION AVOIDANCE: AUTOMATIC EMERGENCY BRAKING | FORWARD COLLISION AVOIDANCE: WARNINGS (received 2025-09-30, retrieved): "There is a known issue documented online regarding the 2024 Hyundai Palisade and the ABS system. On multiple occasions we have noticed that when driving at slow speeds (less than 25 miles per hour) and if the road is slightly uneven, gravel, on an incline or decline, the brake pedal start to vibrate and there is loss of control and increased stopping distance. We reported this previously to Hyundai dealership and ..."
- **[C:11706647]** 2022 HYUNDAI PALISADE | SERVICE BRAKES (received 2025-12-22, retrieved): "To Whom It May Concern, I am writing to formally report a serious safety issue involving my Hyundai Palisade related to brake failure. While driving my Hyundai Palisade, I experienced a situation where pressing the brake pedal resulted in little to no braking response. The vehicle did not slow or stop as expected, creating an extremely dangerous situation and a significant risk of collision. This occurred without ..."
- **[C:11622393]** 2024 HYUNDAI PALISADE | SERVICE BRAKES (received 2024-10-29, retrieved): "stopping the vehicle. I have been driving for over 37 years and am very familiar with the sensation of ABS brakes activating in emergency situations. In this instance, the road was dry, and the braking was very gradual, so there was no apparent reason for the ABS to engage. This issue has only been observed on dry, rough, paved roads. Notably, the ABS pulsation continued even after transitioning from the rough ..."
- **[C:11703106]** 2025 HYUNDAI PALISADE | SERVICE BRAKES (received 2025-12-04, retrieved): "Antilock braking system is malfunctioning. Significant increase in stopping distance, and especially on uneven or wet surfaces. The car shutters and shakes while stopping. We have almost hit a deer, had trouble stopping at intersections, and did not stop in a timely manner while behind another vehicle. General fear knowing if brakes are firmly pressed that the car is unable to stop quickly (as expected with other ..."
- **[C:11675428]** 2024 HYUNDAI PALISADE | SERVICE BRAKES (received 2025-07-22, retrieved): "When braking over uneven surfaces or while the vehicle dynamics reduce the weight on the wheels, the ABS system activates and greatly increases the stopping distance."
- **[C:11695093]** 2025 HYUNDAI PALISADE | UNKNOWN OR OTHER (received 2025-10-22, severe outcome): "It happened on the way home from Manhattan [from Mount Sinai Hospital], near the ramp to 9W. The road was freshly milled (top layer removed before repaving), and I was going downhill. Traffic ahead was slowing, I had plenty of room, and it wasn’t even a sudden stop — I was just trying to gradually slow down when the car failed to respond properly. This isn’t some one-off. The behavior matches what I’ve seen others ..."

## 5. Recalls and context

No ABS related recall campaign for this family appears in the recall file before the as of date [S]. A brake related campaign for the same make, 23V415, states: "Certain 2023MY Hyundai Palisade vehicles produced for sale in the US and Canada are being recalled to address a condition involving the brake booster assembly; Subject vehicles are equipped with" [R:23V415]. A brake related campaign for the same make, 20V748, states: "This notice is sent to you in accordance with the National Traffic and Motor Vehicle Safety Act; Hyundai has decided that a defect which relates to motor vehicle safety exists in your vehicle, with" [R:20V748].

- **[R:23V415]** Recall 23V415 | HYUNDAI | model years 2023 to 2023 (related recall, same make, 2023-06-17): Certain 2023MY Hyundai Palisade vehicles produced for sale in the US and Canada are being recalled to address a condition involving the brake booster assembly. Subject vehicles are equipped with brake booster assemblies containing diaphragms that may become unseated due to improperly manufactured housings. An unseated booster diaphragm may result in a vacuum leak and subsequent loss of power brake assist. Loss of ...
- **[R:20V748]** Recall 20V748 | HYUNDAI | model years 2019 to 2021 (related recall, same make, 2020-12-01): This notice is sent to you in accordance with the National Traffic and Motor Vehicle Safety Act. Hyundai has decided that a defect which relates to motor vehicle safety exists in your vehicle, with the VIN shown above. Hyundai is conducting a safety recall in the United States to address a condition of reduced braking performance due to a fault in the Integrated Electronic Brake unit in certain model year 2019 2021 ...
- **[R:21V840]** Recall 21V840 | HYUNDAI | model years 2021 to 2021 (related recall, same make, 2021-11-03): The brake fluid in the subject vehicles may be contaminated with mineral oil causing the brake master cylinder inner cup seals to expand. Expanded brake master cylinder inner cup seals could reduce hydraulic pressure applied by the master cylinder resulting in reduced braking function at the wheels. The driver may experience longer brake pedal travel, change in pedal feel, and extended stopping distance, increasing ...
- **[K:failure_modes.unintended_activation_and_pedal_pulsation]** Unintended activation and pedal pulsation (reference note): ABS activation when no wheel is near lock lengthens low speed stopping distance because the controller releases pressure the driver needs. Narratives describe grinding, buzzing or pulsing in the pedal when stopping at an intersection or in a car park, sometimes with the vehicle rolling further than expected.
- **[K:failure_modes.loss_of_braking_or_extended_stopping_distance]** Loss of braking or extended stopping distance (reference note): Narratives that describe a pedal sinking to the floor, a hard pedal, or the vehicle failing to slow deserve priority review whatever the suspected cause. Possible ABS related mechanisms include a valve stuck open inside the hydraulic unit, air or fluid loss through the unit, and software that releases pressure incorrectly. These narratives also arise from causes unrelated to ABS, so they need careful reading.
- **[K:surveillance_methods.known_limits_of_complaint_based_surveillance]** Known limits of complaint based surveillance (reference note): Complaints are voluntary and unverified. Reporting rises after news coverage or a recall announcement, which is called stimulated reporting. Vehicles with large fleets generate more complaints of every kind, which disproportionality partly corrects for but volume thresholds do not. A statistical signal is a reason for an engineer to read the evidence. It is not a finding that a defect exists.

## 6. Assessment

The evidence is consistent with a growing ABS related problem that is also unusually prominent in this family's complaint mix [S]. 10 of the 204 ABS complaints involve a crash, fire, injury or death (9 crash, 0 fire, 1 injured, 0 deaths) [S]. The CUSUM chart is in alarm with a peak of 23.0, which points to a sustained shift and not a single unusual month [S]. This is a statistical signal built from unverified owner reports and it does not establish that a defect exists [K:surveillance_methods.known_limits_of_complaint_based_surveillance].

## 7. Recommended analyst actions

1. Read the cited narratives in full and confirm the failure mode coding.
2. Check manufacturer communications and open investigations for this family, since no ABS recall is on file.
3. Request a build date breakdown for model years 2024, 2025, 2023.
4. Review the signal again next month and note whether the tier or score has changed.

## 8. Limitations

Complaints are voluntary, unverified owner reports and reporting rises after publicity or a recall. Disproportionality compares complaint mixes and is not a failure rate, because the number of vehicles in service is not in the data. Signals are computed for a vehicle family across all model years, so a problem confined to one model year can be diluted. The brief only uses records received on or before the as of date.

Monthly ABS complaints in the window: 2024-02: 1, 2024-03: 0, 2024-04: 0, 2024-05: 2, 2024-06: 10, 2024-07: 10, 2024-08: 7, 2024-09: 24, 2024-10: 12, 2024-11: 5, 2024-12: 3, 2025-01: 2, 2025-02: 3, 2025-03: 1, 2025-04: 6, 2025-05: 5, 2025-06: 14, 2025-07: 22, 2025-08: 17, 2025-09: 33, 2025-10: 17, 2025-11: 6, 2025-12: 4, 2026-01: 0

Guardrail checks: citation validity 1.00, citation coverage 1.00, numeric fidelity 1.00. Citation keys: S is a computed statistic, C is an owner complaint (ODI number), R is a recall campaign, K is a project reference note.
