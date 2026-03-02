#!/usr/bin/env python3
import os
import re
import json
import csv
import shutil
from pathlib import Path
from datetime import datetime

TOP = Path(".").resolve()
LOG_PATTERN = re.compile(r"boltz_run_.*\.log")
PREDICTIONS_DIR_NAME = "predictions"
BOLTZ_CIF_DIR_NAME = "boltz_cif"


def find_boltz_log(top_dir: Path) -> Path | None:
    """Find the first boltz_run_* .log file in the top-level directory."""
    for p in sorted(top_dir.iterdir()):
        if p.is_file() and LOG_PATTERN.fullmatch(p.name):
            return p
    return None


def parse_start_finish_times(log_text: str) -> tuple[str | None, str | None, str | None]:
    start_line = None
    finish_line = None
    for line in log_text.splitlines():
        if "=== Started at" in line:
            start_line = line.strip()
        elif "=== Finished at" in line:
            finish_line = line.strip()

    total_runtime_str = None
    if start_line and finish_line:
        def parse_time(s: str) -> datetime | None:
            m = re.search(r"=== (Started|Finished) at (.*) ===", s)
            if not m:
                return None
            timestr = m.group(2).strip()
            parts = timestr.split()
            # e.g. Mon Feb  9 11:26:01 GMT 2026
            if len(parts) >= 6:
                timestr_no_tz = " ".join(parts[0:4] + parts[5:])
                fmt = "%a %b %d %H:%M:%S %Y"
            else:
                timestr_no_tz = timestr
                fmt = "%a %b %d %H:%M:%S %Y"
            try:
                return datetime.strptime(timestr_no_tz, fmt)
            except Exception:
                return None

        t_start = parse_time(start_line)
        t_finish = parse_time(finish_line)
        if t_start and t_finish:
            delta = t_finish - t_start
            total_runtime_str = f"Total runtime: {delta} (from start/finish timestamps)"

    return start_line, finish_line, total_runtime_str


def summarize_zsh_command(log_text: str) -> str:
    """
    More permissive heuristic for the invocation line.

    We now:
    - Look for any line containing 'boltz' and 'python' or 'zsh',
    - Fall back to the first line mentioning 'Running structure prediction' or 'Running affinity prediction'.
    """
    lines = log_text.splitlines()
    candidates = []

    for line in lines:
        stripped = line.strip()
        if ("boltz" in stripped.lower()) and ("python" in stripped.lower() or "zsh" in stripped.lower()):
            candidates.append(stripped)

    if candidates:
        return " | ".join(candidates)

    # Fallback: high-level run description
    for line in lines:
        stripped = line.strip()
        if "Running structure prediction" in stripped or "Running affinity prediction" in stripped:
            candidates.append(stripped)
    if candidates:
        return " | ".join(candidates)

    # Last resort: first non-empty line
    for line in lines:
        if line.strip():
            return f"(Heuristic) {line.strip()}"

    return "No clear zsh or boltz invocation line identified."


def summarize_directory_structure(top_dir: Path, max_depth: int = 3) -> str:
    lines = []

    def walk(path: Path, depth: int):
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for entry in entries:
            rel = entry.relative_to(top_dir)
            indent = "  " * depth
            if entry.is_dir():
                lines.append(f"{indent}{rel}/")
                walk(entry, depth + 1)
            else:
                lines.append(f"{indent}{rel}")

    lines.append(f"{top_dir.name}/")
    walk(top_dir, 1)
    return "\n".join(lines)


def extract_yaml_inputs_from_log(log_text: str) -> list[str]:
    yaml_set = set()
    pattern = re.compile(r"Generating MSA for\s+([^\s]+\.ya?ml)\b")
    for line in log_text.splitlines():
        m = pattern.search(line)
        if m:
            yaml_set.add(m.group(1))
    return sorted(yaml_set)


def extract_runtime_and_yaml_summary(log_text: str) -> tuple[str | None, list[str]]:
    _, _, total_runtime_str = parse_start_finish_times(log_text)
    yaml_files = extract_yaml_inputs_from_log(log_text)
    return total_runtime_str, yaml_files


def find_predictions_dir(top_dir: Path) -> Path | None:
    """
    Find a 'predictions' directory anywhere below the top-level directory.
    This fixes the 'No predictions directory found' issue if predictions/
    is not directly under TOP.
    """
    for root, dirs, files in os.walk(top_dir):
        for d in dirs:
            if d == PREDICTIONS_DIR_NAME:
                return Path(root) / d
    return None


