# CalamityOS

A relief-operations workspace for a bank that has to restructure farm loans after a declared calamity, and has to be able to defend every decision afterwards.

When a state declares a drought, a bank does not get a list of borrowers. It gets a committee decision, a gazette date, a 135-day implementation window, and a loan book where eligibility turns on details like whether a second facility was 30 or 31 days overdue on a particular date. Branch staff then work through it in spreadsheets. The parts that go wrong later are rarely the arithmetic — they are the unexamined choice of date, the schedule the core system actually booked not matching the one an officer approved, and no trail back from a booked loan to the sentence in a circular that justified it.

CalamityOS runs that workflow as deterministic code, on a synthetic 300-borrower Andhra Pradesh drought scenario, offline.

## What it actually does

**Makes the date choice visible.** The scenario keeps the occurrence date, the gazette declaration date and the committee reference date in separate fields, because in a real event they disagree. Switch between them and the portfolio moves from 150 eligible borrowers to 149 to 165. The 149 is the interesting one: 30 borrowers become eligible and 31 lose eligibility at the same time, and the simulated additional provision moves by about ₹3.9 lakh. You can open any borrower whose outcome changed and see which facility caused it.

**Checks what the core system booked.** Approving a restructure freezes the simulated repayment schedule. After the booking goes to the lending core, the booked schedule is read back and compared field by field against that frozen approval, plus the policy limits — tenor cap, moratorium length, extra interest, the implementation deadline, and whether any instalment falls inside the payment holiday. A shifted repayment date produces a visible difference, pauses the remaining batch, and lands in the audit trail. A missing core event leaves the plan pending rather than quietly succeeding; re-sending a confirmation does not create a second booking.

**Keeps the borrower in the loop.** Each plan carries a simulated notice with both repayment options priced from the core simulation, an objection window, and a post-booking opt-out. An opt-out previews the catch-up amount, writes a compensating cancellation, restores the original schedule in the mock core and reverses the extra provision.

**Ties terms back to a source.** The evidence desk takes a typed committee brief and extracts the four terms the rule pack needs — reference date, moratorium, and the two tier caps — with the exact character span each value came from. Click a term to highlight its sentence. A brief with a conflicting or missing term cannot be attached to the rule pack. Attaching requires two different officer names.

**Shows whether the deadline is reachable.** The capacity clock compares approvals needed per day against approvals actually achieved over the last week, and projects a finish date from that rate.

Every action appends to a hash-chained ledger, and the chain is validated on every read, so tampering with past entries is detectable.

## Running it

From a source checkout, with Python 3.10 or newer and no dependencies to install:

```
python tasks.py ui --open      # the workspace, on 127.0.0.1 only
python tasks.py test           # 22 tests
python tasks.py demo           # three clean runs from fresh databases
```

On Windows, `Start CalamityOS.cmd` does the same thing with a double-click, and will use a bundled `runtime\python.exe` if one is present next to it.

`demo` is the one worth running first. It walks the whole path — reading comparison, booking with an injected missing event, recovery, opt-out, booking with an injected date shift — three times from three fresh temporary databases, and asserts that all three end at the same audit hash. Local state lives in `local-state/` and is reset from the UI's demo controls.

## How it is put together

Standard library only, four moving parts:

| | |
|---|---|
| `calamityos/domain.py` | The rule pack and scenario: dated eligibility across every facility, area severity tiers, repayment sizing, provisioning, write-back tracking. Pure functions, no I/O. |
| `calamityos/booking.py` | The workflow: draft, two-person approval, notice, objection, booking, read-back reconciliation, opt-out, and the hash-chained ledger. SQLite. |
| `calamityos/mock_core.py` | The lending core, as a separate process spoken to one JSON request at a time. Written independently of the checker that grades it, so the reconciliation tests mean something. |
| `calamityos/app.py` | A loopback-only HTTP server and the single application boundary that both the browser UI and the headless demo go through. |

The browser UI in `calamityos/static` is plain JavaScript against that one JSON API. Status is carried by text and label as well as colour, and chart comparisons are labelled with their values rather than relying on a legend.

Anything that decides an outcome — dates, eligibility, money, schedule comparison — is deterministic code. Nothing in the decision path is probabilistic.

## What this is not

The loan book, the borrowers, the loss list and the approval history are invented. The occurrence date and the replay declaration date are illustrative, chosen so the three-date comparison has something to show; the app labels them as such rather than hiding it.

The lending core is a simulator, the notices are not sent anywhere, and the two officer names simulate a maker-checker control rather than enforcing one. Term extraction is deterministic pattern matching tuned to this scenario's brief, not document AI — it proposes values with spans for a human to accept, and that is the limit of the claim.

Live core integration, real banking identities, and general document extraction would each need separate validation. Accuracy figures against human annotators and model baselines need the independent runs described in [the study protocol](calamityos/STUDY.md), and the tooling for those runs (`python -m calamityos.study`) deliberately prepares blank sheets rather than generating answers. No such results are claimed here.

## Scenario sources

Rule references are to the RBI directions on resolution of stressed assets and on income recognition and provisioning. The Andhra Pradesh terms come from a secondary report of the 6 October special SLBC meeting and the gazette declaration; primary minutes were not available, and the app marks that distinction on each source it shows. The lending event names and the amended-schedule review step follow the Temenos lending lifecycle documentation.
