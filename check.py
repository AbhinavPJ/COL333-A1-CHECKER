import argparse
import contextlib
import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
CHECKER = Path(__file__).resolve().parent
TEST_CASES = CHECKER / "test-cases"
MODEL_SOLUTIONS = CHECKER / "model-solutions"

TEST_ALIASES = {
    "suite_001": TEST_CASES / "suite_001",
    "suite_002": TEST_CASES / "suite_002",
    "suite_003": TEST_CASES / "suite_003",
    "suite_004": TEST_CASES / "suite_004",
}


def parser():
    result = argparse.ArgumentParser(description="Check the root-level assignment submission.")
    result.add_argument(
        "-t", "--tests", action="append",
        help="test-folder alias/path; repeat or comma-separate values (default: all)")
    result.add_argument("-p", "--part", choices=("a", "b", "both"), default="both")
    result.add_argument("--timeout", type=float, help="hard wall-clock limit per run")
    result.add_argument("--python", default=sys.executable)
    result.add_argument("--keep-outputs", type=Path)
    result.add_argument("--overwrite-models", "--overwrite", action="store_true")
    result.add_argument("--fail-fast", action="store_true")
    result.add_argument("--list", action="store_true", help="list test aliases and exit")
    return result


def tokens(values):
    if not values:
        return ["all"]
    return [piece.strip() for value in values for piece in value.split(",") if piece.strip()]


def resolve_test_folders(values):
    selected = []
    for token in tokens(values):
        if token == "all":
            selected.extend(TEST_ALIASES.values())
        elif token in TEST_ALIASES:
            selected.append(TEST_ALIASES[token])
        else:
            supplied = Path(token).expanduser()
            candidates = [supplied] if supplied.is_absolute() else [Path.cwd() / supplied, TEST_CASES / supplied]
            selected.extend(candidate for candidate in candidates if candidate.is_dir())
            if not any(candidate.is_dir() for candidate in candidates):
                raise ValueError(f"unknown test folder or alias: {token}")
    seen = set()
    result = []
    for path in selected:
        path = path.resolve()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def read_budget(csv_path):
    with csv_path.open(newline="", encoding="utf-8") as source:
        return float(next(csv.DictReader(source))["T"])


def verify(csv_path, output_path):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            instance = verifier.read_input(csv_path)
            solution = verifier.read_solution(output_path)
            valid = verifier.verify_solution(instance, solution)
        return valid, verifier.calculate_objective(instance, solution) if valid else None, ""
    except Exception as error:
        return False, None, f"{type(error).__name__}: {error}"


def model_result(folder_name, case, part):
    model_path = MODEL_SOLUTIONS / folder_name / f"{case.stem}.json"
    if not model_path.is_file():
        return None
    valid, objective, _ = verify(case, model_path)
    if valid:
        return "FEASIBLE", objective if part == "b" else None
    try:
        solution = verifier.read_solution(model_path)
    except Exception:
        return "UNKNOWN", None
    return ("INFEASIBLE", None) if solution == {} else ("UNKNOWN", None)


def is_empty_solution(output):
    try:
        return verifier.read_solution(output) == {}
    except Exception:
        return False


def compare(status, objective, output, reference):
    if reference is None or reference[0] == "UNKNOWN":
        return "PASS" if status == "PASS" else "FAIL"
    if reference[0] == "INFEASIBLE":
        return "PASS" if status == "INVALID" and is_empty_solution(output) else "FAIL"
    if status != "PASS":
        return "FAIL"
    if reference[1] is None:
        return "PASS"
    if objective < reference[1]:
        return "MORE_OPTIMAL"
    if objective > reference[1]:
        return "SUBOPTIMAL"
    return "MATCHED"


def execute(python, part, case, timeout, temporary):
    script = REPOSITORY / f"part_{part}.py"
    output = temporary / f"{case.parent.name}_part_{part}_{case.stem}.json"
    if not script.is_file():
        return "MISSING_SCRIPT", None, 0.0, output, str(script)
    started = time.perf_counter()
    try:
        process = subprocess.run(
            [python, str(script), str(case), str(output)], cwd=REPOSITORY,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", None, time.perf_counter() - started, output, ""
    elapsed = time.perf_counter() - started
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        return "RUNTIME_ERROR", None, elapsed, output, detail[-300:]
    if not output.is_file():
        return "NO_OUTPUT", None, elapsed, output, process.stdout.strip()[-300:]
    valid, objective, detail = verify(case, output)
    return ("PASS" if valid else "INVALID"), objective, elapsed, output, detail


def main():
    arguments = parser().parse_args()
    if arguments.list:
        for name, path in TEST_ALIASES.items():
            print(f"{name:12} {path.relative_to(CHECKER)}")
        return 0
    if arguments.timeout is not None and arguments.timeout <= 0:
        parser().error("--timeout must be positive")
    try:
        folders = resolve_test_folders(arguments.tests)
    except ValueError as error:
        parser().error(str(error))
    cases = [(folder.name, case) for folder in folders for case in sorted(folder.glob("*.csv"))]
    if not cases:
        parser().error("no CSV test cases found in the selected folder(s)")
    parts = ("a", "b") if arguments.part == "both" else (arguments.part,)
    rows = []
    details = []
    with tempfile.TemporaryDirectory(prefix="col333-check-") as temporary_name:
        temporary = Path(temporary_name)
        for folder_name, case in cases:
            for part in parts:
                timeout = arguments.timeout if arguments.timeout is not None else max(0.05, read_budget(case) + 2.0)
                status, objective, elapsed, output, detail = execute(arguments.python, part, case, timeout, temporary)
                if arguments.overwrite_models and output.is_file():
                    target = MODEL_SOLUTIONS / folder_name / f"{case.stem}.json"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(output, target)
                result = compare(status, objective, output, model_result(folder_name, case, part))
                rows.append((part.upper(), f"{folder_name}/{case.name}", result, objective, elapsed))
                if detail:
                    details.append((part, case.name, detail))
                if arguments.keep_outputs and output.is_file():
                    arguments.keep_outputs.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(output, arguments.keep_outputs / output.name)
                print(f"{part.upper()} {folder_name}/{case.name}: {result} objective={objective} seconds={elapsed:.4f}", flush=True)
                if arguments.fail_fast and result == "FAIL":
                    break
            if arguments.fail_fast and rows[-1][2] == "FAIL":
                break
    passed = sum(row[2] != "FAIL" for row in rows)
    print(f"Summary: {passed}/{len(rows)} runs passed")
    counts = {status: sum(row[2] == status for row in rows)
              for status in ("MATCHED", "MORE_OPTIMAL", "SUBOPTIMAL", "PASS", "FAIL")}
    print("Verdicts: "
          f"MATCHED={counts['MATCHED']} "
          f"MORE OPTIMAL={counts['MORE_OPTIMAL']} "
          f"SUBOPTIMAL={counts['SUBOPTIMAL']} "
          f"PASS={counts['PASS']} "
          f"FAIL={counts['FAIL']}")
    print(f"Total time: {sum(row[4] for row in rows):.4f} seconds")
    for part, case, detail in details:
        print(f"[{part} {case}] {detail}", file=sys.stderr)
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    import verifier
    raise SystemExit(main())
