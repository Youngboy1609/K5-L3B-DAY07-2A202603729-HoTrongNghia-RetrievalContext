# Bonus benchmark v4 source and overlap review

Dataset: World Bank, *World Development Report 2024*; source PDF is the full 276-page indexed copy in the local research cache. The answerable labels below cite source chunks and physical PDF pages. Every visual page was rendered from the original PDF and inspected.

## Split and overlap policy

- Dev remains the same 24-question set; only its existing labels were retained.
- Test is a newly authored 30-question set with groups: table 6, image/diagram 5, chart 5, multi-hop 4, text 4, absent 6.
- The new items intentionally avoid the exposed answer targets. Table S.1 reuses physical pages 81–82 because they contain multiple previously unused cells; the exact country/column targets are new and are documented per question. Other page overlaps with v1 maps 6.1–6.3 are also deliberate, with new map targets: teal legend class, inset count, and a named map callout. No old map answer is reused.
- No answers or gold fields are passed to the agent. Run once after freeze; do not revise the test in response to outputs.

## Source review: answerable test cases

### bonus-v4-table-01
- Group: table
- Question: In Table S.1, what 2023 GNI per capita (Atlas method) is listed for Pakistan?
- Expected: US$1,500.
- Evidence: wdr-p081-table-01 (physical p.81)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-table-02
- Group: table
- Question: What Economic Complexity Index value does Table S.1 report for India?
- Expected: 0.5.
- Evidence: wdr-p081-table-01 (physical p.81)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-table-03
- Group: table
- Question: In Table S.1, what technology-index value is listed for China?
- Expected: 13.1.
- Evidence: wdr-p081-table-01 (physical p.81)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-table-04
- Group: table
- Question: What upper-secondary completion rate does Table S.1 list for Brazil, including the relevant-age-group basis?
- Expected: 69.00% of the relevant age group.
- Evidence: wdr-p081-table-01 (physical p.81)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-table-05
- Group: table
- Question: How many researchers per million inhabitants are listed for Türkiye in Table S.1?
- Expected: 1,736.7 researchers per million inhabitants.
- Evidence: wdr-p081-table-01 (physical p.81)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-table-06
- Group: table
- Question: What is Mexico’s energy intensity in Table S.1, including the unit from the column heading?
- Expected: 6.17 exajoules per trillion US dollars of GDP.
- Evidence: wdr-p081-table-01 (physical p.81)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-image-01
- Group: image_diagram
- Question: In Figure O.6’s scanned technical collaboration agreement, which two companies are named as the parties?
- Expected: Nippon Electric Co., Ltd. and Samsung Electron Devices Co., Ltd.
- Evidence: wdr-p041-caption-01 (physical p.41), wdr-p041-image-01 (physical p.41)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-image-02
- Group: image_diagram
- Question: In Figure P2.1, which labeled force remains at the top of both the initial and rebalanced circles?
- Expected: Creation.
- Evidence: wdr-p115-caption-01 (physical p.115), wdr-p115-image-01 (physical p.115)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-image-03
- Group: image_diagram
- Question: On Map 6.1, which income group is represented by the blue-green/teal legend swatch?
- Expected: Lower-middle-income.
- Evidence: wdr-p173-caption-01 (physical p.173), wdr-p173-image-01 (physical p.173)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-image-04
- Group: image_diagram
- Question: How many inset maps are shown on Map 6.2?
- Expected: Two inset maps.
- Evidence: wdr-p182-caption-01 (physical p.182), wdr-p182-image-01 (physical p.182)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-image-05
- Group: image_diagram
- Question: In panel b of Map 6.3, which province is named by the red callout in northern China?
- Expected: Shanxi province.
- Evidence: wdr-p186-caption-01 (physical p.186), wdr-p186-image-01 (physical p.186)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-chart-01
- Group: chart
- Question: In Figure O.9 panel b, which income group has the highest estimated coefficient of skilled workers’ intergenerational mobility?
- Expected: High-income countries (HICs).
- Evidence: wdr-p047-caption-01 (physical p.47)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-chart-02
- Group: chart
- Question: In Figure 1.6 panel b, at roughly 50% proximity to the frontier, which group has the higher cumulative probability of slowdown: less-free or more-free economies?
- Expected: Less-free economies.
- Evidence: wdr-p076-caption-02 (physical p.76), wdr-p076-text-00 (physical p.76)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-chart-03
- Group: chart
- Question: In Figure 2.7, how many researchers per million inhabitants are shown for the low-income group?
- Expected: 48 researchers per million inhabitants.
- Evidence: wdr-p096-caption-02 (physical p.96), wdr-p096-text-00 (physical p.96)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-chart-04
- Group: chart
- Question: In Figure 3.6, which income-group average has the highest weighted average cost of capital (WACC)?
- Expected: The low-income group average.
- Evidence: wdr-p109-caption-01 (physical p.109), wdr-p109-text-00 (physical p.109)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-chart-05
- Group: chart
- Question: In Figure 6.6, which country has the tallest bar for the share of online job postings related to low-carbon technologies?
- Expected: Costa Rica.
- Evidence: wdr-p180-caption-01 (physical p.180), wdr-p180-text-00 (physical p.180)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-multi-01
- Group: multihop
- Question: What 2023 GNI per capita does Table S.1 report for Colombia, and which central-bank-related action was part of its 2001 reform package in Box 2.3?
- Expected: Colombia: US$6,870; the reform increased central bank independence.
- Evidence: wdr-p081-table-01 (physical p.81), wdr-p097-text-00 (physical p.97), wdr-p097-text-00 (physical p.97)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-multi-02
- Group: multihop
- Question: How many researchers per million inhabitants does Table S.1 list for Korea, Rep., and does its sustained-growth line in Figure 1.3 extend longer than India’s?
- Expected: Korea, Rep.: 8,483.2 researchers per million; yes, its line extends longer than India’s.
- Evidence: wdr-p082-table-01 (physical p.82), wdr-p072-caption-01 (physical p.72), wdr-p072-text-00 (physical p.72)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-multi-03
- Group: multihop
- Question: What 2023 GNI per capita is listed for Türkiye in Table S.1, and what fiscal target did Box 2.3 say Türkiye implemented in the early 2000s?
- Expected: Türkiye: US$11,650; it implemented a primary-surplus target.
- Evidence: wdr-p081-table-01 (physical p.81), wdr-p097-text-00 (physical p.97)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-multi-04
- Group: multihop
- Question: What 2023 GNI per capita does Table S.1 report for Portugal, and approximately what 2022 GDP per capita does Figure 8.2 panel a plot for Portugal?
- Expected: Portugal: US$26,270 GNI per capita (2023); approximately US$22,000 GDP per capita (2022).
- Evidence: wdr-p081-table-01 (physical p.81), wdr-p232-caption-01 (physical p.232), wdr-p232-text-00 (physical p.232)
- Visual source review: rendered original PDF; answer region/legend/axis checked

