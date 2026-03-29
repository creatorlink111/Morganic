from __future__ import annotations

from pathlib import Path

from morganic.cli import _needs_more_input, _resolve_module_imports


def test_trailing_colon_does_not_force_multiline_repl() -> None:
    assert _needs_more_input("[a]=^1^:") is False


def test_module_import_resolution(tmp_path: Path) -> None:
    module = tmp_path / "defaults.morgan"
    module.write_text("[x]=^9^:", encoding="utf-8")
    resolved = _resolve_module_imports("@defaults.morgan@:[y]=[x]", tmp_path)
    assert "[x]=^9^:" in resolved


def test_standard_module_resolution_from_repo_root() -> None:
    nested = Path(__file__).resolve().parent
    resolved = _resolve_module_imports("@scicons.morgan@:[v]=[SCI_PI]", nested)
    assert "[SCI_PI]=^3.141592653589793^:" in resolved
