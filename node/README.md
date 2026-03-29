# Morganic Node.js Runtime (Third Runtime Folder)

This folder is a full standalone JavaScript runtime for Morganic, separate from `python/` and `rust/`.

## Run

```bash
cd node
npm install
npm run start -- --repl
```

Inline script:

```bash
npm run start -- -c "[a]=^3^:[b]=^4^:1(|`a+`b|)"
```

File execution:

```bash
npm run start -- ../scicons.morgan
```

## Implemented language features

- Statement splitting and comment handling (`:`, `%`, `%%...%`)
- Typed/bare values (`^n^`, `i8^n^`, `£text`, booleans)
- Variable assignment and reads
- Arithmetic pipes (`|...|`) with variable interpolation using backticks
- Printing (`1(...)`)
- If / while / for-range / for-each
- String/list iteration
- Type conversion (`[x]$...`)
- Enum declaration and constructor-style enum values
- Function declaration/call
- Class declaration + star/dot constructors
- Input (`[x]=;(...)`)
- Console graph plotting (`0{...}` and ranged `0(...){...}`)

## Notes

This runtime is intentionally separate and non-disruptive, preserving existing Python and Rust implementations.
