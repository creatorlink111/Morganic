# Morganic Language

Morganic is a compact, quirky, statement-oriented toy language with symbolic syntax and `:` as its top-level statement separator, and scripting with `.elemens` script extension.

## Installation
Clone this repository and pick the runtime you want:

- `python/` → primary Python interpreter (slow, but currently the primary model)
- `rust/` → significantly faster Rust interpreter (about 30x faster)

## Requirements

- Python **3.10+** for the Python runtime
- Rust toolchain (`cargo`) for the Rust runtime
- Optional (Python): `prompt_toolkit` for richer REPL highlighting

## Python setup (`python/`)
```bash
cd python
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e .[dev]
```

Run REPL:

```bash
cd python
python -m morganic --repl
```

Run inline code:

```bash
cd python
python -m morganic -c "[a]=^3^:[b]=^4^:1(|`a+`b|)"
```

Run source file:

```bash
cd python
python -m morganic ../example_script.elemens
```

Run and then stay interactive:

```bash
cd python
python -m morganic -c "[x]=^10^" --interactive
```

## Rust setup (`rust/`)
```bash
cd rust
cargo run -- -c "[a]=^3^:[b]=^4^:1(|`a+`b|)"
cargo test
```

---

## Language Syntax Guide

### 1) Statement model

- Statements are split by top-level `:`.
- Newlines are allowed; they do **not** necessarily end statements by themselves.

```text
[a]=^10^:[b]=^20^:1(|`a+`b|)
```

### 2) Data types

- `i` integer
- `i2..i512` sized signed integers
- `f` float
- `b` boolean (`/` true, `\` false)
- `£` string
- `l(type)` typed list (`l(i4)`, `l(f)`, `l(£)`, etc.)
- `l(c)` coordinate list (list of `(x,y)` integer pairs)
- `m` matrix-style coordinate set from parallel x/y lists

### 3) Literals

- Number: `^42^`, `^3.14^`
- Typed integer: `i8^12^`
- String: `£hello`
- Boolean: `b/` or `b\`
- Typed list: `l(i4)<i4^1^,i4^2^>` or `l(£)<£a,£b>`
- Coord list: `l(c)<(0,0),(1,1),(2,2)>`
- Matrix coords: `m<0,1,2><0,1,2>`

> Note: bare numeric tokens (like `3`) are invalid in value expressions; use `^3^`.

### 4) Variables

- Assignment: `[name]=<expr>`
- Read by bracket: `[name]`
- Read in arithmetic: `` `name ``
- Read variable type: `"[name]` (returns canonical type name as string)

```text
[value]=^42^
1([value])
[kind]="[value]
1([kind])
```

### 5) Operators

#### Arithmetic (inside `|...|` or `{...}`)

- `+`, `-`, `*`, `/`, `//`, `%`
- Unary `+` and `-`
- Parentheses allowed

```text
[a]=^8^:[b]=^2^:1(|(`a+2)*`b|)
```

#### Comparison/condition

- Equality only: `..`

```text
2([x]..^10^){1(£x is ten)}
```

### 6) Statements and control flow

#### Print

```text
1([name])
1(^42^)
1(£hello)
1(|`a+`b|)
```

#### Console graphing (new unique point)

Use `0(...)` to render a graph directly in the terminal with axes and marked points.

Syntax:

```text
0(xMin&xMax,yMin&yMax){(x1,y1)(x2,y2)...}
0{xOrPairPayload}
```

Example:

```text
0(-10&10,-20&20){(0,0)(1,4)(5,5)}
[pairs]=m<0,1,5><0,4,5>:0(-10&10,-20&20){[pairs]}
[coords]=l(c)<(0,0),(1,4),(5,5)>:0{[coords]}
```

Optional numeric axis labels:

```text
0.1(-10&10,-10&10){(0,0)(1,1)}   # label each unit
0.2(-10&10,-10&10){(0,0)(2,2)}   # label every 2 units
```

- X-axis range is `-10..10` in this example.
- Y-axis range is `-20..20` in this example.
- You can customize both ranges as needed, or omit them to default to `-10..10` for both axes.
- Graph payload may be explicit pairs, or an expression that evaluates to `m` / `l(c)`.
- Points are plotted as markers only (no dotted connector lines).

### 6.5) Enums (quoted syntax)

Define an enum using quoted type name and `¬`-separated members:

```text
"direction"=north¬south¬east¬west
```

