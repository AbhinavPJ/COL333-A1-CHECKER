import contextlib
import csv
import io
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def read_json(path):
    with path.open(encoding='utf-8') as file:
        return json.load(file)


def suites():
    test_root = CHECKER / 'test-cases'
    if not test_root.is_dir():
        return []
    return sorted(path for path in test_root.iterdir() if path.is_dir() and any(path.glob('*.csv')))


def expected_type(input_path):
    model_path = CHECKER / 'model-solutions' / input_path.parent.name / f'{input_path.stem}.json'
    try:
        return 'empty' if read_json(model_path) == {} else 'valid'
    except (OSError, json.JSONDecodeError):
        return 'valid'


def verify_solution(verifier, instance, solution):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return verifier.verify_solution(instance, solution)
    except (KeyError, TypeError, ValueError):
        return False


def is_correct(verifier, instance, input_path, solution):
    if expected_type(input_path) == 'empty':
        return solution == {}
    return verify_solution(verifier, instance, solution)


def timeout_for(input_path):
    try:
        with input_path.open(newline='', encoding='utf-8') as file:
            timeout = float(next(csv.DictReader(file))['T'])
        return max(1.0, timeout + 1.0)
    except (KeyError, OSError, StopIteration, ValueError):
        return 30.0


def solve_to_temp(input_path, directory, timeout=None):
    directory.mkdir(parents=True, exist_ok=True)
    temporary_path = directory / f'.{input_path.stem}.{uuid.uuid4().hex}.tmp'
    command = [sys.executable, str(ROOT / 'part_a.py'), str(input_path), str(temporary_path)]
    timeout = timeout or timeout_for(input_path)
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        temporary_path.unlink(missing_ok=True)
        return None, f'timeout after {timeout:g}s'
    if completed.returncode != 0 or not temporary_path.exists():
        temporary_path.unlink(missing_ok=True)
        return None, 'solver failed'
    try:
        solution = read_json(temporary_path)
    except (OSError, json.JSONDecodeError):
        temporary_path.unlink(missing_ok=True)
        return None, 'invalid JSON'
    return (temporary_path, solution), None


def overwrite_models():
    import verifier

    updated = 0
    failures = 0
    for suite in suites():
        model_dir = CHECKER / 'model-solutions' / suite.name
        for input_path in sorted(suite.glob('*.csv')):
            result, error = solve_to_temp(input_path, model_dir, timeout=60)
            if error:
                failures += 1
                print(f'FAIL {suite.name}/{input_path.name}: {error}')
                continue
            temporary_path, solution = result
            instance = verifier.read_input(str(input_path))
            if not is_correct(verifier, instance, input_path, solution):
                temporary_path.unlink(missing_ok=True)
                failures += 1
                print(f'FAIL {suite.name}/{input_path.name}: solver output is not correct')
                continue
            temporary_path.replace(model_dir / f'{input_path.stem}.json')
            updated += 1
        print(f'{suite.name}: overwritten')
    print(f'Model solutions updated: {updated}; failures: {failures}')
    return failures == 0


def evaluate():
    import verifier
    correct = 0
    total = 0
    for suite in suites():
        suite_correct = 0
        suite_total = 0
        solution_dir = CHECKER / 'solutions' / suite.name
        for input_path in sorted(suite.glob('*.csv')):
            suite_total += 1
            total += 1
            result, error = solve_to_temp(input_path, solution_dir)
            if error:
                print(f'FAIL {suite.name}/{input_path.name}: {error}')
                continue
            temporary_path, candidate = result
            temporary_path.replace(solution_dir / f'{input_path.stem}.json')
            instance = verifier.read_input(str(input_path))
            candidate_correct = is_correct(verifier, instance, input_path, candidate)
            if candidate_correct:
                correct += 1
                suite_correct += 1
            else:
                print(f'FAIL {suite.name}/{input_path.name}: incorrect solver output')
        print(f'{suite.name}: correct {suite_correct}/{suite_total}')
    print(f'Correct: {correct}/{total}')
    return correct == total

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {'overwrite', 'evaluate'}:
        print('Usage: python checker/check_a.py overwrite|evaluate')
        return 2
    if sys.argv[1] == 'overwrite':
        return 0 if overwrite_models() else 1
    return 0 if evaluate() else 1


if __name__ == '__main__':
    raise SystemExit(main())
