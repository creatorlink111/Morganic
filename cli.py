from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    __package__ = 'morganic'

# We keep these at the top, but if the error persists, 
# it means parser.py is importing from cli.py.
from .errors import MorganicError

RESET = "\033[0m"
COLORS = {
    "var": "\033[32m",      # green
    "func": "\033[35m",     # magenta
    "builtin": "\033[36m",  # cyan
    "comment": "\033[90m",  # grey
    "string": "\033[33m",   # yellow
    "plain": "\033[37m",    # white
}


def colorize_source_line(line: str) -> str:
    patterns = [
        (r"(%%.*?%|%.*$)", "comment"),
        (r"(£[^\n:]*)", "string"),
        (r"(#[A-Za-z_][A-Za-z0-9_]*)", "func"),
        (r"(\[[A-Za-z_][A-Za-z0-9_]*\]|`[A-Za-z_][A-Za-z0-9_]*|&[A-Za-z_][A-Za-z0-9_]*)", "var"),
        (r"(\b[0-4]\(\)|\b[0-4]\()", "builtin"),
    ]
    result = line
    for pattern, key in patterns:
        result = re.sub(pattern, lambda m: f"{COLORS[key]}{m.group(0)}{RESET}", result)
    return f"{COLORS['plain']}{result}{RESET}"


def repl() -> None:
    from .parser import execute_program
    from .state import MorganicState
    """Standard REPL for the Morganic language."""
    state = MorganicState()
    print("Morganic REPL")
    print("Press Ctrl+C or Ctrl+D to exit.")
    
    while True:
        try:
            line = input(">>> ")
            if not line.strip():
                continue
            print(colorize_source_line(line))
            execute_program(line, state)
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        except MorganicError as e:
            print(f"Error: {e}")

def main(argv: list[str] | None = None) -> int:
    from .parser import execute_program
    from .state import MorganicState
    """Main entry point handling file execution and -c flags."""
    if argv is None:
        argv = sys.argv

    # 1. No arguments: Start REPL
    if len(argv) == 1:
        repl()
        return 0

    state = MorganicState()

    # 2. Command flag: python -m morganic -c "1 + 1"
    if argv[1] == "-c":
        if len(argv) < 3:
            print('Usage: python -m morganic -c "code"')
            return 1
        try:
            execute_program(argv[2], state)
            return 0
        except MorganicError as e:
            print(f"Error: {e}")
            return 1

    # 3. File Execution or String Execution
    arg = argv[1]
    path = Path(arg)
    
    try:
        # Check if the argument is a path to an actual file
        if path.is_file():
            if path.suffix and path.suffix not in {".elemens"}:
                print(f"Warning: running non-.elemens file '{path.name}'.")
            code = path.read_text(encoding="utf-8")
        else:
            # Treat the argument itself as code (e.g., morganic "print(5)")
            code = arg
            
        execute_program(code, state)
        return 0
    except MorganicError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    # We use SystemExit to properly relay the return code to the terminal
    raise SystemExit(main())
