# Morganic Language Quick Guide

This project implements **Morganic**, a compact language built around `:` separated statements.

## Best Practice (Project Convention)

Use **huge blocks of code** in a single statement stream and separate statements with `:` (a colon), rather than writing each statement on its own newline.

- Prefer: `[x]=^3^:[y]=^4^:1(|`x+`y|)`
- Avoid relying on line breaks for statement boundaries.

## Basic Syntax

### 1) Statement separation

Top-level statements are split by `:`.

```text
[a]=^10^:[b]=^20^:1(|`a+`b|)
```

### 2) Variables and assignment

- Assign with `[name]=...`
- Read with `` `name `` or `[name]` depending on context

```text
[value]=^42^
```

Typed integer assignment is also supported:

```text
[a]=i^4^:[b]=i8^15^:[c]=i32^47373^
```

Sized integers currently support: `i2`, `i4`, `i8`, `i16`, `i32`, `i64`, `i128`, `i256`, `i512`.

### 3) Boolean values

Use `/` for true and `\` for false.

```text
[flag]=b/:[other]=b\:1([flag]):1([other])
```
### 4) String values

Prefix with `£`.

```text
[msg]=£hello world:1([msg])
```

### 5) Arithmetic

Use `| ... |` (or `{ ... }`) for arithmetic expressions.

```text
1(|3+4|)
```

You can also enter a plain arithmetic expression directly:

```text
|3+4|
```

That directly returns:

```text
7
```

### 6) Printing

`1(...)` prints values.

```text
[a]=^3^:[b]=^4^:1(|`a+`b|)
```

### 7) Control blocks

- `2(condition){...}` for conditional execution
- `3(condition){...}` for while loops
- `4(start,end){...}` for range loops

Range loops accept plain integer bounds too:

```text
4(0,5){1(£hi):1(£again)}
```
### 8) Comments

- `% ...` for single-line comments
- `%% ... %` for block comments

## REPL behavior

- Input is executed directly (it is **not echoed back** as a separate output line).
- If supported by the terminal environment (`prompt_toolkit` available), syntax coloring is shown while typing.
- Direct arithmetic input like `|3+4|` prints the computed result.
