import csv
import json

SHIFTS = {"M", "A", "E", "R", "B"}


def read_input(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    required = {"N", "D", "N_s", "N_g", "m", "a", "e", "T", "days", "K", "leaves"}
    if len(rows) != 1 or reader.fieldnames is None or set(reader.fieldnames) != required:
        raise ValueError("input CSV must contain exactly one valid data row")
    row = rows[0]
    instance = {name: int(row[name]) for name in ("N", "D", "N_s", "N_g", "m", "a", "e")}
    instance["T"] = float(row["T"])
    instance["days"] = row["days"]
    instance["K"] = int(row["K"])
    instance["leaves"] = row["leaves"]
    if any(instance[name] < 0 for name in ("N", "D", "N_s", "N_g", "m", "a", "e", "K")):
        raise ValueError("instance values must be non-negative")
    if instance["N_s"] + instance["N_g"] != instance["N"]:
        raise ValueError("N_s + N_g must equal N")
    if len(instance["days"]) != instance["D"] or set(instance["days"]) - {"G", "S"}:
        raise ValueError("days must contain exactly D characters from G and S")
    if len(instance["leaves"]) != instance["N"] * instance["D"] or set(instance["leaves"]) - {"W", "L"}:
        raise ValueError("leaves must contain one W or L marker per nurse-day")
    return instance


def read_solution(json_path):
    with open(json_path, encoding="utf-8") as json_file:
        solution = json.load(json_file)
    if not isinstance(solution, dict):
        raise ValueError("solution must be a JSON object")
    return solution


def expected_keys(instance):
    return {f"N{nurse}_{day}" for nurse in range(instance["N"]) for day in range(instance["D"])}


def shift(solution, nurse, day):
    return solution[f"N{nurse}_{day}"]


def verify_solution(instance, solution):
    if set(solution) != expected_keys(instance):
        return False
    for nurse in range(instance["N"]):
        for day in range(instance["D"]):
            value = shift(solution, nurse, day)
            if not isinstance(value, str) or value not in SHIFTS:
                return False
            if value == "B" and nurse >= instance["N_s"]:
                return False
            if instance["leaves"][nurse * instance["D"] + day] == "L" and value != "R":
                return False
    for nurse in range(instance["N"]):
        for day in range(instance["D"] - 1):
            current = shift(solution, nurse, day)
            following = shift(solution, nurse, day + 1)
            if current in {"M", "B"} and following in {"M", "B"}:
                return False
            if current == "E" and following in {"M", "B"}:
                return False
            if current == "B" and following not in {"R", "E"}:
                return False
    for nurse in range(instance["N"]):
        for start in range(instance["D"] - 5):
            if all(shift(solution, nurse, day) != "R" for day in range(start, start + 6)):
                return False
    for day, day_type in enumerate(instance["days"]):
        counts = {value: 0 for value in SHIFTS}
        for nurse in range(instance["N"]):
            counts[shift(solution, nurse, day)] += 1
        if day_type == "G" and counts["B"]:
            return False
        if counts["M"] + counts["B"] != instance["m"]:
            return False
        if counts["A"] + counts["B"] != instance["a"] or counts["E"] != instance["e"]:
            return False
        if day_type == "S" and not any(shift(solution, nurse, day) == "B" for nurse in range(instance["N_s"])):
            return False
    for nurse in range(instance["N"]):
        total = sum(shift(solution, nurse, day) != "R" for day in range(instance["D"]))
        total += sum(shift(solution, nurse, day) == "B" for day in range(instance["D"]))
        if total > instance["K"]:
            return False
    return True


def calculate_objective(instance, solution):
    objective = 0
    for nurse in range(instance["N"]):
        mornings = sum(shift(solution, nurse, day) in {"M", "B"} for day in range(instance["D"]))
        afternoons = sum(shift(solution, nurse, day) in {"A", "B"} for day in range(instance["D"]))
        evenings = sum(shift(solution, nurse, day) == "E" for day in range(instance["D"]))
        total = mornings + afternoons + evenings
        objective += 3 * (mornings ** 2 + afternoons ** 2 + evenings ** 2) - total ** 2
    return objective
