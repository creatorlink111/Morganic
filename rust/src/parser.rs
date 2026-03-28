use std::fs;

use crate::arithmetic::eval_arithmetic;
use crate::errors::MorganicError;
use crate::splitter::{split_statement_chunks, split_statements};
use crate::state::{MorganicState, PointerValue, Value};

fn is_integer_type(type_code: &str) -> bool {
    if type_code == "i" {
        return true;
    }
    if !type_code.starts_with('i') {
        return false;
    }
    matches!(
        &type_code[1..],
        "2" | "4" | "8" | "16" | "32" | "64" | "128" | "256" | "512"
    )
}

fn integer_bounds(type_code: &str) -> Option<(i128, i128)> {
    if type_code == "i" {
        return None;
    }
    if !is_integer_type(type_code) {
        return None;
    }
    let bits: u32 = type_code[1..].parse().ok()?;
    Some((-(2i128.pow(bits - 1)), (2i128.pow(bits - 1)) - 1))
}

fn validate_integer_range(value: i64, type_code: &str) -> Result<(), MorganicError> {
    if let Some((low, high)) = integer_bounds(type_code) {
        let v = value as i128;
        if v < low || v > high {
            return Err(MorganicError::new(format!(
                "Integer overflow for {type_code}: {value} out of range [{low}, {high}]."
            )));
        }
    }
    Ok(())
}

fn canonical_type_name(type_code: &str) -> String {
    match type_code {
        "b" => "Boolean".to_string(),
        "f" => "Float".to_string(),
        "i" => "Integer".to_string(),
        "£" => "String".to_string(),
        _ if is_integer_type(type_code) => format!("Integer{}", &type_code[1..]),
        _ => type_code.to_string(),
    }
}

fn get_var<'a>(state: &'a MorganicState, name: &str) -> Result<&'a Value, MorganicError> {
    state
        .env
        .get(name)
        .ok_or_else(|| MorganicError::new("Undefined variable").with_token(name).with_hint("Define it before use with [name]=..."))
}

fn infer_type_code(value: &Value) -> String {
    value.type_code()
}

fn is_numeric_literal(expr: &str) -> bool {
    expr.parse::<i64>().is_ok() || expr.parse::<f64>().is_ok()
}

fn parse_bool_token(token: &str) -> Result<bool, MorganicError> {
    match token {
        "/" => Ok(true),
        "\\" => Ok(false),
        _ => Err(MorganicError::new(format!("Expected boolean token '/' or '\\', got: {token}"))),
    }
}

fn split_top_level_csv(raw: &str) -> Vec<String> {
    let mut tokens = vec![];
    let mut buf = String::new();
    let mut p = 0i32;
    let mut b = 0i32;
    let mut c = 0i32;
    let mut a = 0i32;
    for ch in raw.chars() {
        match ch {
            '(' => p += 1,
            ')' => p = (p - 1).max(0),
            '[' => b += 1,
            ']' => b = (b - 1).max(0),
            '{' => c += 1,
            '}' => c = (c - 1).max(0),
            '<' => a += 1,
            '>' => a = (a - 1).max(0),
            ',' if p == 0 && b == 0 && c == 0 && a == 0 => {
                let part = buf.trim();
                if !part.is_empty() {
                    tokens.push(part.to_string());
                }
                buf.clear();
                continue;
            }
            _ => {}
        }
        buf.push(ch);
    }
    let tail = buf.trim();
    if !tail.is_empty() {
        tokens.push(tail.to_string());
    }
    tokens
}

fn split_top_level_operator(raw: &str, operator: char) -> Option<(String, String)> {
    let mut p = 0i32;
    let mut b = 0i32;
    let mut c = 0i32;
    let mut a = 0i32;
    for (idx, ch) in raw.char_indices() {
        match ch {
            '(' => p += 1,
            ')' => p = (p - 1).max(0),
            '[' => b += 1,
            ']' => b = (b - 1).max(0),
            '{' => c += 1,
            '}' => c = (c - 1).max(0),
            '<' => a += 1,
            '>' => a = (a - 1).max(0),
            _ => {}
        }
        if ch == operator && p == 0 && b == 0 && c == 0 && a == 0 {
            let left = raw[..idx].trim().to_string();
            let right = raw[idx + ch.len_utf8()..].trim().to_string();
            return Some((left, right));
        }
    }
    None
}

