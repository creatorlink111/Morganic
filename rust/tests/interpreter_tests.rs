use morganic_rs::arithmetic::eval_arithmetic;
use morganic_rs::parser::execute_program;
use morganic_rs::splitter::split_statement_chunks;
use morganic_rs::state::{MorganicState, Value};

#[test]
fn assignment_and_arithmetic() {
    let mut state = MorganicState::default();
    execute_program("[a]=^3^:[b]=^4^:[c]=|`a+`b|", &mut state).expect("program should execute");
    assert_eq!(state.env.get("c"), Some(&Value::Int(7)));
    assert_eq!(state.types.get("c").map(String::as_str), Some("i"));
}

#[test]
fn splitter_tracks_line_numbers() {
    let chunks = split_statement_chunks("[a]=^1^:\n[b]=^2^");
    assert_eq!(chunks.len(), 2);
    assert_eq!(chunks[0].line, 1);
    assert_eq!(chunks[1].line, 2);
}

#[test]
fn arithmetic_variables() {
    let mut state = MorganicState::default();
    state.env.insert("a".to_string(), Value::Int(3));
    state.env.insert("b".to_string(), Value::Int(4));
    let result = eval_arithmetic("`a + `b * 2", &state).expect("arithmetic should evaluate");
    assert_eq!(result, Value::Int(11));
}

#[test]
fn append_and_index_can_be_nested_inside_expression() {
    let mut state = MorganicState::default();
    execute_program("[mylist]=l(i)<^1^,^2^,^3^>:[mylist]~[mylist]@^2^", &mut state)
        .expect("program should execute");
    assert_eq!(
        state.env.get("mylist"),
        Some(&Value::List(vec![Value::Int(1), Value::Int(2), Value::Int(3), Value::Int(3)]))
    );
}
