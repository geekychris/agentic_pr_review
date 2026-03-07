package main

import (
	"database/sql"
	"fmt"
	"net/http"
	"os/exec"
)

// SQL injection
func getUser(db *sql.DB, username string) (*sql.Row, error) {
	query := fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", username)
	row := db.QueryRow(query)
	return row, nil
}

// Unchecked error
func writeFile(path string, data []byte) {
	f, _ := os.Create(path)
	f.Write(data)
	f.Close()
}

// Command injection
func runCommand(userInput string) string {
	cmd := exec.Command("sh", "-c", userInput)
	out, _ := cmd.Output()
	return string(out)
}

// Race condition - shared state without mutex
var requestCount int

func handler(w http.ResponseWriter, r *http.Request) {
	requestCount++
	fmt.Fprintf(w, "Request #%d", requestCount)
}

// Resource leak - response body not closed
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

// Goroutine leak
func processItems(items []string) {
	for _, item := range items {
		go func() {
			fmt.Println(item) // Bug: captures loop variable
		}()
	}
}
