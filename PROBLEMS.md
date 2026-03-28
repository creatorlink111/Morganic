# Morganic Runtime Problem Report

_Date:_ 2026-03-28  
_Repo:_ `/workspace/Morganic`

## Test matrix executed

- Python runtime unit/integration tests: `cd python && python -m pytest -q`
- Node runtime tests: `cd node && npm test --silent`
- Rust runtime tests: `cd rust && cargo test`
- Program-pack smoke tests across all runtimes (all `example programs/*.elemens` + `example_script.elemens`) with `timeout 8s` guards.

---

## Confirmed problems

### 1) `%` comment stripping conflicts with modulo operator in full showcase script
- **Severity:** High
- **Runtimes affected:** Python, Rust (and likely any splitter sharing `%` single-line comment semantics)
- **Reproduction:**
  - `cd python && python -m morganic ../example_script.elemens`
  - `cd rust && cargo run --quiet -- ../example_script.elemens`
- **Observed:** execution stops at arithmetic section around `[mod]=|`a%`b|` with parse/arithmetic errors.
- **Expected:** modulo expression should evaluate as normal arithmetic.
- **Likely root cause:** `%` is also the single-line comment marker, and current tokenizer/splitter appears to treat `%` inside arithmetic pipes as comment start.

### 2) Node runtime does not support `"[var]` type-query expression used by canonical showcase
- **Severity:** High (feature parity gap)
- **Runtime affected:** Node
- **Reproduction:**
  - `cd node && node src/cli.js ../example_script.elemens`
- **Observed:** `Fatal: Unsupported value expression: "[title]`
- **Expected:** should return canonical type-name string (as Python runtime does), per repository language guide examples.

### 3) Rust runtime lacks multiple language features used in official example programs
- **Severity:** High (major feature coverage gap)
- **Runtime affected:** Rust
- **Reproduction examples:**
  - Input expression unsupported:  
    `cd rust && cargo run --quiet -- "../example programs/cli_unit_converter.elemens"`
  - Coordinate tuple literal unsupported in value expression context:  
    `cd rust && cargo run --quiet -- "../example programs/graphing_quadratic.elemens"`
  - Additional script failures in tactical grid / graph showcase / scoreboard manager.
- **Observed:** recurring `Unrecognized value expression` errors for `;(...)`, tuple coordinates like `(-5,21)`, and some loop variable/list forms.
- **Expected:** examples in `example programs/` should run across supported runtimes or be clearly marked runtime-specific.

### 4) Python runtime exits with unhandled EOF path for input-based examples in non-interactive execution
- **Severity:** Medium
- **Runtime affected:** Python
- **Reproduction:**
  - `cd python && python -m morganic "../example programs/cli_unit_converter.elemens"`
- **Observed:** `Unexpected error: EOF when reading a line` and non-zero exit.
- **Expected:** graceful language-level error or configurable default for non-interactive stdin contexts.

### 5) Cross-runtime behavior drift for input scripts (Node succeeds where Python/Rust fail)
- **Severity:** Medium
- **Runtimes affected:** Python, Rust, Node (inconsistent semantics)
- **Observed in smoke run:**
  - Node reports successful execution for interactive example scripts in non-interactive CI shell.
  - Python errors on EOF.
  - Rust rejects input expression syntax.
- **Impact:** same `.elemens` script has incompatible runtime behavior, reducing reliability of cross-runtime conformance expectations.

---

## Notes on test coverage vs runtime readiness

- Automated unit tests currently pass in all runtimes, but they do **not** cover enough of the language surface used by `example_script.elemens` and the full program pack.
- Practical conformance is significantly lower than test pass rates suggest, especially in Rust runtime and some Node/Python edge cases.