fn canonical_primitive_type(raw: &str) -> String {
    match raw.trim().to_lowercase().as_str() {
        "bool" | "boolean" => "b".to_string(),
        "int" | "integer" => "i".to_string(),
        "float" => "f".to_string(),
        "str" | "string" | "s" => "£".to_string(),
        "matrix" => "m".to_string(),
        other => other.to_string(),
    }
}

fn is_allowed_list_element_type(type_code: &str) -> bool {
    let normalized = canonical_primitive_type(type_code);
    if matches!(normalized.as_str(), "£" | "b" | "f" | "c" | "m") || is_integer_type(&normalized) {
        return true;
    }
    if normalized.starts_with("l(") && normalized.ends_with(')') {
        let inner = normalized[2..normalized.len() - 1].trim();
        return !inner.is_empty() && is_allowed_list_element_type(inner);
    }
    false
}

fn parse_pointer_address(raw: &str) -> Result<i64, MorganicError> {
    let token = raw.trim();
    if let Ok(v) = token.parse::<i64>() {
        return Ok(v);
    }
    if token.starts_with("0x") {
        return i64::from_str_radix(&token[2..], 16)
            .map_err(|_| MorganicError::new(format!("Invalid pointer address: {raw}")));
    }
    Err(MorganicError::new(format!("Invalid pointer address: {raw}")))
}

fn parse_byte_literal(raw: &str) -> Result<u8, MorganicError> {
    let token = raw.trim();
    if token.starts_with("0x") {
        return u8::from_str_radix(&token[2..], 16)
            .map_err(|_| MorganicError::new(format!("Invalid byte literal: {raw}")));
    }
    let value = token
        .parse::<u16>()
        .map_err(|_| MorganicError::new(format!("Invalid byte literal: {raw}")))?;
    if value > 255 {
        return Err(MorganicError::new(format!("Byte literal out of range 0..255: {value}")));
    }
    Ok(value as u8)
}

