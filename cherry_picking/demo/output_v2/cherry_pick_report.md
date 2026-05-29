# Cherry-Pick Detection Report (v2 — Context-Aware)

**Graph:** `demo/cherry_picked_graph.png`
**Dataset:** `demo/full_dataset.csv`

---

## Verdict: High (Score: 70/100)

| Score Range | Meaning |
|-------------|---------|
| 0-20 | Legitimate focused presentation |
| 21-40 | Minor concerns, not misleading |
| 41-60 | Moderate — some misleading framing |
| 61-80 | High — hidden data contradicts shown narrative |
| 81-100 | Extreme — actively deceptive |

---

## Cherry-Pick Indicators

### ⚠ CONTRADICTING DATA HIDDEN (impact: 80/100)

Only 16% of x-range shown (2012.8–2015.2). Hidden data contradicts shown pattern in: expenses, profit.

*Why this matters:* Hidden data would change the viewer's conclusion.

## Legitimate Aspects

### ✓ MIXED STATISTICAL RESULTS

Dataset contains both significant (['profit_176']) and non-significant (['profit_142', 'profit_146']) results.

*Why this is fine:* Reporting both significant and non-significant results is transparent, not cherry-picking.

## Mitigating Factors

- Both significant and non-significant results are in the data
