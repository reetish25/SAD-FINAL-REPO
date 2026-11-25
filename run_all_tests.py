#!/usr/bin/env python3
"""
Leafline Platform Unified Test Runner & Report Generator
Executes all test suites across the 3 microservices, API Gateway, and E2E integration.
Produces an audit-ready test summary report with pass/fail evidence.
"""

import sys
import time
import unittest
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent

def run_suite(name, cmd, cwd=None):
    print(f"\n{'='*70}\nRUNNING: {name}\n{'='*70}")
    t0 = time.time()
    res = subprocess.run(cmd, shell=True, cwd=cwd or ROOT_DIR, capture_output=True, text=True)
    duration = round(time.time() - t0, 2)
    passed = (res.returncode == 0)
    print(res.stdout)
    if res.stderr:
        print(res.stderr)
    print(f"RESULT: {'PASS' if passed else 'FAIL'} ({duration}s)")
    return {
        "suite": name,
        "passed": passed,
        "duration": duration,
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr
    }

def main():
    print("=" * 80)
    print("  LEAFLINE INTEGRATED PLATFORM - AUTOMATED VERIFICATION SUITE")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    suites = [
        # 1. Soil Service Unit Tests (Pure Rules & Boundaries)
        {
            "name": "Soil & Nutrient Service: Unit & Business Rules (NS-BR-01..08)",
            "cmd": "python -m unittest discover -s microservice-3-soil/tests -t microservice-3-soil -p test_rules.py -v"
        },
        # 2. Plant Health Service Inference Contract & ML Tests
        {
            "name": "Plant Health Service: PyTorch ML Inference & Severity (MobileNetV2, EfficientNetB0, Xception)",
            "cmd": "python -m pytest microservice-1-leafline/backend/tests/test_inference.py -o pythonpath=microservice-1-leafline/backend -v"
        },
        # 3. Plant Health Service API & Database Persistence Tests
        {
            "name": "Plant Health Service: REST API, Auth, Pesticide Versioning & Scans",
            "cmd": "python -m pytest microservice-1-leafline/backend/tests/test_api.py -o pythonpath=microservice-1-leafline/backend -v"
        },
        # 4. Weather Service Unit, Assessment & Sensor Tests
        {
            "name": "Environment & Weather Service: Open-Meteo, EDPS Alternaria Risk & Sensors",
            "cmd": "python -m pytest microservice-2-weather/backend/tests/ -o pythonpath=microservice-2-weather/backend -v"
        },
        # 5. API Gateway Mode B Synthesis & Resilient Fallback Tests
        {
            "name": "API Gateway & Orchestrator: Reverse Proxy Routing, Mode B Synthesis & Degradation",
            "cmd": "python -m pytest api-gateway/tests/test_gateway.py -v"
        },
        # 6. Platform-Wide E2E Cross-Service Integration Tests
        {
            "name": "Platform E2E Integration: Cross-Domain Synergy, Partial Failures & Rule Validation",
            "cmd": "python -m pytest tests/test_e2e_integration.py -v"
        }
    ]

    results = []
    for s in suites:
        r = run_suite(s["name"], s["cmd"])
        results.append(r)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count

    print("\n" + "=" * 80)
    print("  FINAL TEST EXECUTION SUMMARY")
    print("=" * 80)
    for idx, r in enumerate(results, 1):
        status_str = "[ PASS ]" if r["passed"] else "[ FAIL ]"
        print(f"{idx}. {status_str} {r['suite']} ({r['duration']}s)")

    print("-" * 80)
    print(f"Total Suites Executed: {total} | Passed: {passed_count} | Failed: {failed_count}")
    print("=" * 80)

    # Save Markdown test report
    report_path = ROOT_DIR / "documentation" / "TEST_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Leafline Platform — Automated Test Execution Report\n\n")
        f.write(f"- **Execution Timestamp:** {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"- **Environment:** Windows / Python 3.14 / PyTorch 2.13 CPU / FastAPI / SQLite\n")
        f.write(f"- **Total Suites:** {total}\n")
        f.write(f"- **Suites Passed:** {passed_count}\n")
        f.write(f"- **Suites Failed:** {failed_count}\n")
        f.write(f"- **Success Rate:** {round(passed_count / total * 100, 1)}%\n\n")
        f.write("## Test Suite Breakdown\n\n")
        f.write("| # | Component / Suite | Scope | Status | Duration |\n")
        f.write("|---|---|---|---|---|\n")
        scopes = [
            "Unit / Business Rules",
            "ML Inference / Grad-CAM",
            "REST API / Auth / SQLite",
            "Atmospheric & Epidemiological",
            "Gateway / Mode B Orchestrator",
            "E2E Cross-Service Integration"
        ]
        for idx, (r, sc) in enumerate(zip(results, scopes), 1):
            status = "✅ PASS" if r["passed"] else "❌ FAIL"
            f.write(f"| {idx} | {r['suite']} | {sc} | {status} | {r['duration']}s |\n")

        f.write("\n## Detailed Execution Logs\n\n")
        for idx, r in enumerate(results, 1):
            f.write(f"### {idx}. {r['suite']}\n\n")
            f.write("```\n")
            f.write(r["stdout"][:2000] if r["stdout"] else "No stdout")
            f.write("\n```\n\n")

    print(f"\nWritten detailed test report to: {report_path}")
    sys.exit(0 if failed_count == 0 else 1)

if __name__ == "__main__":
    main()
