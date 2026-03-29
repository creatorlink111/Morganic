use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use morganic_rs::parser::{execute_program, try_eval_and_print_inline_expression};
use morganic_rs::state::MorganicState;

fn project_root_from(base_dir: &Path) -> PathBuf {
    for candidate in base_dir.ancestors() {
        if candidate.join("README.md").is_file()
            && candidate.join("rust").is_dir()
            && candidate.join("python").is_dir()
        {
            return candidate.to_path_buf();
        }
    }
    base_dir.to_path_buf()
}

fn candidate_import_paths(raw_ref: &str, base_dir: &Path) -> Vec<PathBuf> {
    let trimmed = raw_ref.trim();
    let ref_path = Path::new(trimmed);
    let mut candidates = vec![base_dir.join(ref_path)];

    let is_bare = ref_path.components().count() == 1;
    if is_bare {
        let root = project_root_from(base_dir);
        candidates.push(root.join(trimmed));
        candidates.push(root.join("std").join(trimmed));
    }

    let mut out: Vec<PathBuf> = Vec::new();
    for p in candidates {
        let canonical = p.canonicalize().unwrap_or(p);
        if !out.contains(&canonical) {
            out.push(canonical);
        }
    }
    out
}

fn resolve_module_imports(
    source: &str,
    base_dir: &Path,
    stack: &mut Vec<PathBuf>,
    cache: &mut HashMap<PathBuf, String>,
) -> Result<String, String> {
    let mut out = String::with_capacity(source.len());
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

                let target = candidate_import_paths(raw_ref, base_dir)
                    .into_iter()
                    .find(|p| {
                        p.is_file()
                            && matches!(
                                p.extension().and_then(|s| s.to_str()),
                                Some("morgan") | Some("elemens")
                            )
                    })
                    .ok_or_else(|| format!("Import file not found: {raw_ref}"))?;

                if stack.contains(&target) {
                    return Err(format!("Circular module import detected: {:?}", stack));
                }

                stack.push(target.clone());
                let nested = if let Some(cached) = cache.get(&target) {
                    cached.clone()
                } else {
                    let text = fs::read_to_string(&target)
                        .map_err(|e| format!("Import read failed for {raw_ref}: {e}"))?;
                    cache.insert(target.clone(), text.clone());
                    text
                };
                let resolved = resolve_module_imports(
                    &nested,
                    target.parent().unwrap_or(base_dir),
                    stack,
                    cache,
                )?;
                stack.pop();

                out.push_str(&resolved);
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
        eprintln!("Usage: morganic-rs '<source>' | -c '<source>' | <file.elemens|file.morgan>");
        std::process::exit(0);
    }

    let mut cache = HashMap::new();
    let code_result: Result<String, String> = if args[1] == "-c" || args[1] == "--code" {
        let raw = args.get(2).cloned().unwrap_or_default();
        resolve_module_imports(
            &raw,
            &env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
            &mut Vec::new(),
            &mut cache,
        )
    } else {
        let candidate = &args[1];
        match fs::read_to_string(candidate) {
            Ok(text) => {
                let base = Path::new(candidate)
                    .canonicalize()
                    .ok()
                    .and_then(|p| p.parent().map(Path::to_path_buf))
                    .unwrap_or_else(|| PathBuf::from("."));
                resolve_module_imports(&text, &base, &mut Vec::new(), &mut cache)
            }
            Err(_) => resolve_module_imports(
                candidate,
                &env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
                &mut Vec::new(),
                &mut cache,
            ),
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