### bonus-v4-text-01
- Group: text
- Question: How does Box 1.3 define the minimum growth-rate decline for an episode to count as a slowdown?
- Expected: A decline of at least 2 percentage points in the seven-year average GDP-per-capita growth rate.
- Evidence: wdr-p074-text-00 (physical p.74)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-text-02
- Group: text
- Question: According to Policy insight 3 in Box 2.2, what is essential for moving from infusion to innovation?
- Expected: Skilled labor.
- Evidence: wdr-p095-text-00 (physical p.95)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-text-03
- Group: text
- Question: Why does Box 2.3 say countries need to scale up investment to advance technologically?
- Expected: Because technology is embodied in capital, and advancing technologically is challenging without scaling up investment.
- Evidence: wdr-p097-text-00 (physical p.97)
- Visual source review: text/table row and column headings checked against the indexed original text

### bonus-v4-text-04
- Group: text
- Question: What benefit do well-structured power-purchase agreements provide to buyers and sellers, according to the report?
- Expected: They provide certainty by locking in electricity prices for decades; sellers gain a steady revenue source and better access to low-cost financing.
- Evidence: wdr-p181-text-01 (physical p.181), wdr-p181-text-01 (physical p.181)
- Visual source review: text/table row and column headings checked against the indexed original text

## Source review: absent cases

