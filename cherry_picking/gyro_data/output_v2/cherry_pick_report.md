# Cherry-Pick Detection Report (v2 — Context-Aware)

**Graph:** `gyro_data/Code_Generated_Image.png`
**Dataset:** `gyro_data/10min_gyro_data.csv`

---

## Verdict: High (Score: 62/100)

| Score Range | Meaning |
|-------------|---------|
| 0-20 | Legitimate focused presentation |
| 21-40 | Minor concerns, not misleading |
| 41-60 | Moderate — some misleading framing |
| 61-80 | High — hidden data contradicts shown narrative |
| 81-100 | Extreme — actively deceptive |

---

## Cherry-Pick Indicators

### ⚠ CONTRADICTING DATA HIDDEN (impact: 70/100)

Only 42% of x-range shown (200.0–450.0). Hidden data contradicts shown pattern in: Gyro_Z.

*Why this matters:* Hidden data would change the viewer's conclusion.

### ⚠ FEW DATA POINTS SHOWN (impact: 55/100)

Only ~9 of 30000 data points appear in the graph (0%). Full dataset correlation: r=0.067. Selective point inclusion may create a misleading pattern.

*Why this matters:* Showing a small fraction of available data in a scatter plot suggests selective inclusion.
