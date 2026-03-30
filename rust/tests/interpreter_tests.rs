use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use morganic_rs::arithmetic::eval_arithmetic;
use morganic_rs::parser::execute_program;
use morganic_rs::splitter::split_statement_chunks;
use morganic_rs::state::{MorganicState, Value};

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("workspace root")
        .to_path_buf()
}

fn graph_snapshot_dir() -> PathBuf {
    project_root().join("graph_snapshots")
}

fn normalize(text: &str) -> String {
    text.replace("\r\n", "\n")
        .trim_start_matches('\u{feff}')
        .trim_end_matches('\n')
        .to_string()
}

fn read_fixture(path: &Path) -> String {
    normalize(&fs::read_to_string(path).expect("fixture should be readable"))
}

fn graph_case_names() -> Vec<String> {
    let mut names = fs::read_dir(graph_snapshot_dir())
        .expect("graph snapshot dir should exist")
        .filter_map(|entry| {
            let path = entry.ok()?.path();
            if path.extension()?.to_str()? != "elemens" {
                return None;
            }
            Some(path.file_stem()?.to_str()?.to_string())
        })
        .collect::<Vec<_>>();
    names.sort();
    names
}

fn run_cli(source: &str) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_morganic-rs"))
        .args(["-c", source])
        .output()
        .expect("morganic-rs binary should run")
}

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

#[test]
fn modulo_inside_arithmetic_is_not_treated_as_comment() {
    let mut state = MorganicState::default();
    execute_program("[a]=^7^:[b]=^3^:[m]=|`a%`b|", &mut state).expect("program should execute");
    assert_eq!(state.env.get("m"), Some(&Value::Int(1)));
}

#[test]
fn coord_literal_parses_in_typed_coord_list() {
    let mut state = MorganicState::default();
    execute_program("[pts]=l(c)<(0,1),(2,3)>", &mut state).expect("coord list should parse");
    assert_eq!(state.types.get("pts").map(String::as_str), Some("l(c)"));
}

#[test]
fn foreach_loop_binds_reference_variable() {
    let mut state = MorganicState::default();
    execute_program(
        "[items]=l(i)<^1^,^2^,^3^>:[sum]=^0^:4(v,_[items]){[cur]=&v:[sum]=|`sum+`cur|}",
        &mut state,
    )
    .expect("foreach loop should execute");
    assert_eq!(state.env.get("sum"), Some(&Value::Int(6)));
}

#[test]
fn graph_output_snapshots_stay_stable() {
    for case in graph_case_names() {
        let source_path = graph_snapshot_dir().join(format!("{case}.elemens"));
        let expected_path = graph_snapshot_dir().join(format!("{case}.out.txt"));
        if !expected_path.exists() {
            continue;
        }
        let source = read_fixture(&source_path);
        let expected = read_fixture(&expected_path);
        let output = run_cli(&source);
        assert!(output.status.success(), "{case}: {}", String::from_utf8_lossy(&output.stderr));
        assert_eq!(normalize(&String::from_utf8_lossy(&output.stdout)), expected, "{case}");
    }
}

#[test]
fn graph_error_snapshots_stay_stable() {
    for case in graph_case_names() {
        let source_path = graph_snapshot_dir().join(format!("{case}.elemens"));
        let expected_path = graph_snapshot_dir().join(format!("{case}.err.txt"));
        if !expected_path.exists() {
            continue;
        }
        let source = read_fixture(&source_path);
        let expected = read_fixture(&expected_path);
        let output = run_cli(&source);
        assert!(!output.status.success(), "{case}: expected failure");
        let stderr = normalize(&String::from_utf8_lossy(&output.stderr));
        assert!(stderr.contains(&expected), "{case}: {stderr}");
    }
}

#[test]
fn processed_string_injects_variables_and_expressions() {
    let mut state = MorganicState::default();
    execute_program("[name]=£Morgan:[msg]=&£hello $$[name], $$|10+8| total", &mut state)
        .expect("processed string should execute");
    assert_eq!(state.env.get("msg"), Some(&Value::Str("hello Morgan, 18 total".to_string())));
    assert_eq!(state.types.get("msg").map(String::as_str), Some("&£"));
}

#[test]
fn processed_string_type_query_returns_canonical_name() {
    let mut state = MorganicState::default();
    execute_program("[msg]=&£value=$$|10+8|:[kind]=\"[msg]", &mut state)
        .expect("type query should execute");
    assert_eq!(state.env.get("kind"), Some(&Value::Str("ProcessedString".to_string())));
}
