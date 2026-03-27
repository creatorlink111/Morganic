use std::env;
use std::fs;

use morganic_rs::parser::{execute_program, try_eval_and_print_inline_expression};
use morganic_rs::state::MorganicState;

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut state = MorganicState::default();

    if args.len() <= 1 {
        eprintln!("Usage: morganic-rs '<source>' | -c '<source>' | <file.elemens>");
        std::process::exit(0);
    }

    let code = if args[1] == "-c" || args[1] == "--code" {
        args.get(2).cloned().unwrap_or_default()
    } else {
        let candidate = &args[1];
        match fs::read_to_string(candidate) {
            Ok(text) => text,
            Err(_) => candidate.clone(),
        }
    };

    match try_eval_and_print_inline_expression(&code, &state) {
        Ok(true) => {}
        Ok(false) => {
            if let Err(e) = execute_program(&code, &mut state) {
                eprintln!("Error: {e}");
                std::process::exit(1);
            }
        }
        Err(e) => {
            eprintln!("Error: {e}");
            std::process::exit(1);
        }
    }
}
