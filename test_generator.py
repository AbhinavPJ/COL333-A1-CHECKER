import contextlib
import csv
import io
import json
import random
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import verifier


def can_assign(nurse, day, shift, days, ns, k, previous, streak, load):
    if streak[nurse] >= 5:
        return False
    cost = 2 if shift == 'B' else 1
    if load[nurse] + cost > k:
        return False
    if shift == 'B':
        return nurse < ns and days[day] == 'S' and previous[nurse] not in {'M', 'B', 'E'}
    if shift == 'M':
        return previous[nurse] not in {'M', 'B', 'E'}
    if shift == 'A':
        return previous[nurse] != 'B'
    return shift == 'E'


def build_roster(spec):
    n = spec['N']
    d = spec['D']
    ns = spec['N_s']
    k = spec['K']
    days = spec['days']
    previous = [None] * n
    streak = [0] * n
    load = [0] * n
    roster = []

    def search(day):
        if day == d:
            return True
        b = 1 if days[day] == 'S' else 0
        roles = [('B', b), ('M', spec['m'] - b), ('A', spec['a'] - b), ('E', spec['e'])]
        assignment = ['R'] * n

        def choose(role_index, used):
            if role_index == len(roles):
                next_previous = previous[:]
                next_streak = streak[:]
                next_load = load[:]
                for nurse in range(n):
                    shift = assignment[nurse]
                    next_previous[nurse] = shift
                    next_streak[nurse] = 0 if shift == 'R' else streak[nurse] + 1
                    next_load[nurse] += 2 if shift == 'B' else int(shift != 'R')
                old_previous = previous[:]
                old_streak = streak[:]
                old_load = load[:]
                previous[:], streak[:], load[:] = next_previous, next_streak, next_load
                roster.append(assignment[:])
                if search(day + 1):
                    return True
                previous[:], streak[:], load[:] = old_previous, old_streak, old_load
                roster.pop()
                return False

            shift, count = roles[role_index]
            candidates = [
                nurse for nurse in range(n)
                if nurse not in used and can_assign(
                    nurse, day, shift, days, ns, k, previous, streak, load
                )
            ]
            candidates.sort(key=lambda nurse: (load[nurse], streak[nurse], nurse))
            if len(candidates) < count:
                return False
            for selected in combinations(candidates, count):
                for nurse in selected:
                    assignment[nurse] = shift
                if choose(role_index + 1, used | set(selected)):
                    return True
                for nurse in selected:
                    assignment[nurse] = 'R'
            return False

        return choose(0, set())

    if not search(0):
        raise ValueError(f"could not build witness for {spec['name']}")
    return roster


