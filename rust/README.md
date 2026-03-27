# Morganic Rust (No longer experimental)

This folder contains an **stable Rust rewrite** of the Morganic interpreter.
It is intentionally isolated from the main Python implementation so the existing Python runtime is not disrupted.

## Run

```bash
cd rust
cargo run -- -c "[a]=^3^:[b]=^4^:1(|`a+`b|)"
```

## Test

```bash
cd rust
cargo test
```

## Scope

The Rust rewrite mirrors the core language engine structure from Python:

- source splitting/comment stripping
- arithmetic evaluation
- typed value parsing and assignment
- control flow (`if`, `while`, `for-range`)
- list append and index printing
- file write statement

Some advanced Python runtime behavior may still be evolving in this experimental port.
