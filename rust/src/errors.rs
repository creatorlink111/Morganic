use std::fmt::{Display, Formatter};

#[derive(Debug, Clone)]
pub struct MorganicError {
    pub message: String,
    pub line: Option<usize>,
    pub token: Option<String>,
    pub hint: Option<String>,
}

impl MorganicError {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            line: None,
            token: None,
            hint: None,
        }
    }

    pub fn with_line(mut self, line: usize) -> Self {
        self.line = Some(line);
        self
    }

    pub fn with_token(mut self, token: impl Into<String>) -> Self {
        self.token = Some(token.into());
        self
    }

    pub fn with_hint(mut self, hint: impl Into<String>) -> Self {
        self.hint = Some(hint.into());
        self
    }
}

impl Display for MorganicError {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let mut parts = vec![self.message.clone()];
        if let Some(line) = self.line {
            parts.push(format!("line={line}"));
        }
        if let Some(token) = &self.token {
            parts.push(format!("token='{token}'"));
        }
        if let Some(hint) = &self.hint {
            parts.push(format!("hint={hint}"));
        }
        write!(f, "{}", parts.join(" | "))
    }
}

impl std::error::Error for MorganicError {}
