import java.io.*;
import java.nio.charset.*;
public class Check {
    public static void main(String[] a) throws Exception {
        String path = "C:\\workspace\\res_decrypted\\com\\fine\\ai\\prompt\\copilot_plan.txt";
        // ?UTF-8?
        String utf8 = new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(path)), StandardCharsets.UTF_8);
        System.out.println("UTF-8 length: " + utf8.length());
        System.out.println("First 200 chars (UTF-8):");
        System.out.println(utf8.substring(0, Math.min(200, utf8.length())));
        
        // ????? replacement character (U+FFFD)
        int count = 0;
        for (char c : utf8.toCharArray()) {
            if (c == '\uFFFD') count++;
        }
        System.out.println("\nReplacement chars (U+FFFD): " + count);
        
        // ??GBK
        String gbk = new String(utf8.getBytes(StandardCharsets.UTF_8), Charset.forName("GBK"));
        System.out.println("\nGBK display of same text:");
        System.out.println(gbk.substring(0, Math.min(200, gbk.length())));
    }
}
