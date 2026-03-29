# Morganic x64 Assembly Runtime

This directory contains a Linux x86_64 assembly runtime launcher that executes a sibling native `morganic-rs` binary.

Execution model:

- `morganic-asm` is a pure x64 assembly entrypoint.
- It executes `./morganic-rs` directly with all original CLI args and the same environment.
- `make` builds Rust release runtime first, then assembles/links the launcher.

This removes the Python dependency from the assembly runtime path.

## Build and run

```bash
make
make run
```

## Quick checks

```bash
make check
```

## Usage examples

```bash
# Inline code
./morganic-asm -c "[x]=^21^:1(|`x*2|)"

# Script file
./morganic-asm "../example programs/program_pack_index.elemens"

# Import standard scientific constants module
./morganic-asm -c "@scicons.morgan@:[g]=[SCI_GRAVITY_MPS2]:1([g])"
```
