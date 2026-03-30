# Morganic TODO

## Short term (next 1–4 weeks)

- [x] Add cross-runtime conformance tests that run the same `.elemens` fixtures against Python, Rust, and Node and compare outputs/errors.
- [x] Add automated checks for every program in `example programs/` (with canned stdin for interactive scripts) in CI.
- [x] Expand parser tests for nested expression operators (`~`, `@`) in all runtimes, including invalid forms and precedence edge-cases.
- [x] Document expression operator semantics and precedence in `README.md` (especially append side effects in value expressions).
- [x] Improve Node runtime type metadata so typed-list behavior mirrors Python/Rust more strictly.
- [x] Add friendly runtime error messages for common input mistakes (e.g., unknown unit/operator in examples and tutorials).

## Medium term (1–3 months)

- [x] Add deterministic snapshot tests for terminal graph rendering to prevent regressions.
- [x] Implement a language spec file (`SPEC.md`) that defines grammar, runtime semantics, and error behavior.
- [ ] Introduce a formatter / linter for Morganic source to normalize style and reduce syntax mistakes.
- [ ] Add a benchmark harness that runs all runtimes on the same workloads and updates `website/benchmark-data.json`.
- [ ] Build a first-party standard example suite (basic, intermediate, advanced) with expected outputs.
- [ ] Add package/version alignment checks so Python, Rust, and Node release notes stay in sync.

## Long term (3+ months)

- [ ] Design and implement module/import support for larger multi-file programs.
- [ ] Add a proper static type checker (optional mode) for typed lists, function signatures, and conversions.
- [ ] Build an LSP server (syntax highlighting, completion, diagnostics) for editor integrations.
- [ ] Define stable language versions and migration guides (e.g., Morganic 1.0 spec and compatibility policy).
- [ ] Create a playground website with in-browser execution (Node/WASM runtime) and shareable examples.
- [ ] Establish governance: roadmap, contribution guide improvements, and compatibility guarantees across runtimes.