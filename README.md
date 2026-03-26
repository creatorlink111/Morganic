# Morganic Language

Morganic is a compact, quirky, statement-oriented toy language with symbolic syntax and `:` as its top-level statement separator, and scripting with `.elemens` script extension.

## Installation
Just download ts or clone it or smth idk
## Requirements

- Python **3.10+**
- Optional: `prompt_toolkit` for richer REPL highlighting

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e .[dev]
```

Run REPL:

```bash
python -m morganic --repl
```

Run inline code:

```bash
python -m morganic -c "[a]=^3^:[b]=^4^:1(|`a+`b|)"
```

Run source file:

```bash
python -m morganic script.elemens
```

Run and then stay interactive:

```bash
python -m morganic -c "[x]=^10^" --interactive
```

---

## Language Syntax Guide

### 1) Statement model

- Statements are split by top-level `:`.
- Newlines are allowed; they do **not** end statements by themselves.

```text
[a]=^10^:[b]=^20^:1(|`a+`b|)
```

### 2) Data types

- `i` integer
- `i2..i512` sized signed integers
- `f` float
- `b` boolean (`/` true, `\` false)
- `£` string
- `l(b)` list of booleans

### 3) Literals

- Number: `^42^`, `^3.14^`
- Typed integer: `i8^12^`
- String: `£hello`
- Boolean: `b/` or `b\`
- Bool list: `l(b)</,\,/>`

> Note: bare numeric tokens (like `3`) are invalid in value expressions; use `^3^`.

### 4) Variables

- Assignment: `[name]=<expr>`
- Read by bracket: `[name]`
- Read in arithmetic: `` `name ``

```text
[value]=^42^
1([value])
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

### 8) Functions

Define function:

```text
#echo'msg.i4'#{1(&msg)}
```

Call function:

```text
#echo £hello
```

### 9) Input

```text
[name]=;(£Enter your name: )
```

### 10) Comments

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