fn parse_value_expr(expr: &str, state: &mut MorganicState) -> Result<(Value, String), MorganicError> {
    let expr = expr.trim();

    if let Some(name) = expr.strip_prefix("--") {
        let pointer = state
            .pointers
            .get(name)
            .ok_or_else(|| MorganicError::new(format!("Undefined pointer: {name}")))?;
        let address = pointer
            .address
            .ok_or_else(|| MorganicError::new(format!("Pointer '{name}' is free and cannot be dereferenced.")))?;
        if address < 0 || address as usize >= pointer.buffer.len() {
            return Err(MorganicError::new(format!(
                "Pointer '{name}' address {address} is out of bounds."
            )));
        }
        return Ok((Value::Int(pointer.buffer[address as usize] as i64), "i8".to_string()));
    }

    if let Some(token) = expr.strip_prefix('b') {
        if token == "/" || token == "\\" {
            return Ok((Value::Bool(parse_bool_token(token)?), "b".to_string()));
        }
    }

    if expr.starts_with('i') && expr.contains('^') && expr.ends_with('^') {
        if let Some((type_code, rest)) = expr.split_once('^') {
            if is_integer_type(type_code) {
                let lit = &rest[..rest.len() - 1];
                let v: i64 = lit
                    .trim()
                    .parse()
                    .map_err(|_| MorganicError::new(format!("{type_code} requires an integer literal inside ^ ^.")))?;
                validate_integer_range(v, type_code)?;
                return Ok((Value::Int(v), type_code.to_string()));
            }
        }
    }

    if expr.starts_with('^') && expr.ends_with('^') && expr.len() >= 2 {
        let lit = &expr[1..expr.len() - 1];
        if let Ok(v) = lit.parse::<i64>() {
            return Ok((Value::Int(v), "i".to_string()));
        }
        if let Ok(v) = lit.parse::<f64>() {
            return Ok((Value::Float(v), "f".to_string()));
        }
        return Ok((Value::Str(lit.to_string()), "£".to_string()));
    }

    if expr.starts_with('[') && expr.ends_with(']') {
        let name = &expr[1..expr.len() - 1];
        if name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
            let v = get_var(state, name)?;
            let t = state.types.get(name).cloned().unwrap_or_else(|| infer_type_code(v));
            return Ok((v.clone(), t));
        }
    }

    if expr.starts_with("\"") && expr.len() > 1 {
        let rest = &expr[1..];
        if rest.starts_with('[') && rest.ends_with(']') {
            let name = &rest[1..rest.len() - 1];
            if !state.env.contains_key(name) {
                return Err(MorganicError::new("Undefined variable").with_token(name).with_hint("Define it before reading type with \"[name]."));
            }
            let t = state.types.get(name).cloned().unwrap_or_else(|| "Unknown".to_string());
            return Ok((Value::Str(canonical_type_name(&t)), "£".to_string()));
        }
    }

    if expr.starts_with('|') && expr.ends_with('|') {
        let v = eval_arithmetic(&expr[1..expr.len() - 1], state)?;
        let t = infer_type_code(&v);
        return Ok((v, t));
    }

    if let Some(name) = expr.strip_prefix('`') {
        let v = get_var(state, name)?;
        let t = state.types.get(name).cloned().unwrap_or_else(|| infer_type_code(v));
        return Ok((v.clone(), t));
    }

    if expr.starts_with("m<") && expr.ends_with('>') {
        let core = &expr[2..];
        let Some((left, right_with_gt)) = core.split_once("><") else {
            return Err(MorganicError::new("m<x...><y...> requires two coordinate vectors."));
        };
        let right = right_with_gt.strip_suffix('>').unwrap_or(right_with_gt);
        let xs: Vec<&str> = left.strip_prefix('<').unwrap_or(left).split(',').map(str::trim).filter(|s| !s.is_empty()).collect();
        let ys: Vec<&str> = right.split(',').map(str::trim).filter(|s| !s.is_empty()).collect();
        if xs.len() != ys.len() {
            return Err(MorganicError::new("m<x...><y...> requires equal x and y counts."));
        }
        let mut points = vec![];
        for (x_raw, y_raw) in xs.iter().zip(ys.iter()) {
            let x = x_raw.parse::<i64>().map_err(|_| MorganicError::new("m coordinates must be integers."))?;
            let y = y_raw.parse::<i64>().map_err(|_| MorganicError::new("m coordinates must be integers."))?;
            points.push(Value::List(vec![Value::Int(x), Value::Int(y)]));
        }
        return Ok((Value::List(points), "m".to_string()));
    }

    if expr.starts_with("l(") && expr.contains(")<") && expr.ends_with('>') {
        let close = expr.find(")<").expect("checked contains");
        let inner = expr[2..close].trim();
        let element = canonical_primitive_type(inner);
        if !is_allowed_list_element_type(&element) {
            return Err(MorganicError::new(format!("Unsupported list element type: {inner}")));
        }
        let inside = &expr[close + 2..expr.len() - 1];
        if inside.trim().is_empty() {
            return Ok((Value::List(vec![]), format!("l({element})")));
        }
        let mut values = vec![];
        for token in split_top_level_csv(inside) {
            let (v, t) = parse_value_expr(&token, state)?;
            if t != element {
                return Err(MorganicError::new(format!("Type safety violation: list expects {element}, got {t}.")));
            }
            values.push(v);
        }
        return Ok((Value::List(values), format!("l({element})")));
    }

    if expr == "/" || expr == "\\" {
        return Ok((Value::Bool(parse_bool_token(expr)?), "b".to_string()));
    }

    if let Some(s) = expr.strip_prefix('£') {
        return Ok((Value::Str(s.to_string()), "£".to_string()));
    }

    if let Some((left_raw, right_raw)) = split_top_level_operator(expr, '~') {
        let list_name = if left_raw.starts_with('[') && left_raw.ends_with(']') && left_raw.len() >= 2 {
            &left_raw[1..left_raw.len() - 1]
        } else {
            return Err(MorganicError::new("Append expression requires a list variable target like [list]~value."));
        };

        let list_type = state
            .types
            .get(list_name)
            .cloned()
            .ok_or_else(|| MorganicError::new("Append requires a typed list variable."))?;
        if !list_type.starts_with("l(") || !list_type.ends_with(')') {
            return Err(MorganicError::new("Append requires a typed list variable."));
        }
        let element_type = list_type[2..list_type.len() - 1].to_string();
        let (value, value_type) = parse_value_expr(&right_raw, state)?;
        if value_type != element_type {
            return Err(MorganicError::new("Type safety violation: append type does not match list type."));
        }
        match state.env.get_mut(list_name) {
            Some(Value::List(v)) => {
                v.push(value);
                return Ok((Value::List(v.clone()), list_type));
            }
            _ => return Err(MorganicError::new("Append requires a typed list variable.")),
        }
    }

    if let Some((left_raw, right_raw)) = split_top_level_operator(expr, '@') {
        let (seq_value, seq_type) = parse_value_expr(&left_raw, state)?;
        let list = if let Value::List(v) = seq_value {
            v
        } else {
            return Err(MorganicError::new("Index operator '@' requires a list value."));
        };
        let (idx_value, _) = parse_value_expr(&right_raw, state)?;
        let idx = if let Value::Int(i) = idx_value {
            i
        } else {
            return Err(MorganicError::new("List index must be an integer."));
        };
        if idx < 0 || idx as usize >= list.len() {
            return Err(MorganicError::new(format!("List index out of bounds: {idx} (size={}).", list.len())));
        }
        let value = list[idx as usize].clone();
        let item_type = if seq_type.starts_with("l(") && seq_type.ends_with(')') {
            seq_type[2..seq_type.len() - 1].to_string()
        } else {
            infer_type_code(&value)
        };
        return Ok((value, item_type));
    }

    if is_numeric_literal(expr) {
        return Err(MorganicError::new("Numeric literals must be wrapped with ^ ^ (example: ^3^)."));
    }

    Err(MorganicError::new(format!("Unrecognized value expression: {expr}")))
}

