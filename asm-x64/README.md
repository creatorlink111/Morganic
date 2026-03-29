# Morganic x64 Assembly Runtime

This directory now contains a Linux x86_64 assembly **launcher runtime** with full Morganic language parity by forwarding execution to the Python reference runtime.

Execution model:

- The assembly binary builds an argv list for:
  - `/usr/bin/env python3 -m morganic <original args...>`
- It preserves the current process environment.
- The provided `Makefile` sets `PYTHONPATH=../python` so local development uses this repository's Python runtime.

This keeps the x64 entrypoint implemented in assembly while ensuring complete feature parity and behavior consistency with the canonical interpreter.

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
PYTHONPATH=../python ./morganic-asm -c "[x]=^21^:1(|`x*2|)"

# Script file
PYTHONPATH=../python ./morganic-asm ../example_script.elemens
```
