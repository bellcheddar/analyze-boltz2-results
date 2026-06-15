# 📊 analyze_boltz.py

> **Harvest a sprawling Boltz-2 output tree into one tidy summary, CSV, and CIF folder.**

![python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white) ![dependencies](https://img.shields.io/badge/dependencies-zero-00897B) ![engine](https://img.shields.io/badge/engine-Boltz--2-467FF7) ![licence](https://img.shields.io/badge/licence-MIT-9b51e0) ![author](https://img.shields.io/badge/author-Marc%20C.%20Deller%2C%20D.Phil.-1C244B)

<table>
<tr>
<td>🌐 <b>Website</b></td><td><a href="https://marcdeller.com" target="_blank" rel="noopener noreferrer">marcdeller.com</a></td>
<td>✉️ <b>Contact</b></td><td><a href="mailto:marc@marcdeller.com">marc@marcdeller.com</a></td>
<td>🐙 <b>GitHub</b></td><td><a href="https://github.com/bellcheddar/analyze-boltz2-results" target="_blank" rel="noopener noreferrer">bellcheddar/analyze-boltz2-results</a></td>
</tr>
</table>

---

A post-run analysis script for [Boltz-2](https://github.com/jwohlwend/boltz) co-folding predictions. Run it in any directory containing a `boltz_run_*.log` file and a `predictions/` subdirectory to automatically harvest confidence scores, affinity predictions, CIF models, and run metadata into a clean summary report and CSV.

Why it matters: a Boltz-2 batch leaves behind a deep, scattered output tree (per-target directories, confidence JSONs, affinity JSONs, ModelCIFs, and a verbose log) that is painful to read by hand and impossible to rank at a glance. analyze_boltz.py walks the whole tree, extracts every useful number, derives a pIC50 estimate, and consolidates everything into a human-readable summary, a machine-readable CSV, and a flat folder of all model CIFs. It is useful for anyone screening many complexes: instant triage and ranking of predictions by confidence and predicted affinity, with robust handling of missing or malformed files so no result is silently dropped.

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

---

## 👤 Author

**Marc C. Deller, D.Phil.**  
Structural biologist & drug discovery scientist  

<table>
<tr>
<td>🌐</td><td><a href="https://marcdeller.com" target="_blank" rel="noopener noreferrer">marcdeller.com</a></td>
<td>✉️</td><td><a href="mailto:marc@marcdeller.com">marc@marcdeller.com</a></td>
<td>🐙</td><td><a href="https://github.com/bellcheddar/analyze-boltz2-results" target="_blank" rel="noopener noreferrer">github.com/bellcheddar/analyze-boltz2-results</a></td>
</tr>
</table>
