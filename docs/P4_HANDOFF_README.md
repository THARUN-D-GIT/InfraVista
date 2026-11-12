# InfraVista Person 4 — Integration handoff (prototype)

## Purpose
The P4 consolidated handoff cross-checks five existing JSON reports against a shared P3 run ID and sector/area inventory. It bundles evidence readiness, demand input requirements, hypothetical scenario review status, assumptions, and outstanding approval/validation gates.

**Not** a validated urban-growth forecast, infrastructure need estimate, site feasibility assessment, investment ranking, or construction recommendation.

## Inputs
- `reports/p4_screening/multi_sector_screening.json`
- `reports/p4_screening/infrastructure_gap_analysis.json`
- `reports/p4_screening/option_evidence_readiness.json`
- `reports/p4_screening/scenario_comparison.json`
- `reports/p4_screening/demand_readiness.json`

## Run
```powershell
$env:PYTHONPATH = "$PWD\src"
python -m pytest tests/unit/test_p4_handoff.py -v
python -m infravista.screening.p4_handoff
python -m pytest tests/ -q
```

Generated output: `reports/p4_screening/p4_consolidated_handoff.json`.

## For downstream P5 / P6
- P5 may display readiness, missing inputs, assumptions, and validation gates. Do **not** render the hypothetical comparisons as site recommendations or predicted benefits.
- P6 should independently check indicator provenance, area/sector consistency, CRS/geometry, OSM completeness, and data-rights assumptions before any production use.
- P1 must approve a bounded planning use case before real-world candidate recommendation work is enabled.
- P2/P6 historical built-up change results are still exploratory until suitable dated source imagery and an independent change validation protocol are confirmed.

## Approval gates
All gate values are conservative **not_confirmed** defaults. These cannot be automatically promoted to approved by this generator. Record evidence and approvals through the project governance process before changing downstream policy.
