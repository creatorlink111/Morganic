# Morganic Language

Morganic is a compact, statement-oriented toy language that uses symbolic syntax and `:` as its primary statement separator.

This repository provides:
- A Morganic parser/interpreter.
- A REPL (`python -m morganic`).
- File and inline execution support.

---

## Installation / Running

From the repository root:

```bash
python -m morganic
```

Run inline code:

```bash
python -m morganic -c "[a]=^3^:[b]=^4^:1(|`a+`b|)"
```

Run a source file:

```bash
python -m morganic script.elemens
```

---

## Core Syntax

## 1) Statements

Top-level statements are separated by `:`.

```text
[a]=^10^:[b]=^20^:1(|`a+`b|)
```

Line breaks are allowed, but `:` is what actually splits statements.

## 2) Variables

- Assign: `[name]=...`
- Read as a value expression: `[name]` or `` `name `` (context-dependent)

```text
[value]=^42^
1([value])
```

## 3) Numeric literals

Numeric literals must be wrapped in `^...^`.

```text
[n]=^123^
[x]=^3.14^
```

Using raw numeric tokens without `^ ^` is rejected.

## 4) Strings

Strings are prefixed with `£`.

```text
[msg]=£hello world
1([msg])
```

## 5) Booleans

- `/` means true
- `\` means false

```text
[flag]=b/
[off]=b\
```

## 6) Arithmetic

Use `|...|` (or `{...}` in print/inline arithmetic contexts):

```text
[a]=^8^:[b]=^2^:1(|`a/`b|)
```

In REPL mode, a standalone arithmetic expression prints directly:

```text
>>> |3+4|
7
```

## 7) Printing

`1(...)` prints:

```text
1([name])
1(^42^)
1(£hello)
1(|`a+`b|)
```

---

## Types

Morganic tracks variable types and enforces type safety on reassignment.

### Built-in scalar types

- `i` (generic integer)
- sized integers: `i2`, `i4`, `i8`, `i16`, `i32`, `i64`, `i128`, `i256`, `i512`
- `f` (float)
- `b` (boolean)
- `£` (string)

### Typed integer literal assignment

```text
[a]=i8^12^
[b]=i32^500000^
```

Sized integers are range-checked.

---

## Type Conversion

Use conversion syntax:

```text
[var]$targetType
```

Examples:

```text
[txt]=£656556
[txt]$i32
1([txt])
```

```text
[n]=^12^
[n]$£
1([n])
```

Supported conversion targets include `i`, sized integer types like `i32`, `f`, `b`, and `£`.

Notes:
- Float -> integer conversion requires a whole-number float.
- String -> integer/float conversion requires numeric string content.
- String -> boolean expects `/` or `\`.
- Invalid conversions raise an error.

---

## Control Flow

## 1) If

```text
2([x]..^10^){1(£x is ten)}
```

## 2) While

```text
[i]=^0^:3([i]..^0^){1(£loop once):[i]=^1^}
```

## 3) For/range loop

```text
4(0,5){1(£hi)}
```

## 4) Iteration over string characters

```text
[s]=£abc:4(ch,[s]){1(&ch)}
```

---

## Lists

Current list literal support is for boolean lists:

```text
[flags]=l(b)</,\\,/>
```

Append boolean values with `~`:

```text
[flags]~/
[flags]~\\
```

---

## Functions

Define functions with typed parameters and call by name.

```text
#echo'i.msg'#{1(&msg)}
#echo £hello
```

---

## Input

Read input into a string variable:

```text
[name]=;(£Enter your name: )
```

---

## Comments

- Single-line comment: `% comment`
- Block comment: `%% comment block %`

---

## Common Errors and Fixes

- **`Numeric literals must be wrapped with ^ ^`**
  - Fix: use `^3^` instead of `3`.
- **`Unrecognized: ...`**
  - Usually means statement syntax is malformed.
  - Ensure statements are separated by `:`.
- **Type conversion errors**
  - Verify the variable currently holds a convertible value.
  - Use a valid target type (`i`, `i32`, `f`, `b`, `£`, etc.).
- **Integer overflow for sized integers**
  - Use a wider integer type (e.g., `i64` instead of `i8`).

---

## REPL Tips

- Start with `python -m morganic`.
- Exit with `Ctrl+C` or `Ctrl+D`.
- Inline arithmetic (`|...|`) prints immediately.
- If `prompt_toolkit` is installed, interactive syntax coloring is enabled.
