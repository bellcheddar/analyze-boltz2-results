# analyze_boltz.py

A post-run analysis script for [Boltz-2](https://github.com/jwohlwend/boltz) co-folding predictions. Run it in any directory containing a `boltz_run_*.log` file and a `predictions/` subdirectory to automatically harvest confidence scores, affinity predictions, CIF models, and run metadata into a clean summary report and CSV.

---

## Overview

Boltz-2 produces a sprawling output tree: per-target prediction directories, confidence JSONs, affinity JSONs, and ModelCIF files, alongside a verbose run log. `analyze_boltz.py` walks that tree, extracts everything useful, and consolidates it into three outputs:

| Output | Description |
|---|---|
| `boltz_run_summary.log` | Human-readable summary: invocation, directory tree, runtime, per-prediction scores |
| `boltz_summary.csv` | Machine-readable table of all predictions with confidence, affinity, and pIC₅₀ |
| `boltz_cif/` | Flat directory of all `*_model_0.cif` files, ready for downstream structure analysis |

---

## Requirements

- Python 3.10+ (uses `Path | None` union syntax)
- Standard library only — no external dependencies

---

## Usage

Copy `analyze_boltz.py` into, or run it from, the top-level directory of your Boltz-2 run output:

```bash
cd /path/to/your/boltz_run_dir
python analyze_boltz.py
```

The script resolves everything relative to the current working directory. No arguments are required.

### Expected directory layout

```
boltz_run_dir/
├── boltz_run_20260101_120000.log     ← required: matches boltz_run_*.log
├── predictions/                      ← required: can be nested
│   ├── target_001/
│   │   ├── target_001_model_0.cif
│   │   ├── confidence_target_001_model_0.json
│   │   └── affinity_target_001_model_0.json
│   └── target_002/
│       └── ...
└── analyze_boltz.py
```

`predictions/` can be located anywhere below the top-level directory — the script walks the full subtree to find it.

---

## Outputs

### `boltz_run_summary.log`

Sections:

1. **Zsh execution script and switches** — reconstructed boltz invocation line(s) from the log
2. **Directory structure** — annotated tree up to 3 levels deep
3. **Run timing** — start/finish timestamps and total wall-clock runtime
4. **Prediction summaries** — per-target: CIF name, confidence score, affinity values, pIC₅₀
5. **CIF copy operations** — log of every file copied into `boltz_cif/`

### `boltz_summary.csv`

One row per prediction subdirectory:

| Column | Description |
|---|---|
| `input YAML name` | Source YAML inferred from log or directory name |
| `output cif name` | Filename of the `*_model_0.cif` model |
| `confidence_score` | Boltz-2 overall confidence score (0–1) |
| `affinity_pred_value1` | Raw affinity prediction (log-scale, kcal/mol units) |
| `affinity_probability_binary1` | Probability of binding (binary classifier output) |
| `pIC₅₀` | Derived pIC₅₀: `(6 − affinity_pred_value1) × 1.364` |

### `boltz_cif/`

Flat collection of all `*_model_0.cif` files discovered across the predictions tree. Suitable for bulk loading into PyMOL, ChimeraX, or a downstream PLIP/interaction analysis pipeline.

---

## pIC₅₀ Derivation

The affinity output from Boltz-2 (`affinity_pred_value1`) is a log-transformed binding free energy proxy. The conversion applied here is:

```
pIC₅₀ = (6 − affinity_pred_value1) × 1.364
```

This is a heuristic approximation; treat values as relative rankings rather than absolute potency predictions.

---

## Notes

- **YAML association**: prediction directories are matched to input YAMLs by stem name. If no match is found, the script falls back to the first YAML detected in the log, then derives a name from the directory itself — no prediction is silently dropped.
- **Robustness**: the script tolerates missing confidence or affinity JSONs, absent CIF files, and non-standard timestamp formats. Failures are logged per-prediction rather than aborting the run.
- **Log parsing**: the invocation heuristic looks for lines containing both `boltz` and `python`/`zsh`. If none are found, it falls back to `Running structure prediction` / `Running affinity prediction` lines.

---

## Compatibility

Tested against Boltz-2 output structure as of early 2026. The script assumes:
- Log filename matches `boltz_run_*.log`
- Confidence JSONs match `confidence*_model_0.json`
- Affinity JSONs match `affinity*.json`
- Model CIFs match `*_model_0.cif`

---

## Licence

MIT