- bonus-v4-absent-01: What was Hanoi’s hotel occupancy rate during calendar year 2025? Reason: The WDR 2024 has no Hanoi hotel-occupancy dataset or 2025 observation.
- bonus-v4-absent-02: How many passenger electric vehicles were registered in Viet Nam during 2025? Reason: The report does not provide Viet Nam’s 2025 passenger-EV registrations.
- bonus-v4-absent-03: What was the average monthly rent for a one-bedroom apartment in Jakarta during 2024? Reason: The report does not provide Jakarta residential rental-price statistics.
- bonus-v4-absent-04: How many semiconductor wafers did Malaysia export in 2025? Reason: The report contains no 2025 wafer-export count for Malaysia.
- bonus-v4-absent-05: What was the Brent crude-oil closing price on 16 November 2026? Reason: The report is a static 2024 publication and contains no daily Brent price for this date.
- bonus-v4-absent-06: What was the average weekly working time of Brazilian employees in 2024? Reason: The report does not contain this Brazil-specific 2024 labor-hours statistic.

## Limitations

- AI-assisted source review of labels is not student personal signoff. Similar page use is documented above. A single test result is not a guarantee of general retrieval performance.

## Exposed benchmark overlap audit

The v4 prompts and answer strings were compared with the current benchmark, `questions-v2-historical.jsonl`, the preserved v1 test backup, and the v2 candidate. The mechanical comparison found 0 duplicate IDs, 0 normalized prompt matches, and 0 exact normalized answer-string matches. Manual review found no repeated fact target.

| Source overlap | Earlier target | v4 target | Assessment |
|---|---|---|---|
| Table S.1 physical pages 81–82 | Prior tests queried other cells (for example India researchers, Malaysia energy intensity, France ECI, Japan social mobility, and several UK/France/Japan fields). | New country/field cells include Pakistan GNI, India ECI, China technology, Brazil completion, Türkiye researchers, Mexico energy intensity, plus distinct Portugal/Colombia/Korea/Türkiye/Belgium/France cells in multi-hop questions. | Page overlap is deliberate; each queried cell is new. |
| Map 6.1 physical page 173 | Orange legend swatch = upper-middle-income. | Blue-green/teal swatch = lower-middle-income. | New legend item and answer. |
| Map 6.2 physical page 182 | Red lines = power-transmission lines. | Count of two inset maps. | New diagram attribute and answer. |
| Map 6.3 physical page 186 | Broad concentration of low-carbon jobs on China's southeast coast. | Panel b red callout names Shanxi province. | New callout target; no broad-region answer repeated. |

## Corpus-wide absence keyword check

All pages of the local full PDF were searched as extracted text; counts below are exact case-insensitive substring counts. These searches support that the named data series are absent, while source limitations are also checked against the report's scope and year.

| ID | Search terms and occurrences | Label rationale |
|---|---|---|
| absent-01 | `Hanoi` 0; `hotel occupancy` 0 | No city hotel-occupancy series or 2025 observation. |
| absent-02 | `Viet Nam` 2; `registered` 2; `passenger electric vehicles` 0; `2025` 2 | Mentions of the country/registration do not provide 2025 passenger-EV registrations. |
| absent-03 | `Jakarta` 2; `one-bedroom` 0; `monthly rent` 0 | City mentions do not provide residential rental prices. |
| absent-04 | `Malaysia` 28; `wafer exports` 0; `2025` 2 | No Malaysian semiconductor-wafer export count or 2025 trade observation. |
| absent-05 | `Brent` 0; `16 November 2026` 0 | Static 2024 report cannot support a daily closing price for this date. |
| absent-06 | `Brazil` 78; `weekly working time` 0; `2024` 344 | Country/year mentions do not provide average weekly employee hours. |

The extracted-text keyword check is not a substitute for a claim that a topic is absent from every possible third-party source; it supports only absence from this corpus. The benchmark requires the agent to abstain from the supplied corpus.