def summarize_predictions(predictions_dir: Path, yaml_paths_from_log: list[str]) -> tuple[list[dict], list[str]]:
    """
    Fully automatic discovery of predictions:

    - First, build a list of prediction subdirs under predictions/.
    - For each subdir, try to associate with a YAML based on stem,
      but if that fails, still include it with a best-guess 'input YAML name'.
    """
    rows = []
    log_lines = []

    if not predictions_dir or not predictions_dir.exists():
        return rows, ["No predictions directory found."]

    pred_dirs = [d for d in predictions_dir.iterdir() if d.is_dir()]
    pred_dirs_sorted = sorted(pred_dirs, key=lambda d: d.name)

    yaml_info = []
    for ypath in yaml_paths_from_log:
        y = Path(ypath)
        yaml_info.append({"full": ypath, "name": y.name, "stem": y.stem})

    # Map prediction dirs to best YAML match
    dir_to_yaml = {}
    for d in pred_dirs_sorted:
        dname = d.name
        best_yaml = None
        for y in yaml_info:
            if y["stem"] in dname:
                best_yaml = y["full"]
                break
        if not best_yaml and yaml_info:
            # If nothing matches, just assign the first YAML to avoid dropping data
            best_yaml = yaml_info[0]["full"]
        dir_to_yaml[dname] = best_yaml

    for pred_dir in pred_dirs_sorted:
        pred_name = pred_dir.name
        input_yaml_name = dir_to_yaml.get(pred_name)

        if input_yaml_name is None:
            # Last resort: derive from directory name
            input_yaml_name = pred_name + ".yaml"

        # CIF
        cif_files = sorted(pred_dir.glob("*_model_0.cif"))
        cif_file = cif_files[0] if cif_files else None

        # confidence JSON
        confidence_json_files = sorted(pred_dir.glob("confidence*_model_0.json"))
        confidence_json = confidence_json_files[0] if confidence_json_files else None

        # affinity JSON
        affinity_json_files = sorted(pred_dir.glob("affinity*.json"))
        affinity_json = affinity_json_files[0] if affinity_json_files else None

        confidence_score = None
        if confidence_json and confidence_json.is_file():
            try:
                with confidence_json.open() as f:
                    conf_data = json.load(f)
                confidence_score = conf_data.get("confidence_score", None)
            except Exception as e:
                confidence_score = None
                log_lines.append(f"{pred_name}: Failed to parse {confidence_json.name}: {e}")

        affinity_pred_value1 = None
        affinity_probability_binary1 = None
        if affinity_json and affinity_json.is_file():
            try:
                with affinity_json.open() as f:
                    aff_data = json.load(f)
                affinity_pred_value1 = aff_data.get("affinity_pred_value1", None)
                affinity_probability_binary1 = aff_data.get("affinity_probability_binary1", None)
            except Exception as e:
                log_lines.append(f"{pred_name}: Failed to parse {affinity_json.name}: {e}")

        output_cif_name = cif_file.name if cif_file else ""
        pIC50 = None
        if affinity_pred_value1 is not None:
            try:
                pIC50 = (6 - float(affinity_pred_value1)) * 1.364
            except Exception:
                pIC50 = None

        rows.append(
            {
                "input_yaml_name": input_yaml_name,
                "output_cif_name": output_cif_name,
                "confidence_score": confidence_score,
                "affinity_pred_value1": affinity_pred_value1,
                "affinity_probability_binary1": affinity_probability_binary1,
                "pIC50": pIC50,
                "prediction_dir": pred_name,
                "cif_path": str(cif_file) if cif_file else "",
            }
        )

        log_lines.append(
            f"{pred_name} (from {input_yaml_name}): "
            f"CIF={output_cif_name or 'MISSING'}, "
            f"confidence_score={confidence_score}, "
            f"affinity_pred_value1={affinity_pred_value1}, "
            f"affinity_probability_binary1={affinity_probability_binary1}, "
            f"pIC50={pIC50}"
        )

    return rows, log_lines


