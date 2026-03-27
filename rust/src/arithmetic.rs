use crate::errors::MorganicError;
use crate::state::{MorganicState, Value};

#[derive(Debug, Clone)]
enum Token {
    Num(f64),
    Op(String),
    LParen,
    RParen,
}

fn read_var(state: &MorganicState, name: &str) -> Result<f64, MorganicError> {
    match state.env.get(name) {
        Some(Value::Int(v)) => Ok(*v as f64),
        Some(Value::Float(v)) => Ok(*v),
        Some(_) => Err(MorganicError::new("Arithmetic blocks only allow numeric operands")),
        None => Err(MorganicError::new("Undefined variable in arithmetic block").with_token(name)),
    }
}

fn tokenize(expr: &str, state: &MorganicState) -> Result<Vec<Token>, MorganicError> {
    let chars: Vec<char> = expr.chars().collect();
    let mut i = 0usize;
    let mut out = Vec::new();

    while i < chars.len() {
        let ch = chars[i];
        if ch.is_whitespace() {
            i += 1;
            continue;
        }
        if ch == '(' {
            out.push(Token::LParen);
            i += 1;
            continue;
        }
        if ch == ')' {
            out.push(Token::RParen);
            i += 1;
            continue;
        }
        if ch == '`' {
            i += 1;
            let start = i;
            while i < chars.len() && (chars[i].is_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            let name: String = chars[start..i].iter().collect();
            if name.is_empty() {
                return Err(MorganicError::new("Malformed variable reference"));
            }
            out.push(Token::Num(read_var(state, &name)?));
            continue;
        }
        if ch.is_ascii_digit() || ch == '.' {
            let start = i;
            i += 1;
            while i < chars.len() && (chars[i].is_ascii_digit() || chars[i] == '.') {
                i += 1;
            }
            let raw: String = chars[start..i].iter().collect();
            let v: f64 = raw
                .parse()
                .map_err(|_| MorganicError::new("Bad arithmetic expression").with_token(raw.clone()))?;
            out.push(Token::Num(v));
            continue;
        }
        if i + 1 < chars.len() {
            let two: String = chars[i..=i + 1].iter().collect();
            if ["//"].contains(&two.as_str()) {
                out.push(Token::Op(two));
                i += 2;
                continue;
            }
        }
        if ['+', '-', '*', '/', '%'].contains(&ch) {
            out.push(Token::Op(ch.to_string()));
            i += 1;
            continue;
        }

        return Err(MorganicError::new("Bad arithmetic expression").with_token(ch.to_string()));
    }

    Ok(out)
}

struct Parser {
    tokens: Vec<Token>,
    idx: usize,
}

impl Parser {
    fn peek(&self) -> Option<&Token> {
        self.tokens.get(self.idx)
    }

    fn take(&mut self) -> Option<Token> {
        let t = self.tokens.get(self.idx).cloned();
        if t.is_some() {
            self.idx += 1;
        }
        t
    }

    fn parse_expr(&mut self) -> Result<f64, MorganicError> {
        let mut v = self.parse_term()?;
        loop {
            match self.peek() {
                Some(Token::Op(op)) if op == "+" || op == "-" => {
                    let op = if let Some(Token::Op(s)) = self.take() { s } else { unreachable!() };
                    let rhs = self.parse_term()?;
                    v = if op == "+" { v + rhs } else { v - rhs };
                }
                _ => break,
            }
        }
        Ok(v)
    }

    fn parse_term(&mut self) -> Result<f64, MorganicError> {
        let mut v = self.parse_factor()?;
        loop {
            match self.peek() {
                Some(Token::Op(op)) if ["*", "/", "//", "%"].contains(&op.as_str()) => {
                    let op = if let Some(Token::Op(s)) = self.take() { s } else { unreachable!() };
                    let rhs = self.parse_factor()?;
                    v = match op.as_str() {
                        "*" => v * rhs,
                        "/" => {
                            if rhs == 0.0 {
                                return Err(MorganicError::new("Division by zero").with_hint(
                                    "Check divisor values before using /, //, or %.",
                                ));
                            }
                            v / rhs
                        }
                        "//" => {
                            if rhs == 0.0 {
                                return Err(MorganicError::new("Division by zero").with_hint(
                                    "Check divisor values before using /, //, or %.",
                                ));
                            }
                            (v / rhs).floor()
                        }
                        _ => {
                            if rhs == 0.0 {
                                return Err(MorganicError::new("Division by zero").with_hint(
                                    "Check divisor values before using /, //, or %.",
                                ));
                            }
                            v % rhs
                        }
                    }
                }
                _ => break,
            }
        }
        Ok(v)
    }

    fn parse_factor(&mut self) -> Result<f64, MorganicError> {
        match self.take() {
            Some(Token::Num(v)) => Ok(v),
            Some(Token::Op(op)) if op == "+" || op == "-" => {
                let x = self.parse_factor()?;
                Ok(if op == "-" { -x } else { x })
            }
            Some(Token::LParen) => {
                let v = self.parse_expr()?;
                match self.take() {
                    Some(Token::RParen) => Ok(v),
                    _ => Err(MorganicError::new("Bad arithmetic expression")),
                }
            }
            _ => Err(MorganicError::new("Bad arithmetic expression")),
        }
    }
}

pub fn eval_arithmetic(expr: &str, state: &MorganicState) -> Result<Value, MorganicError> {
    let tokens = tokenize(expr, state)?;
    let mut parser = Parser { tokens, idx: 0 };
    let v = parser.parse_expr()?;
    if parser.peek().is_some() {
        return Err(MorganicError::new("Bad arithmetic expression").with_token(expr));
    }
    if v.fract() == 0.0 {
        Ok(Value::Int(v as i64))
    } else {
        Ok(Value::Float(v))
    }
}
