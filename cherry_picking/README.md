# Cherry-Pick Detector

Detects cherry-picked or misleading graphs by comparing them against the full dataset.
Fully local — no API key required.

## How it works

```
Graph image (PNG/JPG)  ──┐
                         ├──► EasyOCR extracts axis labels & data point labels
Dataset (CSV/Excel)    ──┘
                              │
                              ▼
                    Context-aware analysis checks:
                      1. Does hidden data CONTRADICT the shown trend?
                      2. Were data points selectively included to inflate correlation?
                      3. Is the y-axis scaled to distort perception?
                      4. Are statistical results selectively reported?
                              │
                              ▼
                    Score 0-100 with severity rating + explanation
                              │
                              ▼
                    Outputs: report.md, analysis.png, stats.json
```

## Key principle

**A focused graph is NOT cherry-picking.**
Cherry-picking requires that hidden data **contradicts** the shown conclusion.

## Install

```bash
pip install numpy pandas matplotlib Pillow opencv-python easyocr scipy scikit-learn openpyxl
```

## Usage

```bash
python cherry_pick_detector.py <graph_image> <dataset> [--output <folder>]
```

### Examples

```bash
# Ancel Keys dataset (cherry-picked)
python cherry_pick_detector.py countries/countries.png countries/ancel_keys_dataset.xlsx --output countries/output

# Gyroscope data (cherry-picked time window)
python cherry_pick_detector.py gyro_data/Code_Generated_Image.png gyro_data/10min_gyro_data.csv --output gyro_data/output

# Nature paper figure (legitimate — not cherry-picked)
python cherry_pick_detector.py nature_data/image.png nature_data/nature_data.xlsx --output nature_data/output
```

## Scoring

| Score | Severity | Meaning |
|-------|----------|---------|
| 0-20 | None/Minimal | Legitimate focused presentation |
| 21-40 | Low | Minor concerns, not misleading |
| 41-60 | Medium | Some misleading framing |
| 61-80 | High | Hidden data contradicts shown narrative |
| 81-100 | Extreme | Actively deceptive |

## What it detects

- **Selective data point inclusion** — plotting only points that support a hypothesis (Ancel Keys style)
- **Contradicting hidden data** — showing a time window where the trend is opposite to the full data
- **Correlation inflation** — selecting a subset that makes a weak correlation look strong
- **Y-axis manipulation** — zooming to exaggerate trivial variation

## What it does NOT flag (correctly)

- Focused scientific figures showing one condition
- Appropriate y-axis scaling for the data being shown
- Showing a subset when hidden data is consistent with shown pattern
- Standard multi-panel figures in journal papers

## Outputs

| File | Description |
|------|-------------|
| `analysis.png` | Side-by-side: original graph vs full dataset |
| `cherry_pick_report.md` | Full report with findings and justifications |
| `stats.json` | Machine-readable score and metadata |

## Supported formats

- **Images:** PNG, JPG
- **Datasets:** CSV, Excel (.xlsx/.xls), JSON
