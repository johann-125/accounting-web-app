---
name: generate-report
description: Generate an accounting report (invoices, expenses, profit/loss) for a given period
allowed-tools: Read, Grep, Bash
user-invocable: true
argument-hint: [report-type] [period]
---

Generate an accounting report based on the project data.

Report type: $ARGUMENTS[0] (e.g. invoice, expenses, profit-loss)
Period: $ARGUMENTS[1] (e.g. 2024-Q1, 2024-01, 2024)

Steps:
1. Locate relevant data files for the requested period
2. Aggregate and summarize the figures
3. Output a clean, readable report with totals
