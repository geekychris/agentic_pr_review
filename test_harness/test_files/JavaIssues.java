import java.sql.*;
import java.io.*;
import java.util.*;

/**
 * Intentionally buggy Java code for testing the code review agent.
 */
public class JavaIssues {

    // SQL injection
    public ResultSet getUser(Connection conn, String username) throws SQLException {
        Statement stmt = conn.createStatement();
        return stmt.executeQuery("SELECT * FROM users WHERE name = '" + username + "'");
    }

    // Resource leak - connection never closed
    public String readFromDb(String url) throws Exception {
        Connection conn = DriverManager.getConnection(url);
        Statement stmt = conn.createStatement();
        ResultSet rs = stmt.executeQuery("SELECT value FROM config LIMIT 1");
        rs.next();
        return rs.getString(1);
        // conn is never closed!
    }

    // Null pointer risk
    public String getUserEmail(Map<String, Object> user) {
        return user.get("email").toString();
    }

    // Hardcoded secret
    private static final String SECRET_KEY = "super-secret-key-12345";

    // Catching generic Exception
    public void processData(String input) {
        try {
            int value = Integer.parseInt(input);
            System.out.println(100 / value);
        } catch (Exception e) {
            // Swallowing exception silently
        }
    }

    // Thread safety issue
    private int counter = 0;
    public void increment() {
        counter++;  // Not thread-safe
    }

    // Insecure random
    public String generateToken() {
        Random rand = new Random();
        return String.valueOf(rand.nextLong());
    }
}
