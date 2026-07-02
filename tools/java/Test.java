import java.io.*;
public class Test {
    public static void main(String[] a) {
        File f = new File("C:\\Users\\admin\\Desktop\\fanruan2\\??\\com.fr.plugin.design.ai.v11-1.0.6\\decompiled\\resources\\com\\fine\\ai\\prompt\\copilot_plan.txt");
        System.out.println("File exists: " + f.exists());
        System.out.println("File length: " + f.length());
        
        File dir = new File("C:\\Users\\admin\\Desktop\\fanruan2\\??\\com.fr.plugin.design.ai.v11-1.0.6\\decompiled\\resources");
        File[] files = dir.listFiles();
        System.out.println("Dir children: " + (files != null ? files.length : "null"));
        if (files != null) {
            for (File cf : files) System.out.println("  " + cf.getName());
        }
    }
}
