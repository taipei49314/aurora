# sodium-ion-us-2025 — real offline replay package

A small **real-world** package for `python -m aurora.cli --package`. Unlike the
Northstar demo (`datasets/northstar`, synthetic), every row here is a real,
dated fact taken from a public-domain U.S. Government record or a USPTO
publication. No synthetic content is mixed in.

## What's inside

| Ref | What it records | Date |
|---|---|---|
| `arpa-e-natron-scaleup` | ARPA-E SCALEUP award, Natron Energy, $19,883,951 | 2021-02-22 |
| `sbir-mana-nsf-2423370` | NSF SBIR Phase I, Mana Battery, $275,000 | 2025-05-22 |
| `sbir-mana-army-w51701` | Army SBIR Phase I, Mana Battery, $249,998 | 2025-02-25 |
| `sbir-airtronics-nasa-80nssc25c0127` | NASA SBIR Phase I, Airtronics, $147,205 | 2025-09-09 |
| `uspto-us20140220392a1` | USPTO published application US20140220392A1 (Natron/Alveo) | 2014-08-07 |

## Sources and license

- ARPA-E project page: <https://arpa-e.energy.gov/programs-and-initiatives/search-all-projects/domestic-manufacturing-sodium-ion-batteries>
- SBIR award records: <https://www.sbir.gov/awards/215029>, <https://www.sbir.gov/awards/215637>, <https://www.sbir.gov/awards/220508>
- USPTO publication: <https://patents.google.com/patent/US20140220392A1/en>

All retrieved on **2026-09-08**. U.S. Government works (award records, patent
publications) are public domain; each source row carries its own `license`
field. Excerpts are short verbatim or near-verbatim quotes from those records.

## Honest scope

This package exists to exercise the real-data replay path, not to claim any
discovery. Three companies, five public records, and nine observations cannot
and do not establish an "industry candidate", and no run output from this
package may be presented as a real-world early-detection result. A run on this
package is findings-only; no prediction is registered because there is no
measured retention baseline for real data.

## Replay

```bash
python -m aurora.cli --package datasets/sodium-ion-us-2025/package.json \
  --out-dir runs/sodium-ion-2025
# historical replay (the 2025 awards drop out of the window):
python -m aurora.cli --package datasets/sodium-ion-us-2025/package.json \
  --cutoff 2025-01-01 --out-dir runs/sodium-ion-cutoff-2025
```
