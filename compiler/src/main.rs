use std::env;
use std::ffi::OsStr;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn print_usage() {
    eprintln!(
        "Usage: morganic-compiler <input.elemens> [-o output_binary]\n\n\
Compiles a Morganic source file into a standalone native executable."
    );
}

fn parse_args() -> Result<(PathBuf, PathBuf), String> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        return Err("Missing input file.".to_string());
    }

    if args[1] == "-h" || args[1] == "--help" {
        print_usage();
        std::process::exit(0);
    }

    let input = PathBuf::from(&args[1]);
    let mut output: Option<PathBuf> = None;

    let mut idx = 2;
    while idx < args.len() {
        match args[idx].as_str() {
            "-o" | "--output" => {
                if idx + 1 >= args.len() {
                    return Err("Expected output path after -o/--output.".to_string());
                }
                output = Some(PathBuf::from(&args[idx + 1]));
                idx += 2;
            }
            flag => return Err(format!("Unknown argument: {flag}")),
        }
    }

    let default_output = default_output_path(&input)?;
    Ok((input, output.unwrap_or(default_output)))
}

fn default_output_path(input: &Path) -> Result<PathBuf, String> {
    let stem = input
        .file_stem()
        .and_then(OsStr::to_str)
        .ok_or_else(|| "Unable to determine input filename stem.".to_string())?;
    let mut output = input.with_file_name(stem);
    if cfg!(windows) {
        output.set_extension("exe");
    }
    Ok(output)
}

fn escape_rust_string(raw: &str) -> String {
    let mut escaped = String::new();
    for ch in raw.chars() {
        match ch {
            '\\' => escaped.push_str("\\\\"),
            '"' => escaped.push_str("\\\""),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            _ => escaped.push(ch),
        }
    }
    escaped
}

fn unique_temp_dir() -> io::Result<PathBuf> {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|err| io::Error::new(io::ErrorKind::Other, err.to_string()))?
        .as_nanos();
    let mut dir = env::temp_dir();
    dir.push(format!("morganic-compiler-{nanos}"));
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

fn repo_root_from_manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("compiler crate should live one directory below repo root")
        .to_path_buf()
}

fn write_temp_project(temp_dir: &Path, source_program: &str, runtime_path: &Path) -> io::Result<()> {
    let src_dir = temp_dir.join("src");
    fs::create_dir_all(&src_dir)?;

    let runtime_dependency = runtime_path.to_string_lossy().replace('\\', "\\\\");

    let cargo_toml = format!(
        "[package]\nname = \"morganic_compiled_program\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\nmorganic-rs = {{ path = \"{runtime_dependency}\" }}\n"
    );
    fs::write(temp_dir.join("Cargo.toml"), cargo_toml)?;

    let escaped_source = escape_rust_string(source_program);
    let main_rs = format!(
        "use morganic_rs::{{execute_program, MorganicState}};\n\nfn main() {{\n    let program = \"{escaped_source}\";\n    let mut state = MorganicState::default();\n    if let Err(err) = execute_program(program, &mut state) {{\n        eprintln!(\"{{}}\", err);\n        std::process::exit(1);\n    }}\n}}\n"
    );
    fs::write(src_dir.join("main.rs"), main_rs)?;

    Ok(())
}

fn build_project(temp_dir: &Path) -> io::Result<PathBuf> {
    let status = Command::new("cargo")
        .arg("build")
        .arg("--release")
        .arg("--manifest-path")
        .arg(temp_dir.join("Cargo.toml"))
        .status()?;

    if !status.success() {
        return Err(io::Error::new(
            io::ErrorKind::Other,
            "cargo build failed for generated project",
        ));
    }

    let mut built_binary = temp_dir.join("target").join("release").join("morganic_compiled_program");
    if cfg!(windows) {
        built_binary.set_extension("exe");
    }

    if !built_binary.exists() {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            format!("Expected compiled binary not found at {}", built_binary.display()),
        ));
    }

    Ok(built_binary)
}

fn copy_output(binary_path: &Path, output_path: &Path) -> io::Result<()> {
    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    fs::copy(binary_path, output_path)?;
    Ok(())
}

fn main() {
    let (input_path, output_path) = match parse_args() {
        Ok(v) => v,
        Err(message) => {
            eprintln!("Error: {message}");
            print_usage();
            std::process::exit(2);
        }
    };

    let source_program = match fs::read_to_string(&input_path) {
        Ok(content) => content,
        Err(err) => {
            eprintln!("Failed to read {}: {err}", input_path.display());
            std::process::exit(1);
        }
    };

    let temp_dir = match unique_temp_dir() {
        Ok(path) => path,
        Err(err) => {
            eprintln!("Failed to create temp workspace: {err}");
            std::process::exit(1);
        }
    };

    let runtime_path = repo_root_from_manifest_dir().join("rust");
    if let Err(err) = write_temp_project(&temp_dir, &source_program, &runtime_path) {
        eprintln!("Failed to write generated compiler project: {err}");
        std::process::exit(1);
    }

    let built_binary = match build_project(&temp_dir) {
        Ok(path) => path,
        Err(err) => {
            eprintln!("Compilation failed: {err}");
            std::process::exit(1);
        }
    };

    if let Err(err) = copy_output(&built_binary, &output_path) {
        eprintln!("Failed to write output binary {}: {err}", output_path.display());
        std::process::exit(1);
    }

    if let Err(err) = fs::remove_dir_all(&temp_dir) {
        eprintln!("Warning: failed to remove temp directory {}: {err}", temp_dir.display());
    }

    println!("Compiled {} -> {}", input_path.display(), output_path.display());
}

#[cfg(test)]
mod tests {
    use super::escape_rust_string;

    #[test]
    fn escapes_control_and_quote_chars() {
        let raw = "\"a\n\\b\t";
        assert_eq!(escape_rust_string(raw), "\\\"a\\n\\\\b\\t");
    }
}
