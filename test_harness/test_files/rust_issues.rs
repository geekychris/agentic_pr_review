use std::collections::HashMap;
use std::fs;
use std::process::Command;

// ── ERROR-level: Command injection via user input ──
fn run_user_command(input: &str) -> String {
    let output = Command::new("sh")
        .arg("-c")
        .arg(input)
        .output()
        .unwrap();
    String::from_utf8_lossy(&output.stdout).to_string()
}

// ── ERROR-level: Unsafe block without justification ──
fn dangerous_operation(ptr: *const i32) -> i32 {
    unsafe {
        *ptr
    }
}

// ── ERROR-level: Hardcoded secret ──
const API_TOKEN: &str = "ghp_super_secret_token_12345";

// ── WARNING-level: Unwrap on Result — will panic on error ──
fn read_config(path: &str) -> String {
    fs::read_to_string(path).unwrap()
}

// ── WARNING-level: Integer overflow potential ──
fn multiply(a: u32, b: u32) -> u32 {
    a * b  // Can overflow without checked_mul
}

// ── WARNING-level: Missing error handling (unwrap) ──
fn parse_port(s: &str) -> u16 {
    s.parse().unwrap()
}

// ── WARNING-level: Unnecessary double clone ──
fn process_names(names: &[String]) -> Vec<String> {
    let mut result = Vec::new();
    for name in names {
        result.push(name.clone().clone()); // Double clone
    }
    result
}

// ── SUGGESTION-level: Could use iterator collect instead of manual loop ──
fn filter_positive(numbers: &[i32]) -> Vec<i32> {
    let mut result = Vec::new();
    for &n in numbers {
        if n > 0 {
            result.push(n);
        }
    }
    result
    // Could be: numbers.iter().filter(|&&n| n > 0).copied().collect()
}

// ── SUGGESTION-level: String formatting could use write! macro ──
fn build_table(entries: &[(String, u32)]) -> String {
    let mut output = String::new();
    output += "| Name | Count |\n";
    output += "|------|-------|\n";
    for (name, count) in entries {
        output += &format!("| {} | {} |\n", name, count);
    }
    output
}

// ── SUGGESTION-level: HashMap used but could be a struct ──
fn create_config() -> HashMap<String, String> {
    let mut config = HashMap::new();
    config.insert("host".to_string(), "localhost".to_string());
    config.insert("port".to_string(), "8080".to_string());
    config.insert("debug".to_string(), "true".to_string());
    config.insert("max_retries".to_string(), "3".to_string());
    config
}

// ── INFO-level: TODO / dead code ──
// TODO: implement caching layer
// FIXME: temporary workaround for upstream bug
#[allow(dead_code)]
fn placeholder() -> bool {
    false
}
