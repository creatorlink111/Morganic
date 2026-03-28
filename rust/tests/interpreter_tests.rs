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

#[test]
fn nested_index_then_append_precedence() {
    let mut state = MorganicState::default();
    execute_program("[xs]=l(i)<^4^,^5^,^6^>:[idxs]=l(i)<^0^,^1^>:[xs]~[xs]@[idxs]@^1^", &mut state)
        .expect("program should execute");
    assert_eq!(
        state.env.get("xs"),
        Some(&Value::List(vec![Value::Int(4), Value::Int(5), Value::Int(6), Value::Int(5)]))
    );
}

#[test]
fn append_requires_typed_list_target() {
    let mut state = MorganicState::default();
    let err = execute_program("[x]=^1^:[x]~^2^", &mut state).expect_err("append should fail");
    assert!(err.message.contains("typed list variable"));
}

#[test]
fn index_requires_integer_expression() {
    let mut state = MorganicState::default();
    let err = execute_program("[xs]=l(i)<^1^,^2^>:[v]=[xs]@^1.5^", &mut state).expect_err("index should fail");
    assert!(err.message.contains("integer"));
}

#[test]
fn typed_list_allows_matrix_elements() {
    let mut state = MorganicState::default();
    execute_program("[mylist]=l(m)<m<0,1,2><3,1,5>,m<4,2,5><5,6,3>>", &mut state)
        .expect("matrix list should parse");
    assert_eq!(state.types.get("mylist").map(String::as_str), Some("l(m)"));
}

#[test]
fn pointer_buffer_and_dereference_work() {
    let mut state = MorganicState::default();
    execute_program(
        "++buffer==[0x48 0x65 0x6C 0x6C 0x6F]:buffer+-0:+buffer+1:-buffer>>2:[x]=--buffer",
        &mut state,
    )
    .expect("pointer ops should execute");
    assert_eq!(state.env.get("x"), Some(&Value::Int(108)));
}
