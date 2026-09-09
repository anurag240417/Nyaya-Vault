"""
Standalone OR-Tools sanity check - no FastAPI, no Supabase, nothing from
this project. If this script fails, the problem is your Python
environment / ortools install, not your timeline integration code.

Run from backend/ with your venv activated:
    python check_ortools.py

Expected output: both cases print PASS.
"""
from ortools.sat.python import cp_model


def case_feasible_should_pass() -> bool:
    """Two events, far enough apart in time - solver should find a schedule."""
    model = cp_model.CpModel()
    a = model.NewIntVar(0, 100, "a")
    b = model.NewIntVar(0, 100, "b")
    model.Add(b >= a + 50)  # b must start at least 50 "minutes" after a
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


def case_infeasible_should_fail() -> bool:
    """Contradictory constraints - solver must correctly report no solution exists."""
    model = cp_model.CpModel()
    a = model.NewIntVar(0, 10, "a")
    model.Add(a > 10)   # impossible given the variable's own bounds
    model.Add(a < 0)    # doubly impossible
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    return status == cp_model.INFEASIBLE


if __name__ == "__main__":
    print(f"ortools import: OK")

    ok1 = case_feasible_should_pass()
    print(f"Feasible case solved as feasible: {'PASS' if ok1 else 'FAIL'}")

    ok2 = case_infeasible_should_fail()
    print(f"Infeasible case correctly detected: {'PASS' if ok2 else 'FAIL'}")

    if ok1 and ok2:
        print("\nOR-Tools is installed and working correctly.")
    else:
        print("\nSomething is wrong with the ortools install itself.")
        raise SystemExit(1)