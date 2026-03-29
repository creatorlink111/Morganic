# Morganic Language Specification

Version: 1.0 (repository baseline)

This document defines the language-level behavior shared across the Morganic runtimes (`python/`, `node/`, `rust/`). Where an implementation diverges, this document describes the intended behavior.

## 1. Program model

- A Morganic program is a sequence of statements.
- Top-level statement separator is `:`.
- Newlines are whitespace by default and do not terminate statements on their own.
- Blocks use `{ ... }` and may contain nested statements.

### 1.1 Comment forms

- Single-line comment: `% ...`
- Delimited comment: `%% ... %`

Comments are ignored by parsing and execution.

## 2. Lexical forms

### 2.1 Identifiers

- Variable identifier: `[name]`
- Method/function identifier: `#name`
- Reference/lookup in arithmetic and deref contexts: `` `name `` and `&name`

Identifier grammar:

- `name := [A-Za-z_][A-Za-z0-9_]*`

### 2.2 Literal forms

- Numeric literal: `^...^` (integer or float payload)
- String-like text literal: `£...` (up to statement/field delimiter context)
- Booleans are represented via typed values in runtime state (`/` for true, `\` for false, printed as `true/false` in diagnostics where applicable).

## 3. Imports and modules

### 3.1 Syntax

- Module import token: `@path_or_name.morgan@` or `@path_or_name.elemens@`

### 3.2 Semantics

- Import expansion is textual (inlined source) before execution.
- Relative import resolution starts from the current script/statement base directory.
- Bare single-part module names (e.g. `@scicons.morgan@`) additionally resolve against:
  1. repository root
  2. `repo_root/std/`
- Circular imports are an error.
- Unsupported extension imports are an error.

## 4. Statements

### 4.1 Assignment

- Form: `[name]=<expr>`
- Stores evaluated expression into variable `name`.

### 4.2 Output

- Form: `1(<expr>)`
- Evaluates expression and prints its display value.

### 4.3 Input

- Form: `[name]=;(£Enter your name):`
- Reads a line from stdin and stores it in `[name]`.

### 4.4 Conditionals

- If: `2(<cond>){ <statements> }`
- Else-if: `2?(<cond>){ <statements> }` (unimplemented as of 1.0.1)
- Else: `2!{ <statements> }` (unimplemented as of 1.0.1)

Evaluation is ordered: first true branch executes; else branch executes if no condition matched.

### 4.5 Loops

- While-like: `3(<cond>){ <statements> }`
- Foreach/range variants are runtime-supported; forms are implementation-defined but should preserve parser conformance from existing tests.

### 4.6 Type and utility built-ins

- `4(...)` family performs type/runtime utility operations as implemented by runtime parsers.

## 5. Expressions

Expressions may appear in assignment RHS, print arguments, and control-flow conditions.

### 5.1 Variable read

- `[name]` returns current variable value.

### 5.2 Arithmetic block

- Form: `| ... |`
- Inside the block, variable injection uses backtick references, e.g. ``|`a + `b * 2|``.
- Supported operators: `+ - * / %` and parentheses.
- Unknown variable or unsupported syntax is an error.

### 5.3 Direct dereference tokens

- `` `name `` and `&name` are accepted token classes in parser/REPL highlighting and runtime expression support according to implementation context.

## 6. Types

The language supports typed values and explicit type annotations/conversions in core runtime logic.

Documented primitive families include:

- Signed integers: `i`, `i2` ... `i512`
- Unsigned integers: `u`, `u2` ... `u512`
- Floating point: `f`
- Text/string: `s`
- Boolean: `b`
- List: `l(<type>)`
- Matrix: `m`

Exact cast syntax and edge behavior are parser/runtime-defined and should stay compatible with README examples and test corpus.

## 7. Enums

Morganic supports enum declarations and assignment syntax (quoted style), including repository-defined constants such as in `scicons.morgan`.

Canonical module constant style:

**Removed this syntax example due to AI Hallucinatons. See README for proper syntax example.**

## 8. Error model

Runtime/parser errors are surfaced in structured form with:

- message text
- optional line number
- optional offending token
- optional hint

Example shape:

- `Error: Unrecognized statement | line=1 | token='??bad' | hint=Check delimiters and required forms like [x]=..., 1(...), 2(...){...}.`

### 8.1 Common error categories

- Unrecognized statement
- Undefined variable
- Import file not found
- Circular module import
- Arithmetic syntax errors
- Division-by-zero/runtime math errors

## 9. REPL behavior

- REPL reads one logical statement with multiline continuation when bracket-like delimiters are unbalanced.
- Before execution, import tokens are resolved using the same import semantics as file/inline execution.
- REPL attempts inline expression evaluation first, then full statement execution.

## 10. Conformance guidance

- `python/tests/test_cross_runtime_conformance.py` is the authoritative executable conformance indicator.
- New syntax or semantics should be added alongside cross-runtime tests and README updates.

## 11. Non-goals

- This spec does not define bytecode/IR formats.
- This spec does not prescribe optimizer behavior.
- This spec does not require exact matching of internal error class names across runtimes, only equivalent user-visible behavior.
