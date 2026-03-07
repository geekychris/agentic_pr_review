package main

import (
	"database/sql"
	"fmt"
	"net/http"
	"os/exec"
	"strconv"
	"strings"
)

// ── ERROR-level: SQL injection ──
func getUser(db *sql.DB, username string) (*sql.Row, error) {
	query := fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", username)
	row := db.QueryRow(query)
	return row, nil
}

// ── ERROR-level: Command injection ──
func runCommand(userInput string) string {
	cmd := exec.Command("sh", "-c", userInput)
	out, _ := cmd.Output()
	return string(out)
}

// ── ERROR-level: Race condition — shared state without mutex ──
var requestCount int

func handler(w http.ResponseWriter, r *http.Request) {
	requestCount++
	fmt.Fprintf(w, "Request #%d", requestCount)
}

// ── WARNING-level: Unchecked errors ──
func writeFile(path string, data []byte) {
	f, _ := os.Create(path)
	f.Write(data)
	f.Close()
}

// ── WARNING-level: Resource leak — response body not closed ──
func fetchURL(url string) (string, error) {
	resp, err := http.Get(url)
	if err != nil {
		return "", err
	}
	// Missing: defer resp.Body.Close()
	buf := make([]byte, 1024)
	n, _ := resp.Body.Read(buf)
	return string(buf[:n]), nil
}

// ── WARNING-level: Goroutine captures loop variable ──
func processItems(items []string) {
	for _, item := range items {
		go func() {
			fmt.Println(item) // Bug: captures loop variable
		}()
	}
}

// ── WARNING-level: Magic numbers ──
func calculatePrice(qty int, unitPrice float64) float64 {
	subtotal := float64(qty) * unitPrice
	if subtotal > 100.0 {
		subtotal *= 0.9 // 10% discount
	}
	tax := subtotal * 0.0825
	shipping := 5.99
	if subtotal > 50.0 {
		shipping = 0
	}
	return subtotal + tax + shipping
}

// ── SUGGESTION-level: Exported function missing doc comment ──
func FormatUserName(first, last string) string {
	return strings.TrimSpace(first) + " " + strings.TrimSpace(last)
}

// ── SUGGESTION-level: Error not wrapped with context ──
func parsePort(s string) (int, error) {
	p, err := strconv.Atoi(s)
	if err != nil {
		return 0, err // should wrap: fmt.Errorf("parse port: %w", err)
	}
	if p < 1 || p > 65535 {
		return 0, fmt.Errorf("invalid port: %d", p)
	}
	return p, nil
}

// ── SUGGESTION-level: Inefficient string building ──
func buildCSV(rows [][]string) string {
	result := ""
	for _, row := range rows {
		line := ""
		for i, col := range row {
			if i > 0 {
				line += ","
			}
			line += col
		}
		result += line + "\n"
	}
	return result
}

// ── INFO-level: TODO comments, stub implementation ──
// TODO: add pagination support
// FIXME: this is a temporary implementation
func listUsers(db *sql.DB) ([]string, error) {
	rows, err := db.Query("SELECT name FROM users")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var names []string
	for rows.Next() {
		var name string
		rows.Scan(&name)
		names = append(names, name)
	}
	return names, nil
}
