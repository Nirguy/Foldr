# Cherry-Pick Detection Report (v2 — Context-Aware)

**Graph:** `countries/countries.png`
**Dataset:** `countries/ancel_keys_dataset.xlsx`

---

## Verdict: High (Score: 74/100)

| Score Range | Meaning |
|-------------|---------|
| 0-20 | Legitimate focused presentation |
| 21-40 | Minor concerns, not misleading |
| 41-60 | Moderate — some misleading framing |
| 61-80 | High — hidden data contradicts shown narrative |
| 81-100 | Extreme — actively deceptive |

---

## Cherry-Pick Indicators

### ⚠ SELECTIVE DATA POINT INCLUSION (impact: 84/100)

Only 5 of 22 data points shown (23%). The shown subset has correlation r=0.964 vs full dataset r=0.716. The selection makes the relationship appear 1.3× stronger.

*Why this matters:* Data points were selectively chosen to create a stronger apparent correlation. Hidden points weaken or break the pattern.

## Legitimate Aspects

### ✓ FOCUSED COLUMN SELECTION

Graph shows ['Heart Disease Deaths (per 1,000)']. Other columns exist (['% Calories from Fat']) but don't contradict the shown pattern.

*Why this is fine:* Showing specific columns is standard scientific practice. Hidden columns are consistent.

## Mitigating Factors

- Hidden columns don't contradict shown data
