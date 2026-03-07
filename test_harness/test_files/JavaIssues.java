import java.sql.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import java.text.SimpleDateFormat; // unused import

/**
 * Intentionally buggy Java code for testing the code review agent.
 * Contains issues at every severity level including deadlocks and concurrency bugs.
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

    // ── ERROR-level: Classic deadlock — two locks acquired in opposite order ──
    private final Object lockA = new Object();
    private final Object lockB = new Object();
    private int balanceA = 1000;
    private int balanceB = 2000;

    public void transferAtoB(int amount) {
        synchronized (lockA) {
            synchronized (lockB) {  // Acquires lockA then lockB
                balanceA -= amount;
                balanceB += amount;
            }
        }
    }

    public void transferBtoA(int amount) {
        synchronized (lockB) {
            synchronized (lockA) {  // Acquires lockB then lockA — DEADLOCK!
                balanceB -= amount;
                balanceA += amount;
            }
        }
    }

    // ── ERROR-level: Double-checked locking without volatile ──
    private static JavaIssues instance;

    public static JavaIssues getInstance() {
        if (instance == null) {                    // First check (no lock)
            synchronized (JavaIssues.class) {
                if (instance == null) {            // Second check (with lock)
                    instance = new JavaIssues();   // BUG: instance not volatile,
                }                                  // another thread may see
            }                                      // partially constructed object
        }
        return instance;
    }

    // ── ERROR-level: ConcurrentModificationException ──
    public void removeInactive(List<Map<String, Object>> users) {
        for (Map<String, Object> user : users) {     // Iterating
            if (!Boolean.TRUE.equals(user.get("active"))) {
                users.remove(user);                   // Modifying while iterating!
            }
        }
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

    // ── WARNING-level: Thread pool never shut down — resource leak ──
    public List<Future<String>> processAsync(List<String> tasks) {
        ExecutorService pool = Executors.newFixedThreadPool(4);
        List<Future<String>> futures = new ArrayList<>();
        for (String task : tasks) {
            futures.add(pool.submit(() -> {
                Thread.sleep(100);
                return "done: " + task;
            }));
        }
        return futures;
        // pool is never shut down!
    }

    // ── WARNING-level: Race condition — check-then-act without synchronization ──
    private Map<String, String> cache = new HashMap<>();

    public String getOrCompute(String key) {
        if (!cache.containsKey(key)) {           // Check
            String value = expensiveCompute(key);
            cache.put(key, value);               // Act — race between check and put
        }
        return cache.get(key);
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
        System.out.println("Order processed: " + orderId);
    }

    // ── SUGGESTION-level: String concatenation in loop ──
    public String buildReport(List<String> items) {
        String report = "";
        for (String item : items) {
            report += "- " + item + "\n";
        }
        return report;
    }

    // ── SUGGESTION-level: Could use streams ──
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

    // ── SUGGESTION-level: Insecure random for security token ──
    public String generateToken() {
        Random rand = new Random();
        return String.valueOf(rand.nextLong());
    }

    // ── INFO-level: TODO comments ──
    // TODO: add connection pooling
    // FIXME: this class is getting too large, consider splitting
    public void placeholder() {
        // no-op
    }

    private String expensiveCompute(String key) {
        return key.toUpperCase();
    }
}
