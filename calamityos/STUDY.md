# Evidence collection

The working demo supplies synthetic records. S1 and S2 require independent human annotations. The following preparation commands create blank recording sheets. Run from the repository root with ordinary Python.

## Held-out intake (S1)

Freeze the Andhra Pradesh version first. Give the second annotator the Telangana and Assam committee decisions after the freeze. Use public secondary reports with a source label when minutes are unavailable. For every criterion record the source passage, whether the existing AP schema can express it without editing code, field correctness (correct, flagged or silently wrong), elapsed minutes and the failure reason. Keep borrower records inside the bank boundary. Report counts alongside denominators separately for each case.

## Decision vignettes (S2)

1. Run `python -m calamityos.study prepare my-study` to create an unused directory with 80 synthetic questions (16 templates, five variations), two independent answer sheets, a reconciliation sheet and the S1 record sheet.
2. Both humans independently answer the vignettes using the same written rules, without access to system outputs. Each sheet requires an ISO date or one of Eligible, Ineligible and Review for each item. Review indicates insufficient evidence under a rule. Reconcile disagreements in a separate sheet, retaining the originals.
3. Run `python -m calamityos.study freeze my-study`. This requires complete sheets and hash-locks the questions and all three answer files.
4. Run `python -m calamityos.study pipeline my-study` to run the deterministic rules five times per item. The input is structured, so results measure the decision engine after intake. This protocol cannot establish extraction accuracy.
5. For B0 and B1 give the same model the same vignette, scenario rules and day-count setting in a fresh context five times. B1 gets a code tool. Keep prompts, model version, settings and raw responses. Supply `B0.csv` and `B1.csv` with columns `id,run,answer`; use run numbers 1–5 and ABSTAIN for explicit abstentions. Reserve the reconciled sheet for scoring.
6. Run `python -m calamityos.study score my-study`. It validates the original hashes, checks complete responses for every system supplied, and reports raw counts, repeated-run consistency and a template-clustered bootstrap interval. It reports both the full denominator and the denominator excluding abstentions. Classify missed examples by hand as arithmetic, wrong anchor, missed second loan, invented field or other. Report which comparators ran.

The schedule questions use the convention declared in each vignette. A paired alternative-convention analysis would require a second frozen sheet and independently labelled alternative answers. The checked-in tools make no claim about human agreement or model performance.

## Booking checks (S3)

An evaluator who has never seen the reconciliation implementation must author the blind fault catalogue. Record the frozen fault set and score before changing the detector. Label reproducible developer-injected faults in the UI as demonstrations. Reserve the independent S3 result for a completed blinded assessment.
