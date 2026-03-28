from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SUCCESS_FIXTURES = [
    ("arithmetic", "[a]=^3^:[b]=^4^:1(|`a+`b|)", "7"),
    ("append_index", "[xs]=l(i)<^1^,^2^,^3^>:[xs]~[xs]@^2^:1([xs]@^3^)", "3"),
    ("nested_list_type", "[mylist]=l(m)<m<0,1,2><3,1,5>,m<4,2,5><5,6,3>>:1(£ok)", "ok"),
    ("pointers_bytes", "++buffer==[0x48 0x65 0x6C 0x6C 0x6F]:buffer+-0:+buffer+1:-buffer>>2:[v]=--buffer:1([v])", "108"),
]

ERROR_FIXTURES = [
    ("bad_numeric_literal", "[x]=3", "Numeric literals must be wrapped"),
    ("bad_append_target", "[x]=^1^:[x]~^2^", "typed list variable"),
]


def _run_python(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", "-m", "morganic", "-c", source],
        cwd=ROOT / "python",
        capture_output=True,
        text=True,
        check=False,
    )


def _run_rust(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cargo", "run", "--quiet", "--", "-c", source],
        cwd=ROOT / "rust",
        capture_output=True,
        text=True,
        check=False,
    )


def _run_node(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "src/cli.js", "-c", source],
        cwd=ROOT / "node",
        capture_output=True,
        text=True,
        check=False,
    )


def _normalize_output(proc: subprocess.CompletedProcess[str]) -> str:
    return proc.stdout.strip().replace("\r\n", "\n")


def _normalize_error(proc: subprocess.CompletedProcess[str]) -> str:
    raw = proc.stderr.strip() or proc.stdout.strip()
    return raw.replace("\r\n", "\n")


def test_success_fixtures_conform_across_all_runtimes() -> None:
    runtimes = {"python": _run_python, "rust": _run_rust, "node": _run_node}
    for fixture_name, source, expected_stdout in SUCCESS_FIXTURES:
        outputs: dict[str, str] = {}
        for runtime_name, runner in runtimes.items():
            proc = runner(source)
            assert proc.returncode == 0, f"{fixture_name}: {runtime_name} failed: {_normalize_error(proc)}"
            outputs[runtime_name] = _normalize_output(proc)
            assert expected_stdout in outputs[runtime_name], f"{fixture_name}: {runtime_name} output mismatch"
        assert len(set(outputs.values())) == 1, f"{fixture_name}: outputs diverged -> {outputs}"


def test_error_fixtures_conform_across_all_runtimes() -> None:
    runtimes = {"python": _run_python, "rust": _run_rust, "node": _run_node}
    for fixture_name, source, expected_message in ERROR_FIXTURES:
        failures: dict[str, str] = {}
        for runtime_name, runner in runtimes.items():
            proc = runner(source)
            assert proc.returncode != 0, f"{fixture_name}: {runtime_name} unexpectedly succeeded"
            failures[runtime_name] = _normalize_error(proc)
            assert expected_message in failures[runtime_name], (
                f"{fixture_name}: {runtime_name} missing '{expected_message}' in error: {failures[runtime_name]}"
            )
