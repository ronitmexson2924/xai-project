# research/ (owner: Ronit)

Offline work. Nothing here runs in the live app.

| Path | Task | Purpose |
|---|---|---|
| `simulator/`, `simulate.py` | R6 | Synthetic learners with known traits; runs the real services in-process (hypothesis H3) |
| `reliability.py` | R3 | Cronbach's alpha per trait |
| `analysis/` | R8 | Pilot analysis: H1, H2, H4 |
| `backtest/` | R8 | Resonance and drift lead-time backtest (H5) |
| `reports/` | R6, R8, M7 | Generated reports: `simulation.md`, `results.md`, `llm_audit.md` |
| `preregistration.md` | S2 | Hypotheses and analysis plan, committed **before** pilot data exists |

Rules: everything is seeded and reproducible with one command; raw pilot data never goes into git
(`research/data/raw/` is ignored); exports use pseudonymous IDs.

## Running the simulation study (R6)

```bash
cd backend
pip install -e ".[dev,research]"
PYTHONPATH=../research python ../research/simulate.py          # full study, ~15-20 min
PYTHONPATH=../research python ../research/simulate.py --quick  # ~1 min smoke run
```

It writes `research/reports/simulation.md` and `research/reports/figures/*.png`. Each study runs in
a rolled-back transaction against `DATABASE_URL`, so the database is left untouched.
`backend/tests/test_simulator.py` smoke-tests the simulator in CI.
