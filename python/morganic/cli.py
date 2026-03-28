"""Command-line interface and REPL for Morganic."""

from __future__ import annotations

import argparse
import atexit
import re
import sys
from pathlib import Path
from typing import Any

if __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    __package__ = 'morganic'

from .errors import MorganicError

RESET = "\033[0m"
COLORS = {
    "var": "\033[32m",
    "func": "\033[35m",
    "builtin": "\033[36m",
    "comment": "\033[90m",
    "string": "\033[33m",
    "plain": "\033[37m",
}


def colorize_source_line(line: str) -> str:
    """Apply simple ANSI syntax coloring for a source line."""
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


def _configure_readline_history() -> None:
    """Enable persistent REPL history when readline is available."""
    try:
        import readline

        history_path = Path.home() / ".morganic_history"
        if history_path.exists():
            readline.read_history_file(str(history_path))
        readline.set_history_length(1000)
        atexit.register(lambda: readline.write_history_file(str(history_path)))
    except Exception:
        return


def _read_repl_line(prompt: str) -> str:
    """Read REPL input line with optional prompt_toolkit highlighting support."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.lexers import Lexer
        from prompt_toolkit.styles import Style

        class MorganicLexer(Lexer):
            def lex_document(self, document: Any):
                def get_line(_lineno: int):
                    text = document.lines[_lineno]
                    if not text:
                        return [("class:plain", "")]

                    spans: list[tuple[str, str]] = []
                    patterns = [
                        (r"%%.*?%|%.*$", "class:comment"),
                        (r"£[^\n:]*", "class:string"),
                        (r"#[A-Za-z_][A-Za-z0-9_]*", "class:func"),
                        (r"\[[A-Za-z_][A-Za-z0-9_]*\]|`[A-Za-z_][A-Za-z0-9_]*|&[A-Za-z_][A-Za-z0-9_]*", "class:var"),
                        (r"\b[0-4]\(\)|\b[0-4]\(", "class:builtin"),
                    ]

                    i = 0
                    while i < len(text):
                        matched = False
                        for pattern, style_name in patterns:
                            m = re.match(pattern, text[i:])
                            if m:
                                token = m.group(0)
                                spans.append((style_name, token))
                                i += len(token)
                                matched = True
                                break
                        if not matched:
                            spans.append(("class:plain", text[i]))
                            i += 1
                    return spans

                return get_line

        style = Style.from_dict(
            {
                "plain": "ansigray",
                "comment": "ansibrightblack",
                "string": "ansiyellow",
                "func": "ansimagenta",
                "var": "ansigreen",
                "builtin": "ansicyan",
            }
        )
        session = PromptSession()
        return session.prompt(prompt, lexer=MorganicLexer(), style=style)
    except Exception:
        return input(prompt)


def _needs_more_input(source: str) -> bool:
    """Heuristic for multi-line REPL input continuation."""
    pairs = {')': '(', ']': '[', '}': '{', '>': '<'}
    openers = set(pairs.values())
    depth = {'(': 0, '[': 0, '{': 0, '<': 0}

    for ch in source:
        if ch in openers:
            depth[ch] += 1
        elif ch in pairs:
            depth[pairs[ch]] = max(0, depth[pairs[ch]] - 1)

    return any(depth.values())


def _read_repl_statement() -> str:
    """Read one logical statement, supporting multi-line entry."""
    lines: list[str] = []
    prompt = ">>> "
    while True:
        line = _read_repl_line(prompt)
        lines.append(line)
        source = "\n".join(lines)
        if not _needs_more_input(source):
            return source
        prompt = "... "


def repl() -> None:
    """Start interactive Morganic REPL."""
    from .parser import execute_program, try_eval_and_print_inline_expression
    from .state import MorganicState

    _configure_readline_history()
    state = MorganicState()
    print("Morganic REPL")
    print("Press Ctrl+C or Ctrl+D to exit.")

    while True:
        try:
            line = _read_repl_statement()
            if not line.strip():
                continue
            if try_eval_and_print_inline_expression(line, state):
                continue
            execute_program(line, state)
        except EOFError:
            print("\nExiting...")
            break
        except KeyboardInterrupt:
            print()
            continue
        except MorganicError as e:
            print(f"Error: {e}")


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for CLI modes."""
    parser = argparse.ArgumentParser(prog="morganic", description="Morganic language interpreter")
    parser.add_argument("script", nargs="?", help=".elemens source file or inline source code")
    parser.add_argument("-c", "--code", help="execute inline Morganic source")
    parser.add_argument("-i", "--interactive", action="store_true", help="start REPL after executing code/script")
    parser.add_argument("--repl", action="store_true", help="start REPL mode")
    return parser


IMPORT_PATTERN = re.compile(r"@([A-Za-z0-9_./\\-]+\.(?:morgan|elemens))@")


def _resolve_module_imports(source: str, base_dir: Path, stack: tuple[Path, ...] = ()) -> str:
    """Inline module imports using `@file.morgan@` / `@file.elemens@` syntax."""
    def replace(match: re.Match[str]) -> str:
        raw_ref = match.group(1).strip()
        target = (base_dir / raw_ref).resolve()
        if target.suffix not in {".morgan", ".elemens"}:
            raise MorganicError(f"Unsupported import file type: {raw_ref}")
        if not target.is_file():
            raise MorganicError(f"Import file not found: {raw_ref}")
        if target in stack:
            chain = " -> ".join(str(p) for p in (*stack, target))
            raise MorganicError(f"Circular module import detected: {chain}")
        nested = target.read_text(encoding="utf-8")
        return _resolve_module_imports(nested, target.parent, (*stack, target))

    return IMPORT_PATTERN.sub(replace, source)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for script execution and interactive mode."""
    from .parser import execute_program, try_eval_and_print_inline_expression
    from .state import MorganicState

    if argv is None:
        argv = sys.argv

    args = _build_arg_parser().parse_args(argv[1:])
    state = MorganicState()

    if args.repl or (args.script is None and args.code is None):
        repl()
        return 0

    code: str | None = None
    if args.code is not None:
        code = _resolve_module_imports(args.code, Path.cwd())
    elif args.script is not None:
        path = Path(args.script)
        if path.is_file():
            if path.suffix and path.suffix not in {".elemens", ".morgan"}:
                print(f"Warning: running non-.elemens/.morgan file '{path.name}'.")
            code = _resolve_module_imports(path.read_text(encoding="utf-8"), path.resolve().parent)
        else:
            code = _resolve_module_imports(args.script, Path.cwd())

    try:
        if code and not try_eval_and_print_inline_expression(code, state):
            execute_program(code, state)
        if args.interactive:
            repl()
        return 0
    except MorganicError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.path.insert(0, '.')
    raise SystemExit(main())
