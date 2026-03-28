from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "example programs"

STDIN_BY_EXAMPLE = {
    "input_cli_calculator.elemens": "3\n4\n+\n",
    "maze_adventure_game.elemens": "left\ncrawl\nobsidian\n",
    "cli_unit_converter.elemens": "100\ncm\nm\n",
}


def test_all_example_programs_execute_successfully() -> None:
    for example_file in sorted(EXAMPLES_DIR.glob("*.elemens")):
        proc = subprocess.run(
            ["python", "-m", "morganic", str(example_file)],
            cwd=ROOT / "python",
            input=STDIN_BY_EXAMPLE.get(example_file.name, ""),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{example_file.name} failed: {proc.stderr.strip()}"