def day_pattern(length, index, randomizer):
    mode = index % 8
    if mode == 0:
        return 'G' * length
    if mode == 1:
        return 'S' * length
    if mode == 2:
        return ''.join('S' if day % 2 == 0 else 'G' for day in range(length))
    if mode == 3:
        split = max(1, length // 2)
        return 'S' * split + 'G' * (length - split)
    if mode == 4:
        split = max(1, length // 2)
        return 'G' * split + 'S' * (length - split)
    probability = 0.2 if mode == 5 else 0.8 if mode == 6 else 0.45
    return ''.join('S' if randomizer.random() < probability else 'G' for _ in range(length))


def workload(roster):
    return max(
        sum(2 if shift == 'B' else int(shift != 'R') for shift in row)
        for row in zip(*roster)
    )


def valid_spec(index, randomizer):
    n = randomizer.choice([8, 10, 12, 16, 20, 24, 30, 36, 40, 50])
    d = randomizer.choice([1, 2, 5, 6, 7, 8, 14, 21, 30])
    days = day_pattern(d, index, randomizer)
    if set(days) == {'G'}:
        ns = randomizer.randint(0, n)
    else:
        minimum_surgical = 2 if 'SS' in days else 1
        ns = randomizer.randint(minimum_surgical, n)
    limit = max(1, n // 8)
    if index % 17 == 0 and set(days) == {'G'}:
        m = a = e = 0
    else:
        m = randomizer.randint(1, limit)
        a = randomizer.randint(1, limit)
        e = randomizer.randint(0, limit)
    return {
        'name': f'valid_{index:04d}',
        'N': n,
        'D': d,
        'N_s': ns,
        'N_g': n - ns,
        'm': m,
        'a': a,
        'e': e,
        'T': 10,
        'days': days,
        'K': 2 * d
    }


def invalid_spec(index, randomizer):
    kind = index % 7
    if kind == 0:
        n, d, ns, m, a, e, k = 12, 8, 6, 13, 1, 1, 10
        days, leaves = 'G' * d, 'W' * (n * d)
    elif kind == 1:
        n, d, ns, m, a, e, k = 12, 8, 6, 1, 1, 1, 0
        days, leaves = day_pattern(d, index, randomizer), 'W' * (n * d)
    elif kind == 2:
        n, d, ns, m, a, e, k = 10, 7, 0, 1, 1, 1, 7
        days, leaves = 'S' * d, 'W' * (n * d)
    elif kind == 3:
        n, d, ns, m, a, e, k = 10, 7, 5, 1, 1, 1, 7
        days, leaves = day_pattern(d, index, randomizer), 'L' * (n * d)
    elif kind == 4:
        n, d, ns, m, a, e, k = 8, 6, 2, 1, 1, 1, 6
        days = 'SGGGGS'
        leaves = ''.join(
            'L' if nurse < ns and days[day] == 'S' else 'W'
            for nurse in range(n)
            for day in range(d)
        )
    elif kind == 5:
        n, d, ns, m, a, e, k = 3, 6, 0, 1, 1, 1, 6
        days, leaves = 'G' * d, 'W' * (n * d)
    else:
        n, d, ns, m, a, e, k = 4, 2, 0, 2, 2, 1, 1
        days, leaves = 'G' * d, 'W' * (n * d)
    return {
        'name': f'invalid_{index:04d}',
        'N': n,
        'D': d,
        'N_s': ns,
        'N_g': n - ns,
        'm': m,
        'a': a,
        'e': e,
        'T': 3,
        'days': days,
        'K': k,
        'leaves': leaves
    }


def write_case(suite, model_dir, spec, roster, randomizer):
    if roster is not None:
        leave_probability = randomizer.choice([0.0, 0.1, 0.25, 0.45, 0.65])
        leaves = []
        for nurse in range(spec['N']):
            block = []
            for day in range(spec['D']):
                shift = roster[day][nurse]
                block.append('L' if shift == 'R' and randomizer.random() < leave_probability else 'W')
            leaves.append(''.join(block))
        spec['leaves'] = ''.join(leaves)

    fields = ['N', 'D', 'N_s', 'N_g', 'm', 'a', 'e', 'T', 'days', 'K', 'leaves']
    input_path = suite / f"{spec['name']}.csv"
    with input_path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerow({field: spec[field] for field in fields})

    if roster is None:
        solution = {}
    else:
        solution = {
            f'N{nurse}_{day}': roster[day][nurse]
            for nurse in range(spec['N'])
            for day in range(spec['D'])
        }
        with contextlib.redirect_stdout(io.StringIO()):
            instance = verifier.read_input(str(input_path))
            if not verifier.verify_solution(instance, solution):
                raise ValueError(f"invalid witness for {spec['name']}")
    (model_dir / f"{spec['name']}.json").write_text(
        json.dumps(solution), encoding='utf-8'
    )


def generate_suite(base=None, count=1000, seed=20260824):
    base = Path(base or Path(__file__).parent / 'test-cases')
    base.mkdir(parents=True, exist_ok=True)
    index = 1
    while (base / f'suite_{index:03d}').exists():
        index += 1
    suite = base / f'suite_{index:03d}'
    model_dir = Path(__file__).parent / 'model-solutions' / suite.name
    suite.mkdir()
    model_dir.mkdir(parents=True)
    randomizer = random.Random(seed)
    valid_count = count * 7 // 10
    for index in range(count):
        if index < valid_count:
            spec = valid_spec(index, randomizer)
            roster = build_roster(spec)
            spec['K'] = workload(roster) + randomizer.choice([0, 0, 1, 2])
        else:
            spec = invalid_spec(index - valid_count, randomizer)
            roster = None
        spec['name'] = f'test{index + 1}'
        write_case(suite, model_dir, spec, roster, randomizer)

    return suite


if __name__ == '__main__':
    print(generate_suite())
