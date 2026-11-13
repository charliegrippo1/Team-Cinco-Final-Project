# Blind hand-check of the v0 exposure scores (Carter)

**Why:** checklist item 8 says at least one number in each pipeline step must be checked
by hand. For the scoring step, that means a person scores the same firms without seeing
the AI's answer, and then we compare. Disagreements are useful findings for the audit,
not mistakes.

**The sheet:** `audits/hand_check_v0.csv` (opens in Excel or Google Sheets). It has 10
firms, a link to each firm's 10-K on the SEC website, and blank columns for you.
It does **not** show the AI's scores, on purpose.

## Steps (about 10 minutes per firm)

1. Open a firm's 10-K link. Only use what the filing says, not what you know about the
   company or what happened in April 2025.
2. Look at Item 1 (Business), Item 1A (Risk Factors) and Item 7 (MD&A). To save time,
   search the page (Cmd+F) for: `China`, `import`, `tariff`, `supplier`,
   `manufactur`, `outsourc`, `foreign`.
3. Give a score using the same scale the AI got:

   | Score | Meaning |
   |---|---|
   | 0 | Domestic services, no meaningful imports or foreign supply chain |
   | 1 | Generic trade-policy boilerplate only |
   | 2 | Real but limited imported inputs or foreign sales |
   | 3 | Material dependence on imports or foreign manufacturing |
   | 4 | Core business built on imports, or explicit large China exposure |

   If the filing doesn't let you decide, leave the score blank and say why.
4. Write one line of reasoning. Optionally, paste the sentence that convinced you.
5. Do all 10 before looking at any AI score.
6. Save the file and send it to Charlie, or upload it to the PR. Charlie will put the AI
   scores next to yours and count how many match exactly and how many are within one point.

## Rules that keep the check honest

- Don't open `outputs/`, `data/processed/tariff_firms.csv` or the dashboard until you're done.
  They show the AI scores.
- Don't look up stock prices or news.
- Score every firm, including Nike and Hess (the AI did, even though they dropped out later).
