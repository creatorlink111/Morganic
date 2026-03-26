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

### 3) String values

Prefix with `£`.

```text
[msg]=£hello world:1([msg])
```

### 4) Arithmetic

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

### 5) Printing

`1(...)` prints values.

```text
[a]=^3^:[b]=^4^:1(|`a+`b|)
```

### 6) Control blocks

- `2(condition){...}` for conditional execution
- `3(condition){...}` for while loops
- `4(start,end){...}` for range loops

### 7) Comments

- `% ...` for single-line comments
- `%% ... %` for block comments

## REPL behavior

- Input is executed directly (it is **not echoed back** as a separate output line).
- If supported by the terminal environment (`prompt_toolkit` available), syntax coloring is shown while typing.
- Direct arithmetic input like `|3+4|` prints the computed result.
