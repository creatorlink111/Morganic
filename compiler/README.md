# Morganic Compiler

This folder contains a standalone Morganic compiler driver.

It compiles a `.elemens` (or `.morgan`) source file into a native executable by generating a temporary Rust project that embeds the source and links to the Rust Morganic runtime.

## Build

```bash
cd compiler
cargo build --release
```

## Compile a program

```bash
cd compiler
cargo run -- ../example\ programs/graphing_quadratic.elemens -o ../graphing_quadratic
```

Then run the produced binary:

```bash
../graphing_quadratic
```

## Notes

- The produced executable is standalone and does not require Python or Node.
- A Rust toolchain is required on the machine that runs the compiler.
- The temporary build workspace is cleaned up automatically after successful compilation.
