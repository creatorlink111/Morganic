use std::fs;
use std::io::{self, Write};

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
        "&£" => "ProcessedString".to_string(),
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
    let normalized = raw.trim().replace("Â£", "£");
    match normalized.to_lowercase().as_str() {
        "bool" | "boolean" => "b".to_string(),
        "int" | "integer" => "i".to_string(),
        "float" => "f".to_string(),
        "str" | "string" | "s" => "£".to_string(),
        "matrix" => "m".to_string(),
        "£" => "£".to_string(),
        "&£" => "&£".to_string(),
        other => other.to_string(),
    }
}

fn is_allowed_list_element_type(type_code: &str) -> bool {
    let normalized = canonical_primitive_type(type_code);
    if matches!(normalized.as_str(), "£" | "&£" | "b" | "f" | "c" | "m") || is_integer_type(&normalized) {
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

fn find_matching_delimiter(text: &str, start: usize, open_ch: u8, close_ch: u8) -> Result<usize, MorganicError> {
    let bytes = text.as_bytes();
    if bytes.get(start) != Some(&open_ch) {
        return Err(MorganicError::new("Bad processed-string injection delimiter."));
    }
    if open_ch == close_ch {
        for idx in start + 1..bytes.len() {
            if bytes[idx] == close_ch {
                return Ok(idx);
            }
        }
        return Err(MorganicError::new("Unterminated processed-string injection."));
    }
    let mut depth = 0i32;
    for idx in start..bytes.len() {
        if bytes[idx] == open_ch {
            depth += 1;
        } else if bytes[idx] == close_ch {
            depth -= 1;
            if depth == 0 {
                return Ok(idx);
            }
        }
    }
    Err(MorganicError::new("Unterminated processed-string injection."))
}

fn consume_processed_injection(raw: &str) -> Result<(String, usize), MorganicError> {
    if raw.is_empty() {
        return Err(MorganicError::new("Processed string injection is missing an expression after $$."));
    }

    fn consume_atom(segment: &str) -> Result<usize, MorganicError> {
        if segment.starts_with('[') {
            return Ok(find_matching_delimiter(segment, 0, b'[', b']')? + 1);
        }
        if segment.starts_with("\"[") {
            return Ok(find_matching_delimiter(segment, 1, b'[', b']')? + 1);
        }
        if segment.starts_with('|') {
            return Ok(find_matching_delimiter(segment, 0, b'|', b'|')? + 1);
        }
        if segment.starts_with('{') {
            return Ok(find_matching_delimiter(segment, 0, b'{', b'}')? + 1);
        }
        if segment.starts_with('^') {
            return Ok(find_matching_delimiter(segment, 0, b'^', b'^')? + 1);
        }
        if segment.starts_with('i') {
            if let Some(caret_idx) = segment.find('^') {
                return Ok(find_matching_delimiter(segment, caret_idx, b'^', b'^')? + 1);
            }
        }
        if segment.starts_with("b/") || segment.starts_with("b\\") {
            return Ok(2);
        }
        if segment.starts_with('/') || segment.starts_with("\\") {
            return Ok(1);
        }
        if segment.starts_with("l(") {
            if let Some(lt_idx) = segment.find('<') {
                return Ok(find_matching_delimiter(segment, lt_idx, b'<', b'>')? + 1);
            }
        }
        if segment.starts_with("m<") {
            let first_end = find_matching_delimiter(segment, 1, b'<', b'>')?;
            if segment[first_end + 1..].starts_with('<') {
                return Ok(find_matching_delimiter(segment, first_end + 1, b'<', b'>')? + 1);
            }
            return Ok(first_end + 1);
        }
        if segment.starts_with('(') {
            return Ok(find_matching_delimiter(segment, 0, b'(', b')')? + 1);
        }
        Err(MorganicError::new("Unsupported processed-string injection; use forms like $$[name] or $$|...|."))
    }

    let mut consumed = consume_atom(raw)?;
    while let Some(ch) = raw[consumed..].chars().next() {
        if ch != '@' && ch != '~' {
            break;
        }
        consumed += 1 + consume_atom(&raw[consumed + 1..])?;
    }
    Ok((raw[..consumed].to_string(), consumed))
}

fn render_processed_string(raw: &str, state: &mut MorganicState) -> Result<String, MorganicError> {
    let mut out = String::new();
    let mut idx = 0usize;
    while idx < raw.len() {
        if let Some(marker_rel) = raw[idx..].find("$$") {
            let marker = idx + marker_rel;
            out.push_str(&raw[idx..marker]);
            let (expr_text, consumed) = consume_processed_injection(&raw[marker + 2..])?;
            let (value, _) = parse_value_expr(&expr_text, state)?;
            match value {
                Value::Int(v) => out.push_str(&v.to_string()),
                Value::Float(v) => out.push_str(&v.to_string()),
                Value::Bool(v) => out.push_str(if v { "true" } else { "false" }),
                Value::Str(v) => out.push_str(&v),
                Value::List(v) => out.push_str(&format!("{:?}", v)),
            }
            idx = marker + 2 + consumed;
        } else {
            out.push_str(&raw[idx..]);
            break;
        }
    }
    Ok(out)
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

    if let Some(s) = expr.strip_prefix("&£") {
        return Ok((Value::Str(render_processed_string(s, state)?), "&£".to_string()));
    }
    if let Some(s) = expr.strip_prefix("&Â£") {
        return Ok((Value::Str(render_processed_string(s, state)?), "&£".to_string()));
    }

    if let Some(name) = expr.strip_prefix('&') {
        let ref_name = format!("&{name}");
        let v = get_var(state, &ref_name)?;
        let t = state.types.get(&ref_name).cloned().unwrap_or_else(|| infer_type_code(v));
        return Ok((v.clone(), t));
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

    if expr.starts_with('(') && expr.ends_with(')') {
        let inside = &expr[1..expr.len() - 1];
        if let Some((x_raw, y_raw)) = inside.split_once(',') {
            let x = x_raw.trim().parse::<i64>().map_err(|_| MorganicError::new("Coordinate x must be an integer."))?;
            let y = y_raw.trim().parse::<i64>().map_err(|_| MorganicError::new("Coordinate y must be an integer."))?;
            return Ok((Value::List(vec![Value::Int(x), Value::Int(y)]), "c".to_string()));
        }
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

    if let Some(s) = expr.strip_prefix("Â£") {
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

fn parse_graph_range(raw: &str, axis_name: &str) -> Result<(i64, i64), MorganicError> {
    let Some((min_raw, max_raw)) = raw.split_once('&') else {
        return Err(MorganicError::new(format!("Bad {axis_name}-axis range: {raw}")));
    };
    let axis_min = min_raw
        .trim()
        .parse::<i64>()
        .map_err(|_| MorganicError::new(format!("Bad {axis_name}-axis range: {raw}")))?;
    let axis_max = max_raw
        .trim()
        .parse::<i64>()
        .map_err(|_| MorganicError::new(format!("Bad {axis_name}-axis range: {raw}")))?;
    if axis_min >= axis_max {
        return Err(MorganicError::new(format!(
            "{axis_name}-axis min must be less than max: {axis_min}&{axis_max}"
        )));
    }
    Ok((axis_min, axis_max))
}

fn parse_graph_literal_points(payload: &str) -> Result<Option<Vec<(i64, i64)>>, MorganicError> {
    let compact: String = payload.chars().filter(|ch| !ch.is_whitespace()).collect();
    if compact.is_empty() || !compact.starts_with('(') {
        return Ok(None);
    }

    let mut rest = compact.as_str();
    let mut points = Vec::new();
    while !rest.is_empty() {
        if !rest.starts_with('(') {
            return Err(MorganicError::new(
                "Bad graph point payload; use consecutive pairs like {(0,0)(1,4)}.",
            ));
        }
        let Some(end) = rest.find(')') else {
            return Err(MorganicError::new("Bad graph coordinate pair."));
        };
        let pair = &rest[1..end];
        let Some((x_raw, y_raw)) = pair.split_once(',') else {
            return Err(MorganicError::new("Bad graph coordinate pair."));
        };
        let x = x_raw
            .trim()
            .parse::<i64>()
            .map_err(|_| MorganicError::new("Bad graph x coordinate"))?;
        let y = y_raw
            .trim()
            .parse::<i64>()
            .map_err(|_| MorganicError::new("Bad graph y coordinate"))?;
        points.push((x, y));
        rest = &rest[end + 1..];
    }
    Ok(Some(points))
}

fn render_graph(
    points: &[(i64, i64)],
    x_min: i64,
    x_max: i64,
    y_min: i64,
    y_max: i64,
    label_step: i64,
) -> Result<String, MorganicError> {
    let x_scale = 2i64;
    let left_margin = if label_step > 0 { 5usize } else { 0usize };
    let bottom_margin = if label_step > 0 { 2usize } else { 0usize };
    let plot_width = ((x_max - x_min) * x_scale + 1) as usize;
    let plot_height = (y_max - y_min + 1) as usize;
    let width = left_margin + plot_width;
    let height = plot_height + bottom_margin;
    let mut grid = vec![vec![' '; width]; height];

    let to_grid_coords = |x: i64, y: i64| -> (usize, usize) {
        (
            left_margin + ((x - x_min) * x_scale) as usize,
            (y_max - y) as usize,
        )
    };

    if x_min <= 0 && 0 <= x_max {
        let (axis_x, _) = to_grid_coords(0, 0);
        for row in grid.iter_mut().take(plot_height) {
            row[axis_x] = '│';
        }
    }
    if y_min <= 0 && 0 <= y_max {
        let (_, axis_y) = to_grid_coords(0, 0);
        for col in 0..width {
            grid[axis_y][col] = '─';
        }
    }
    if x_min <= 0 && 0 <= x_max && y_min <= 0 && 0 <= y_max {
        let (axis_x, axis_y) = to_grid_coords(0, 0);
        grid[axis_y][axis_x] = '┼';
    }

    for &(x, y) in points {
        if !(x_min <= x && x <= x_max && y_min <= y && y <= y_max) {
            return Err(MorganicError::new(format!(
                "Point ({x},{y}) is outside graph range x[{x_min},{x_max}] y[{y_min},{y_max}]."
            )));
        }
    }

    for &(x, y) in points {
        let (gx, gy) = to_grid_coords(x, y);
        grid[gy][gx] = '●';
    }

    if x_min <= 0 && 0 <= x_max && label_step == 0 {
        let (axis_x, _) = to_grid_coords(0, 0);
        if grid[0][axis_x] == ' ' {
            grid[0][axis_x] = 'y';
        } else if axis_x + 1 < width && grid[0][axis_x + 1] == ' ' {
            grid[0][axis_x + 1] = 'y';
        }
    }
    if y_min <= 0 && 0 <= y_max && label_step == 0 {
        let (_, axis_y) = to_grid_coords(0, 0);
        grid[axis_y][width - 1] = 'x';
    }

    if label_step > 0 {
        if y_min <= 0 && 0 <= y_max {
            let x_label_row = plot_height.min(height - 1);
            for x in x_min..=x_max {
                if x % label_step != 0 {
                    continue;
                }
                let (gx, _) = to_grid_coords(x, 0);
                let label: Vec<char> = x.to_string().chars().collect();
                let start = gx.saturating_sub(label.len() / 2);
                if start + label.len() <= width {
                    for (idx, ch) in label.iter().enumerate() {
                        grid[x_label_row][start + idx] = *ch;
                    }
                }
            }
        }
        if x_min <= 0 && 0 <= x_max {
            let (axis_x, _) = to_grid_coords(0, 0);
            for y in y_min..=y_max {
                if y % label_step != 0 {
                    continue;
                }
                let (_, gy) = to_grid_coords(0, y);
                let label = format!("{:>width$}", y, width = left_margin.saturating_sub(1));
                for (idx, ch) in label.chars().enumerate() {
                    if idx < axis_x {
                        grid[gy][idx] = ch;
                    }
                }
            }
        }
    }

    Ok(grid
        .into_iter()
        .map(|row| row.into_iter().collect::<String>().trim_end().to_string())
        .collect::<Vec<_>>()
        .join("\n"))
}

fn list_to_points(list: &[Value]) -> Result<Vec<(i64, i64)>, MorganicError> {
    if list.is_empty() {
        return Err(MorganicError::new("Graph requires at least one point like {(0,0)}."));
    }

    let mut points = Vec::with_capacity(list.len());
    for item in list {
        let Value::List(pair) = item else {
            return Err(MorganicError::new("Graph points must be 2D coordinate pairs."));
        };
        if pair.len() != 2 {
            return Err(MorganicError::new("Graph points must be 2D coordinate pairs."));
        }
        let x = match &pair[0] {
            Value::Int(v) => *v,
            _ => return Err(MorganicError::new("Graph coordinates must be integer pairs.")),
        };
        let y = match &pair[1] {
            Value::Int(v) => *v,
            _ => return Err(MorganicError::new("Graph coordinates must be integer pairs.")),
        };
        points.push((x, y));
    }
    Ok(points)
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
        if let Some((var_name, seq_expr)) = header.split_once(",_[") {
            if !seq_expr.ends_with(']') {
                return Err(MorganicError::new("Bad foreach loop syntax."));
            }
            let seq_name = &seq_expr[..seq_expr.len() - 1];
            let seq = get_var(state, seq_name)?.clone();
            let items = if let Value::List(v) = seq {
                v
            } else {
                return Err(MorganicError::new("List iteration requires a list variable."));
            };
            let key = format!("&{}", var_name.trim());
            let old_value = state.env.get(&key).cloned();
            let old_type = state.types.get(&key).cloned();
            for item in items {
                store_value(state, &key, item, None)?;
                execute_program(body, state)?;
            }
            if let Some(v) = old_value {
                state.env.insert(key.clone(), v);
                if let Some(t) = old_type {
                    state.types.insert(key, t);
                }
            } else {
                state.env.remove(&key);
                state.types.remove(&key);
            }
            return Ok(());
        }
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

    if stmt.starts_with('[') && stmt.contains("]$") {
        let marker = stmt.find("]$").expect("contains checked");
        let name = &stmt[1..marker];
        let target = stmt[marker + 2..].trim();
        let value = get_var(state, name)?.clone();
        let out = match target {
            "£" => Value::Str(match value {
                Value::Str(s) => s,
                Value::Int(v) => v.to_string(),
                Value::Float(v) => v.to_string(),
                Value::Bool(v) => {
                    if v { "true".to_string() } else { "false".to_string() }
                }
                Value::List(v) => format!("{:?}", v),
            }),
            "b" => Value::Bool(match value {
                Value::Bool(v) => v,
                Value::Int(v) => v != 0,
                Value::Float(v) => v != 0.0,
                Value::Str(ref s) => !s.is_empty(),
                Value::List(ref v) => !v.is_empty(),
            }),
            "f" => Value::Float(match value {
                Value::Float(v) => v,
                Value::Int(v) => v as f64,
                Value::Str(ref s) => s.parse::<f64>().map_err(|_| MorganicError::new("Cannot convert string to float."))?,
                Value::Bool(v) => {
                    if v { 1.0 } else { 0.0 }
                }
                Value::List(_) => return Err(MorganicError::new("Cannot convert list to float.")),
            }),
            t if is_integer_type(t) => Value::Int(match value {
                Value::Int(v) => v,
                Value::Float(v) => v.trunc() as i64,
                Value::Str(ref s) => s.parse::<i64>().map_err(|_| MorganicError::new("Cannot convert string to int."))?,
                Value::Bool(v) => {
                    if v { 1 } else { 0 }
                }
                Value::List(_) => return Err(MorganicError::new("Cannot convert list to int.")),
            }),
            _ => return Err(MorganicError::new(format!("Unsupported conversion target: {target}"))),
        };
        if is_integer_type(target) {
            if let Value::Int(v) = out {
                validate_integer_range(v, target)?;
                state.env.insert(name.to_string(), Value::Int(v));
            } else {
                state.env.insert(name.to_string(), out);
            }
        } else {
            state.env.insert(name.to_string(), out);
        }
        state.types.insert(name.to_string(), target.to_string());
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

    if stmt.starts_with("1(") && stmt.ends_with(')') {
        let inner = &stmt[2..stmt.len() - 1];
        let (value, _) = parse_value_expr(inner, state)?;
        print_value(&value);
        return Ok(());
    }

    if stmt.starts_with("0") && stmt.ends_with('}') && stmt.contains('{') {
        let open = stmt.find('{').expect("contains checked");
        let header = &stmt[..open];
        let payload = stmt[open + 1..stmt.len() - 1].trim();
        let mut label_step = 0i64;
        let mut x_min = -10i64;
        let mut x_max = 10i64;
        let mut y_min = -10i64;
        let mut y_max = 10i64;
        if let Some(dot_idx) = header.find('.') {
            let rest = &header[dot_idx + 1..];
            let digits: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
            if !digits.is_empty() {
                label_step = digits.parse::<i64>().unwrap_or(0);
            }
        }
        if let (Some(lp), Some(rp)) = (header.find('('), header.rfind(')')) {
            let range = &header[lp + 1..rp];
            if let Some((x_raw, y_raw)) = range.split_once(',') {
                (x_min, x_max) = parse_graph_range(x_raw.trim(), "x")?;
                (y_min, y_max) = parse_graph_range(y_raw.trim(), "y")?;
            }
        }
        let points = match parse_graph_literal_points(payload)? {
            Some(points) => points,
            None => {
                let (value, value_type) = parse_value_expr(payload, state)?;
                if value_type != "l(c)" && value_type != "m" {
                    return Err(MorganicError::new(
                        "Graph payload expression must evaluate to l(c) or m.",
                    ));
                }
                let list = if let Value::List(v) = value {
                    v
                } else {
                    return Err(MorganicError::new(
                        "Graph payload expression must evaluate to l(c) or m.",
                    ));
                };
                list_to_points(&list)?
            }
        };
        println!("{}", render_graph(&points, x_min, x_max, y_min, y_max, label_step)?);
        return Ok(());
    }

    if stmt.starts_with('[') && stmt.contains("]=;(") && stmt.ends_with(')') {
        let marker = stmt.find("]=;(").expect("contains checked");
        let name = &stmt[1..marker];
        let prompt_expr = &stmt[marker + 4..stmt.len() - 1];
        let prompt = if let Some(s) = prompt_expr.strip_prefix('£') { s.to_string() } else { prompt_expr.to_string() };
        print!("{prompt}");
        io::stdout().flush().map_err(|e| MorganicError::new(format!("Input flush failed: {e}")))?;
        let mut line = String::new();
        match io::stdin().read_line(&mut line) {
            Ok(count) => {
                if count == 0 {
                    line = "0".to_string();
                }
                if line.ends_with('\n') {
                    line.pop();
                    if line.ends_with('\r') {
                        line.pop();
                    }
                }
            }
            Err(e) => return Err(MorganicError::new(format!("Input failed: {e}"))),
        }
        store_value(state, name, Value::Str(line), Some("£".to_string()))?;
        return Ok(());
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