def copy_cif_files(rows: list[dict], top_dir: Path, dst_dir_name: str = BOLTZ_CIF_DIR_NAME) -> list[str]:
    """
    Copy each discovered *_model_0.cif into top_dir/dst_dir_name, keeping filenames.

    This will copy whatever CIFs were found in summarize_predictions, so
    'No CIF files copied' should only occur if genuinely none exist.
    """
    dst = top_dir / dst_dir_name
    dst.mkdir(exist_ok=True)
    log_lines = []
    for row in rows:
        cif_path = row.get("cif_path")
        if not cif_path:
            log_lines.append(f"{row.get('prediction_dir', '?')}: No CIF model_0 file to copy.")
            continue
        src = Path(cif_path)
        if not src.is_file():
            log_lines.append(f"{row.get('prediction_dir', '?')}: CIF file not found at {src}.")
            continue
        dest_file = dst / src.name
        try:
            shutil.copy2(src, dest_file)
            log_lines.append(f"Copied {src} -> {dest_file}")
        except Exception as e:
            log_lines.append(f"Failed to copy {src} -> {dest_file}: {e}")
    return log_lines


def write_csv(rows: list[dict], csv_path: Path) -> None:
    """
    Populate CSV with all discovered predictions.

    This fixes the 'No data in CSV summary' case as long as there is at least
    one prediction subdirectory.
    """
    fieldnames = [
        "input YAML name",
        "output cif name",
        "confidence_score",
        "affinity_pred_value1",
        "affinity_probability_binary1",
        "pIC50",
    ]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "input YAML name": row.get("input_yaml_name", ""),
                    "output cif name": row.get("output_cif_name", ""),
                    "confidence_score": row.get("confidence_score", ""),
                    "affinity_pred_value1": row.get("affinity_pred_value1", ""),
                    "affinity_probability_binary1": row.get("affinity_probability_binary1", ""),
                    "pIC50": row.get("pIC50", ""),
                }
            )


def main():
    # 1) Find and parse boltz_run_* log
    log_file = find_boltz_log(TOP)
    if log_file is None:
        raise SystemExit("No boltz_run_*_log file found in top-level directory.")

    log_text = log_file.read_text(errors="ignore")

    zsh_summary = summarize_zsh_command(log_text)
    runtime_line, yaml_files = extract_runtime_and_yaml_summary(log_text)
    start_line, finish_line, total_runtime_str = parse_start_finish_times(log_text)
    dir_summary = summarize_directory_structure(TOP)

    # 2) Find predictions directory anywhere under TOP
    predictions_dir = find_predictions_dir(TOP)

    # 3) Summarize predictions (if any)
    prediction_rows, prediction_log_lines = summarize_predictions(predictions_dir, yaml_files)

    # 4) Copy CIF files into boltz_cif
    copy_log_lines = copy_cif_files(prediction_rows, TOP)

    # 5) Write CSV
    csv_path = TOP / "boltz_summary.csv"
    write_csv(prediction_rows, csv_path)

    # 6) Write summary log file
    out_log = TOP / "boltz_run_summary.log"
    with out_log.open("w") as f:
        f.write("Boltz prediction run summary\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Top-level directory: {TOP}\n")
        f.write(f"Original log file: {log_file.name}\n\n")

        f.write("1) Zsh execution script and switches\n")
        f.write("----------------------------------\n")
        f.write(zsh_summary + "\n\n")

        f.write("2) Directory structure from top-level\n")
        f.write("------------------------------------\n")
        f.write(dir_summary + "\n\n")

        f.write("3) boltz_run_* log summary\n")
        f.write("--------------------------\n")
        if start_line:
            f.write(f"{start_line}\n")
        if finish_line:
            f.write(f"{finish_line}\n")
        if total_runtime_str:
            f.write(f"{total_runtime_str}\n")
        elif runtime_line:
            f.write(f"{runtime_line}\n")
        else:
            f.write("Total run time: not found in log (heuristic search failed).\n")
        if yaml_files:
            f.write("Input YAML files detected in log:\n")
            for y in yaml_files:
                f.write(f"  - {y}\n")
        else:
            f.write("No YAML file references detected in log.\n")
        f.write("\n")

        f.write("4) Prediction summaries\n")
        f.write("-----------------------\n")
        if prediction_log_lines:
            for line in prediction_log_lines:
                f.write(line + "\n")
        else:
            f.write("No prediction subdirectories found under a predictions/ directory.\n")
        f.write("\n")

        f.write("5) CIF copy operations\n")
        f.write("----------------------\n")
        if copy_log_lines:
            for line in copy_log_lines:
                f.write(line + "\n")
        else:
            f.write("No CIF files copied.\n")
        f.write("\n")

        f.write(f"CSV summary written to: {csv_path.name}\n")

    print(f"Summary written to {out_log}")
    print(f"CSV written to {csv_path}")
    print(f"CIFs copied to {BOLTZ_CIF_DIR_NAME}/")


if __name__ == "__main__":
    main()
