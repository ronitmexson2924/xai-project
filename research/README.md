# research/ (owner: Ronit)

Offline work. Nothing here runs in the live app.

| Path | Task | Purpose |
|---|---|---|
| `simulator/`, `simulate.py` | R6 | Synthetic learners with known traits; runs the real services in-process (hypothesis H3) |
| `reliability.py` | R3 | Cronbach's alpha per trait |
| `analysis/`, `analyze.py` | R8 | Export (pseudonymised) + H1, H2, H4, reliability; one command writes the results report |
| `backtest/` | R8 | Early-warning backtest of drift and resonance vs. a naive baseline (H5) |
| `reports/` | R6, R7, R8, M7 | Generated: `simulation.md`, `load_test.md`, `results_simulated.md` (pipeline validation), `results.md` (pilot), `llm_audit.md` |
| `preregistration.md` | S2 | Hypotheses and analysis plan. **Draft**: sign off **before** pilot data exists |

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

## Running the analysis (R8)

```bash
cd backend
PYTHONPATH=../research python ../research/analyze.py --simulated            # validation, ~2 min
ANALYSIS_SALT=<fixed secret> PYTHONPATH=../research \
    python ../research/analyze.py --from-db [--save-export ../research/data/raw/export]
```

`--simulated` writes `reports/results_simulated.md`; `--from-db` (pilot) writes `reports/results.md`.
They are never mixed. Keep `ANALYSIS_SALT` secret and the same for the whole study, so pseudonyms
stay stable. `research/data/raw/` is git-ignored: never commit exports.