fn store_value(state: &mut MorganicState, name: &str, value: Value, type_code: Option<String>) -> Result<(), MorganicError> {
    let mut resolved = type_code.unwrap_or_else(|| infer_type_code(&value));
    if let Some(existing_type) = state.types.get(name).cloned() {
        if existing_type != resolved {
            if is_integer_type(&existing_type) {
                if let Value::Int(v) = value {
                    validate_integer_range(v, &existing_type)?;
                    resolved = existing_type;
                    state.env.insert(name.to_string(), Value::Int(v));
                    state.types.insert(name.to_string(), resolved);
                    return Ok(());
                }
            }
            return Err(MorganicError::new(format!(
                "Type safety violation: variable '{name}' is {existing_type}, cannot assign {resolved}."
            )));
        }
    }

    if is_integer_type(&resolved) {
        if let Value::Int(v) = value {
            validate_integer_range(v, &resolved)?;
            state.env.insert(name.to_string(), Value::Int(v));
            state.types.insert(name.to_string(), resolved);
            return Ok(());
        }
    }

    state.env.insert(name.to_string(), value);
    state.types.insert(name.to_string(), resolved);
    Ok(())
}

fn eval_condition(expr: &str, state: &mut MorganicState) -> Result<bool, MorganicError> {
    let (left_raw, right_raw) = expr
        .split_once("..")
        .ok_or_else(|| MorganicError::new("Condition must use equality operator '..'."))?;
    let (left, _) = parse_value_expr(left_raw, state)?;
    let (right, _) = parse_value_expr(right_raw, state)?;
    Ok(left == right)
}

fn parse_loop_range_operand(expr: &str, state: &mut MorganicState) -> Result<i64, MorganicError> {
    let raw = expr.trim();
    if let Ok(v) = raw.parse::<i64>() {
        return Ok(v);
    }
    let (v, _) = parse_value_expr(raw, state)?;
    match v {
        Value::Int(v) => Ok(v),
        _ => Err(MorganicError::new("For loop range bounds must be integers.")),
    }
}

fn parse_list_index(list_name: &str, index_expr: &str, state: &mut MorganicState) -> Result<Value, MorganicError> {
    let seq = get_var(state, list_name)?.clone();
    let list = if let Value::List(v) = seq {
        v
    } else {
        return Err(MorganicError::new(format!("Indexing requires a list variable, got: {list_name}")));
    };

    let idx = if let Ok(i) = index_expr.trim().parse::<i64>() {
        i
    } else {
        let (v, _) = parse_value_expr(index_expr, state)?;
        match v {
            Value::Int(i) => i,
            _ => return Err(MorganicError::new("List index must be an integer.")),
        }
    };

    if idx < 0 || idx as usize >= list.len() {
        return Err(MorganicError::new(format!("List index out of bounds: {idx} (size={}).", list.len())));
    }

    Ok(list[idx as usize].clone())
}

fn print_value(value: &Value) {
    match value {
        Value::Int(v) => println!("{v}"),
        Value::Float(v) => println!("{v}"),
        Value::Bool(v) => println!("{}", if *v { "true" } else { "false" }),
        Value::Str(v) => println!("{v}"),
        Value::List(v) => println!("{:?}", v),
    }
}

