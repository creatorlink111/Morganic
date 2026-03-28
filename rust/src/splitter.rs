#[derive(Debug, Clone, PartialEq)]
pub struct StatementChunk {
    pub text: String,
    pub line: usize,
}

pub fn strip_comments(source: &str) -> String {
    let chars: Vec<char> = source.chars().collect();
    let mut out = String::new();
    let mut i = 0usize;
    let mut in_arithmetic = false;

    while i < chars.len() {
        if chars[i] == '|' {
            in_arithmetic = !in_arithmetic;
            out.push(chars[i]);
            i += 1;
            continue;
        }

        if chars[i] == '%' && !in_arithmetic {
            let next = chars.get(i + 1).copied().unwrap_or('\0');
            if next == '%' {
                i += 2;
                while i < chars.len() && chars[i] != '%' {
                    i += 1;
                }
                if i < chars.len() {
                    i += 1;
                }
                continue;
            }
            i += 1;
            while i < chars.len() && chars[i] != '\n' {
                i += 1;
            }
            continue;
        }

        out.push(chars[i]);
        i += 1;
    }

    out
}

pub fn split_statement_chunks(source: &str) -> Vec<StatementChunk> {
    let source = strip_comments(source);
    let mut out = Vec::new();
    let mut buf = String::new();

    let mut paren = 0i32;
    let mut bracket = 0i32;
    let mut brace = 0i32;
    let mut angle = 0i32;

    let mut line = 1usize;
    let mut stmt_line = 1usize;

    for ch in source.chars() {
        if ch == '\n' {
            line += 1;
        }

        if "([{<".contains(ch) {
            if buf.is_empty() {
                stmt_line = line;
            }
            match ch {
                '(' => paren += 1,
                '[' => bracket += 1,
                '{' => brace += 1,
                '<' => angle += 1,
                _ => {}
            }
            buf.push(ch);
            continue;
        }

        if ")]}>".contains(ch) {
            if buf.is_empty() {
                stmt_line = line;
            }
            match ch {
                ')' => paren = (paren - 1).max(0),
                ']' => bracket = (bracket - 1).max(0),
                '}' => brace = (brace - 1).max(0),
                '>' => angle = (angle - 1).max(0),
                _ => {}
            }
            buf.push(ch);
            continue;
        }

        if ch == ':' && paren == 0 && bracket == 0 && brace == 0 && angle == 0 {
            let part = buf.trim();
            if !part.is_empty() {
                out.push(StatementChunk {
                    text: part.to_string(),
                    line: stmt_line,
                });
            }
            buf.clear();
            stmt_line = line;
            continue;
        }

        if buf.is_empty() {
            stmt_line = line;
        }
        buf.push(ch);
    }

    let tail = buf.trim();
    if !tail.is_empty() {
        out.push(StatementChunk {
            text: tail.to_string(),
            line: stmt_line,
        });
    }

    out
}

pub fn split_statements(source: &str) -> Vec<String> {
    split_statement_chunks(source)
        .into_iter()
        .map(|c| c.text)
        .collect()
}
