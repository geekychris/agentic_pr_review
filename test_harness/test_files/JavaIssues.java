import java.sql.*;
import java.io.*;
import java.util.*;
import java.text.SimpleDateFormat; // unused import

/**
 * Intentionally buggy Java code for testing the code review agent.
 */
public class JavaIssues {

    // ── ERROR-level: SQL injection ──
    public ResultSet getUser(Connection conn, String username) throws SQLException {
        Statement stmt = conn.createStatement();
        return stmt.executeQuery("SELECT * FROM users WHERE name = '" + username + "'");
    }

    // ── ERROR-level: Resource leak — connection never closed ──
    public String readFromDb(String url) throws Exception {
        Connection conn = DriverManager.getConnection(url);
        Statement stmt = conn.createStatement();
        ResultSet rs = stmt.executeQuery("SELECT value FROM config LIMIT 1");
        rs.next();
        return rs.getString(1);
        // conn is never closed!
    }

    // ── ERROR-level: Hardcoded secret ──
    private static final String SECRET_KEY = "super-secret-key-12345";

    // ── ERROR-level: Insecure random for security token ──
    public String generateToken() {
        Random rand = new Random();
        return String.valueOf(rand.nextLong());
    }

    // ── WARNING-level: Null pointer risk — no null check ──
    public String getUserEmail(Map<String, Object> user) {
        return user.get("email").toString();
    }

    // ── WARNING-level: Catching generic Exception + swallowing ──
    public void processData(String input) {
        try {
            int value = Integer.parseInt(input);
            System.out.println(100 / value);
        } catch (Exception e) {
            // Swallowing exception silently
        }
    }

    // ── WARNING-level: Thread safety issue (non-atomic increment) ──
    private int counter = 0;
    public void increment() {
        counter++;  // Not thread-safe
    }

    // ── WARNING-level: Magic numbers ──
    public double calculateShipping(double weight, String zone) {
        if (zone.equals("domestic")) {
            return weight * 2.5 + 4.99;
        } else {
            return weight * 7.25 + 14.99;
        }
    }

    // ── WARNING-level: System.out instead of logger ──
    public void processOrder(String orderId) {
        System.out.println("Processing order: " + orderId);
        // ... business logic ...
        System.out.println("Order processed: " + orderId);
    }

    // ── SUGGESTION-level: Method too long, does too many things ──
    public Map<String, Object> importCsvData(String csvContent) {
        Map<String, Object> result = new HashMap<>();
        String[] lines = csvContent.split("\n");
        String[] headers = lines[0].split(",");
        List<Map<String, String>> rows = new ArrayList<>();
        for (int i = 1; i < lines.length; i++) {
            String[] values = lines[i].split(",");
            Map<String, String> row = new HashMap<>();
            for (int j = 0; j < headers.length; j++) {
                row.put(headers[j], values[j]);
            }
            rows.add(row);
        }
        int valid = 0;
        int invalid = 0;
        for (Map<String, String> row : rows) {
            if (row.get("email") != null && row.get("email").contains("@")) {
                valid++;
            } else {
                invalid++;
            }
        }
        result.put("rows", rows);
        result.put("valid", valid);
        result.put("invalid", invalid);
        result.put("total", rows.size());
        return result;
    }

    // ── SUGGESTION-level: String concatenation in loop ──
    public String buildReport(List<String> items) {
        String report = "";
        for (String item : items) {
            report += "- " + item + "\n";
        }
        return report;
    }

    // ── SUGGESTION-level: Could use enhanced for-loop / streams ──
    public List<String> filterActive(List<Map<String, Object>> users) {
        List<String> names = new ArrayList<>();
        for (int i = 0; i < users.size(); i++) {
            Map<String, Object> u = users.get(i);
            if (Boolean.TRUE.equals(u.get("active"))) {
                names.add((String) u.get("name"));
            }
        }
        return names;
    }

    // ── INFO-level: TODO comments ──
    // TODO: add connection pooling
    // FIXME: this class is getting too large, consider splitting
    public void placeholder() {
        // no-op
    }
}