Assign enum values by calling that quoted type like a literal constructor:

```text
[mydir]="direction"north
```

#### If

```text
2([x]..^10^){1(£x is ten)}
```

#### While

```text
[i]=^0^:3([i]..^0^){1(£loop once):[i]=^1^}
```

#### For range

```text
4(0,3){1(£tick)}
```

#### For each character in string

```text
[s]=£abc:4(ch,[s]){1(&ch)}
```

#### For each item in list variable

```text
[flags]=l(b)</,\>:4(v,_[flags]){1(&v)}
```

### 7) Type conversion

```text
[txt]=£656556:[txt]$i32
[n]=^12^:[n]$£
```

Supported targets: integer types, `f`, `b`, `£`.

Special conversion from coordinate-list to matrix coords:

```text
[data]=l(c)<(0,0),(1,1),(2,2)>:[data]£m
```

### 8) Functions

Define function:

```text
#echo'msg.i4'#{1(&msg)}
```

Call function:

```text
#echo £hello
```

### 9) Classes and constructor expressions

Define a class:

```text
*Point{[x]=^1^:[y]=^2^}
```

Create an instance (star constructor form):

```text
[p]=*Point{x=^5^}
```

Create an instance (dot constructor form):

```text
[q]=.Point.x:^9^,y:^4^
```

#### Constructor logic, step-by-step

When Morganic evaluates `*Class{...}` or `.Class....`, constructor processing follows this exact order:

1. **Resolve class definition**
   - The class must already exist in `state.classes` (from a prior `*Class{...}` declaration).
2. **Seed defaults**
   - A fresh instance map is created with `__class__` and every declared field default.
3. **Parse payload tokens**
   - Constructor payload is split on top-level commas only, so nested values keep their commas.
4. **Accept `=` or `:` assignment forms**
   - Each token may be `field=value` or `field:value`.
5. **Evaluate each override as a normal value expression**
   - Overrides support any valid value expression (`^...^`, typed ints, lists, arithmetic pipes, etc.).
6. **Enforce field type safety**
   - If a default field has a known type, override type must match exactly.
7. **Return typed object**
   - Resulting type code is `.<ClassName>.` (example: `.Point.`), and the value is a dict-like object.

#### Constructor behavior notes

- Missing override fields keep their class defaults.
- Override order matters only when assigning the same field multiple times (last write wins).
- Unknown fields are currently accepted and become new instance keys.
- Type errors are reported per field, e.g. constructor expected `i16` but got `£`.

### 10) Input

```text
[name]=;(£Enter your name: )
```

### 11) Comments

- Single line: `% comment`
- Block: `%% comment block %`

---

## Multi-step Script Examples

### Example: arithmetic pipeline

```text
[a]=^5^:
[b]=^7^:
[sum]=|`a+`b|:
[scaled]=|`sum*2|:
1(£result=):
1([scaled])
```

### Example: typed conversion flow

```text
[raw]=£42:
[raw]$i32:
[val]=|`raw+8|:
[val]$£:
1(£converted=):
1([val])
```

### Example: branch + loop

```text
[count]=^0^:
2([count]..^0^){1(£starting)}:
3([count]..^0^){
  [count]=^1^:
  1(£done)
}
```

---

## Testing

Run tests:

```bash
pytest
```

Current tests cover:

- arithmetic evaluation
- parser assignment/expression flow
- splitter line tracking
- error surfaces (invalid syntax, division by zero)

---

## Error handling

Errors now include structured context when available:

- line number (`line=...`)
- offending token (`token='...'`)
- syntax hint (`hint=...`)

Example:

```text
Error: Unrecognized statement | line=2 | token='??bad' | hint=Check delimiters and required forms like [x]=..., 1(...), 2(...){...}.
```

---

## Project layout

- `parser.py` — statement parsing and execution
- `arithmetic.py` — safe arithmetic evaluator
- `splitter.py` — comment stripping and statement splitting
- `cli.py` — REPL and command-line entrypoint
- `state.py` — runtime state model
- `errors.py` — structured language errors


## High-Speed Rust Rewrite

A separate, non-disruptive Rust rewrite now lives in `rust/`.

- Keeps the main Python interpreter untouched.
- Provides a full lower-runtime Rust interpreter and tests.
- Run with `cd rust && cargo run -- -c "[a]=^3^:[b]=^4^:1(|`a+`b|)"`.
