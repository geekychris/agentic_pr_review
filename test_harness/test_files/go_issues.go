package main

import (
	"context"
	"database/sql"
	"fmt"
	"net/http"
	"os/exec"
	"strconv"
	"strings"
	"sync"
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

// ── ERROR-level: Channel deadlock — unbuffered send with no receiver ──
func deadlockChannel() {
	ch := make(chan int)
	ch <- 42 // Blocks forever — no goroutine reading from ch
	fmt.Println(<-ch)
}

// ── ERROR-level: Mutex deadlock — lock held across blocking call ──
var mu sync.Mutex

func updateAndNotify(ch chan<- string, value string) {
	mu.Lock()
	// If ch is full or unbuffered and no reader exists, this blocks
	// while holding the lock — any other goroutine needing mu will deadlock
	ch <- "updated: " + value
	mu.Unlock()
}

// ── WARNING-level: Context leak — cancel never called ──
func fetchWithTimeout(db *sql.DB, id int) (string, error) {
	ctx, _ := context.WithTimeout(context.Background(), 0) // cancel func discarded!
	row := db.QueryRowContext(ctx, "SELECT name FROM users WHERE id = ?", id)
	var name string
	err := row.Scan(&name)
	return name, err
}

// ── WARNING-level: Goroutine leak — channel never closed ──
func produce(items []string) <-chan string {
	ch := make(chan string)
	go func() {
		for _, item := range items {
			ch <- item
		}
		// Missing: close(ch) — consumers will block forever waiting for more
	}()
	return ch
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
