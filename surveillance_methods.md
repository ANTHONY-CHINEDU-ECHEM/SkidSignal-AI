# Statistical methods used for signal detection

Original notes that define each statistic reported in a SkidSignal brief, so that a
generated explanation can cite a definition instead of improvising one.

## Disproportionality analysis
Disproportionality analysis comes from drug safety surveillance. It asks whether a specific event makes up a larger share of the reports for one product than it does for all other products in the same database. It needs no exposure data such as vehicles in service, which public complaint files do not provide. Here the product is a vehicle family and the event is an ABS related complaint.

## Proportional reporting ratio
The proportional reporting ratio (PRR) divides the share of a vehicle's complaints that are ABS related by the same share for all other vehicles. A PRR of 3 means ABS issues are three times as prominent in that vehicle's complaints as elsewhere. A widely used screening rule flags a PRR of at least 2 with a chi square statistic of at least 4 and at least 3 cases.

## Information component and its lower bound
The information component (IC) is the base 2 logarithm of observed over expected counts with a shrinkage of one half added to both, which pulls estimates from small counts towards zero. IC025 is the lower limit of the 95 percent credibility interval. A positive IC025 means the excess is unlikely to be chance even after shrinkage, which makes it a conservative primary criterion for a signal.

## Surge test and false discovery control
To separate an emerging problem from a long standing one, the number of ABS complaints in the most recent months is compared with the count expected from the vehicle's own earlier rate using a Poisson tail probability. Thousands of vehicle families are tested each month, so the p values are adjusted with the Benjamini Hochberg procedure and a signal is called emerging only if its adjusted value stays below the configured false discovery rate.

## Cumulative sum monitoring
A cumulative sum (CUSUM) chart accumulates the amount by which each month's count exceeds its baseline mean plus an allowance. It resets at zero and raises an alarm when it crosses a decision limit. It is sensitive to small sustained shifts that a single month comparison would miss.

## Known limits of complaint based surveillance
Complaints are voluntary and unverified. Reporting rises after news coverage or a recall announcement, which is called stimulated reporting. Vehicles with large fleets generate more complaints of every kind, which disproportionality partly corrects for but volume thresholds do not. A statistical signal is a reason for an engineer to read the evidence. It is not a finding that a defect exists.
