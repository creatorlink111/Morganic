use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Int(i64),
    Float(f64),
    Bool(bool),
    Str(String),
    List(Vec<Value>),
}

impl Value {
    pub fn type_code(&self) -> String {
        match self {
            Value::Bool(_) => "b".to_string(),
            Value::Int(_) => "i".to_string(),
            Value::Float(_) => "f".to_string(),
            Value::Str(_) => "£".to_string(),
            Value::List(_) => "l(?)".to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct FunctionDef {
    pub params: Vec<(String, String)>,
    pub body: String,
}

#[derive(Debug, Default, Clone)]
pub struct MorganicState {
    pub env: HashMap<String, Value>,
    pub types: HashMap<String, String>,
    pub functions: HashMap<String, FunctionDef>,
}
