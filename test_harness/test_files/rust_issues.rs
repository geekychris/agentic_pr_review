use std::fs;
use std::process::Command;

// Unwrap on Result - will panic
fn read_config(path: &str) -> String {
    fs::read_to_string(path).unwrap()
}

// Command injection via user input
fn run_user_command(input: &str) -> String {
    let output = Command::new("sh")
        .arg("-c")
        .arg(input)
        .output()
        .unwrap();
    String::from_utf8_lossy(&output.stdout).to_string()
}

// Unnecessary clone
fn process_names(names: &[String]) -> Vec<String> {
    let mut result = Vec::new();
    for name in names {
        result.push(name.clone().clone()); // Double clone
    }
    result
}

// Unsafe block without justification
fn dangerous_operation(ptr: *const i32) -> i32 {
    unsafe {
        *ptr
    }
}

// Integer overflow potential
fn multiply(a: u32, b: u32) -> u32 {
    a * b  // Can overflow without checked_mul
}

// Hardcoded secret
const API_TOKEN: &str = "ghp_super_secret_token_12345";

// Missing error handling
fn parse_port(s: &str) -> u16 {
    s.parse().unwrap()
}
