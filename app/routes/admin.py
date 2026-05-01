import os
import re
import sys
import subprocess
from flask import Blueprint, render_template, request, jsonify, current_app
from ..database import get_db

bp = Blueprint("admin", __name__)


@bp.route("/tests", methods=["GET", "POST"])
def tests():
    if request.method == "GET":
        db = get_db()
        last_run = db.execute(
            "SELECT * FROM test_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        history = db.execute(
            "SELECT id, run_at, total, passed, failed FROM test_runs ORDER BY id DESC LIMIT 10"
        ).fetchall()
        return render_template("admin/tests.html", last_run=last_run, history=history)

    tests_dir = os.path.join(os.path.dirname(current_app.root_path), "tests")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", tests_dir, "-v", "--tb=short", "--no-header"],
        capture_output=True, text=True, timeout=120,
        cwd=os.path.dirname(current_app.root_path)
    )
    output = proc.stdout + proc.stderr
    passed = failed = 0
    test_results = []
    for line in output.splitlines():
        m = re.search(r"(\d+) passed", line)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", line)
        if m:
            failed = int(m.group(1))
        tm = re.match(r"\S+::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)", line)
        if tm:
            test_results.append({"name": tm.group(1), "status": tm.group(2)})

    db = get_db()
    run_id = db.execute(
        "INSERT INTO test_runs (total, passed, failed, output) VALUES (?,?,?,?)",
        [passed + failed, passed, failed, output]
    ).lastrowid
    db.commit()
    return jsonify({
        "ok": True, "run_id": run_id,
        "passed": passed, "failed": failed,
        "total": passed + failed,
        "tests": test_results, "output": output
    })
