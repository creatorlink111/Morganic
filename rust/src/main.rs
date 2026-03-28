use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use morganic_rs::parser::{execute_program, try_eval_and_print_inline_expression};
use morganic_rs::state::MorganicState;

fn resolve_module_imports(source: &str, base_dir: &Path, stack: &mut Vec<PathBuf>) -> Result<String, String> {
    let mut out = String::new();
    let mut i = 0usize;
    let bytes = source.as_bytes();
    while i < bytes.len() {
        if bytes[i] == b'@' {
            let mut j = i + 1;
            while j < bytes.len() && bytes[j] != b'@' && bytes[j] != b'\n' {
                j += 1;
            }
            if j < bytes.len() && bytes[j] == b'@' {
                let raw_ref = source[i + 1..j].trim();
                let looks_like_import = raw_ref.ends_with(".morgan") || raw_ref.ends_with(".elemens");
                if !looks_like_import {
                    out.push('@');
                    i += 1;
                    continue;
                }
                let target = base_dir.join(raw_ref).canonicalize().map_err(|_| format!("Import file not found: {raw_ref}"))?;
                match target.extension().and_then(|s| s.to_str()) {
                    Some("morgan") | Some("elemens") => {}
                    _ => return Err(format!("Unsupported import file type: {raw_ref}")),
                }
                if stack.contains(&target) {
                    return Err(format!("Circular module import detected: {:?}", stack));
                }
                stack.push(target.clone());
                let nested = fs::read_to_string(&target).map_err(|e| format!("Import read failed for {raw_ref}: {e}"))?;
                out.push_str(&resolve_module_imports(&nested, target.parent().unwrap_or(base_dir), stack)?);
                stack.pop();
                i = j + 1;
                continue;
            }
        }
        out.push(bytes[i] as char);
        i += 1;
    }
    Ok(out)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut state = MorganicState::default();

    if args.len() <= 1 {
        eprintln!("Usage: morganic-rs '<source>' | -c '<source>' | <file.elemens>");
        std::process::exit(0);
    }

    let code_result: Result<String, String> = if args[1] == "-c" || args[1] == "--code" {
        let raw = args.get(2).cloned().unwrap_or_default();
        resolve_module_imports(&raw, &env::current_dir().unwrap_or_else(|_| PathBuf::from(".")), &mut Vec::new())
    } else {
        let candidate = &args[1];
        match fs::read_to_string(candidate) {
            Ok(text) => {
                let base = Path::new(candidate).parent().unwrap_or_else(|| Path::new("."));
                resolve_module_imports(&text, base, &mut Vec::new())
            }
            Err(_) => Ok(candidate.clone()),
        }
    };
    let code = match code_result {
        Ok(value) => value,
        Err(msg) => {
            eprintln!("Error: {msg}");
            std::process::exit(1);
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