pub fn execute_statement(stmt: &str, state: &mut MorganicState) -> Result<(), MorganicError> {
    let stmt = stmt.trim();
    if stmt.is_empty() {
        return Ok(());
    }

    if stmt.starts_with("2(") && stmt.ends_with('}') && stmt.contains("){") {
        let open = stmt.find("){").expect("contains checked");
        let cond = &stmt[2..open];
        let body = &stmt[open + 2..stmt.len() - 1];
        if eval_condition(cond.trim(), state)? {
            execute_program(body, state)?;
        }
        return Ok(());
    }

    if stmt.starts_with("3(") && stmt.ends_with('}') && stmt.contains("){") {
        let open = stmt.find("){").expect("contains checked");
        let cond = &stmt[2..open];
        let body = &stmt[open + 2..stmt.len() - 1];
        let mut guard = 0usize;
        while eval_condition(cond.trim(), state)? {
            execute_program(body, state)?;
            guard += 1;
            if guard > 100_000 {
                return Err(MorganicError::new("While loop guard triggered (possible infinite loop)."));
            }
        }
        return Ok(());
    }

    if stmt.starts_with("4(") && stmt.ends_with('}') && stmt.contains("){") {
        let open = stmt.find("){").expect("contains checked");
        let header = &stmt[2..open];
        let body = &stmt[open + 2..stmt.len() - 1];
        if let Some((first, second)) = header.split_once(',') {
            let start = parse_loop_range_operand(first.trim(), state)?;
            let end = parse_loop_range_operand(second.trim(), state)?;
            for _ in start..end {
                execute_program(body, state)?;
            }
            return Ok(());
        }
    }

    if stmt.starts_with("[!") && stmt.contains("!/w](") && stmt.ends_with(')') {
        let marker = stmt.find("!/w](").expect("contains checked");
        let filename = &stmt[2..marker];
        let expr = &stmt[marker + 5..stmt.len() - 1];
        let (value, _) = parse_value_expr(expr, state)?;
        let raw = match value {
            Value::Int(v) => v.to_string(),
            Value::Float(v) => v.to_string(),
            Value::Bool(v) => {
                if v { "/".to_string() } else { "\\".to_string() }
            }
            Value::Str(v) => v,
            Value::List(v) => format!("{:?}", v),
        };
        fs::write(filename, raw).map_err(|e| MorganicError::new(format!("File write failed: {e}")))?;
        return Ok(());
    }

    if stmt.starts_with("[") && stmt.contains("]~") {
        let marker = stmt.find("]~").expect("contains checked");
        let name = &stmt[1..marker];
        let expr = &stmt[marker + 2..];
        let list_type = state.types.get(name).cloned().ok_or_else(|| MorganicError::new("Append requires a typed list variable."))?;
        if !list_type.starts_with("l(") || !list_type.ends_with(')') {
            return Err(MorganicError::new("Append requires a typed list variable."));
        }
        let element_type = &list_type[2..list_type.len() - 1];
        let (value, value_type) = parse_value_expr(expr.trim(), state)?;
        if value_type != element_type {
            return Err(MorganicError::new("Type safety violation: append type does not match list type."));
        }
        match state.env.get_mut(name) {
            Some(Value::List(v)) => v.push(value),
            _ => return Err(MorganicError::new("Append requires a typed list variable.")),
        }
        return Ok(());
    }

    if stmt.starts_with("++") && stmt.contains("==[") && stmt.ends_with(']') {
        let marker = stmt.find("==[").expect("contains checked");
        let name = &stmt[2..marker];
        let body = &stmt[marker + 3..stmt.len() - 1];
        let mut buffer = vec![];
        if !body.trim().is_empty() {
            for token in body.split_whitespace() {
                buffer.push(parse_byte_literal(token)?);
            }
        }
        let address = if buffer.is_empty() { None } else { Some(0) };
        state
            .pointers
            .insert(name.to_string(), PointerValue { buffer, address });
        return Ok(());
    }

    if stmt.starts_with("++") && stmt.ends_with("==") {
        let name = &stmt[2..stmt.len() - 2];
        state.pointers.insert(
            name.to_string(),
            PointerValue {
                buffer: vec![],
                address: None,
            },
        );
        return Ok(());
    }

    if stmt.starts_with("++") {
        let name = &stmt[2..];
        state.pointers.entry(name.to_string()).or_insert(PointerValue {
            buffer: vec![],
            address: None,
        });
        return Ok(());
    }

    if let Some(marker) = stmt.find("+-") {
        let name = &stmt[..marker];
        if name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
            let pointer = state
                .pointers
                .get_mut(name)
                .ok_or_else(|| MorganicError::new(format!("Undefined pointer: {name}")))?;
            pointer.address = Some(parse_pointer_address(&stmt[marker + 2..])?);
            return Ok(());
        }
    }

    if stmt.starts_with('+') && stmt.len() > 2 {
        let rest = &stmt[1..];
        if let Some(op_pos) = rest[1..].find(['+', '-']) {
            let split = op_pos + 1;
            let name = &rest[..split];
            let op = rest.as_bytes()[split] as char;
            let delta_str = &rest[split + 1..];
            if !delta_str.is_empty() && delta_str.chars().all(|c| c.is_ascii_digit()) {
                let delta: i64 = delta_str.parse().map_err(|_| MorganicError::new("Invalid pointer delta"))?;
                let pointer = state
                    .pointers
                    .get_mut(name)
                    .ok_or_else(|| MorganicError::new(format!("Undefined pointer: {name}")))?;
                let address = pointer
                    .address
                    .ok_or_else(|| MorganicError::new(format!("Pointer '{name}' is free and cannot be shifted.")))?;
                pointer.address = Some(if op == '+' { address + delta } else { address - delta });
                return Ok(());
            }
        }
    }

    if stmt.starts_with('-') && stmt.contains(">>") {
        let marker = stmt.find(">>").expect("contains checked");
        let name = &stmt[1..marker];
        let delta: i64 = stmt[marker + 2..]
            .parse()
            .map_err(|_| MorganicError::new("Invalid pointer shift delta"))?;
        let pointer = state
            .pointers
            .get_mut(name)
            .ok_or_else(|| MorganicError::new(format!("Undefined pointer: {name}")))?;
        let address = pointer
            .address
            .ok_or_else(|| MorganicError::new(format!("Pointer '{name}' is free and cannot be shifted.")))?;
        pointer.address = Some(address + delta);
        return Ok(());
    }

    if stmt.starts_with("1([") && stmt.ends_with("])" ) {
        let name = &stmt[3..stmt.len() - 2];
        print_value(get_var(state, name)?);
        return Ok(());
    }

    if stmt.starts_with("1([") && stmt.contains("]@") && stmt.ends_with(')') {
        let marker = stmt.find("]@").expect("contains checked");
        let name = &stmt[3..marker];
        let index_expr = &stmt[marker + 2..stmt.len() - 1];
        let v = parse_list_index(name, index_expr, state)?;
        print_value(&v);
        return Ok(());
    }

    if stmt.starts_with("1(|") && stmt.ends_with("|)") {
        let expr = &stmt[3..stmt.len() - 2];
        let v = eval_arithmetic(expr, state)?;
        print_value(&v);
        return Ok(());
    }

    if stmt.starts_with("1(") && stmt.ends_with(')') {
        let inner = &stmt[2..stmt.len() - 1];
        if let Some(s) = inner.strip_prefix('£') {
            println!("{s}");
            return Ok(());
        }
    }

    if stmt.starts_with('[') && stmt.contains("]=") {
        let marker = stmt.find("]=").expect("contains checked");
        let name = &stmt[1..marker];
        let expr = &stmt[marker + 2..];
        let (value, type_code) = parse_value_expr(expr, state)?;
        store_value(state, name, value, Some(type_code))?;
        return Ok(());
    }

    Err(MorganicError::new("Unrecognized statement").with_token(stmt).with_hint(
        "Check delimiters and required forms like [x]=..., 1(...), 2(...){...}.",
    ))
}

pub fn try_eval_and_print_inline_expression(program: &str, state: &MorganicState) -> Result<bool, MorganicError> {
    let statements = split_statements(program);
    if statements.len() != 1 {
        return Ok(false);
    }
    let stmt = statements[0].trim();

    if stmt.starts_with('|') && stmt.ends_with('|') {
        let v = eval_arithmetic(&stmt[1..stmt.len() - 1], state)?;
        print_value(&v);
        return Ok(true);
    }
    if stmt.starts_with('{') && stmt.ends_with('}') {
        let v = eval_arithmetic(&stmt[1..stmt.len() - 1], state)?;
        print_value(&v);
        return Ok(true);
    }

    Ok(false)
}

pub fn execute_program(program: &str, state: &mut MorganicState) -> Result<(), MorganicError> {
    for chunk in split_statement_chunks(program) {
        if let Err(err) = execute_statement(&chunk.text, state) {
            if err.line.is_none() {
                return Err(MorganicError {
                    message: err.message,
                    line: Some(chunk.line),
                    token: err.token,
                    hint: err.hint,
                });
            }
            return Err(err);
        }
    }
    Ok(())
}
