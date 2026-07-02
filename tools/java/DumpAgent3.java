import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.Path;
import java.io.PrintStream;
import java.io.FileOutputStream;
import java.net.URL;
import java.net.URLClassLoader;
import java.util.Enumeration;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

public class DumpAgent3 {
    private static PrintStream log;

    public static void agentmain(String args, Instrumentation inst) {
        try {
            log = new PrintStream(new FileOutputStream("C:\\workspace\\dump_agent.log", true));
        } catch (Exception e) { log = System.out; }

        Path outputDir = Paths.get("C:\\workspace\\dumped_classes");

        log.println("[DumpAgent3] Searching for plugin jar...");
        String jarPath = "C:\\workspace\\plugin.jar";
        log.println("[DumpAgent3] Using jar: " + jarPath);

        inst.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader, String className,
                    Class<?> classBeingRedefined, ProtectionDomain protectionDomain,
                    byte[] classfileBuffer) {
                if (className != null && className.startsWith("com/fine/")) {
                    try {
                        Path filePath = outputDir.resolve(className + ".class");
                        Files.createDirectories(filePath.getParent());
                        Files.write(filePath, classfileBuffer);
                    } catch (Exception e) {
                        log.println("[DumpAgent3] ERROR: " + className + " - " + e.getMessage());
                    }
                }
                return null;
            }
        }, true);

        // Step 3: Read jar and try to load ALL com.fine.* classes
        int total = 0, loadedCount = 0, failedCount = 0;
        try {
            JarFile jar = new JarFile(jarPath);
            Enumeration<JarEntry> entries = jar.entries();
            while (entries.hasMoreElements()) {
                JarEntry entry = entries.nextElement();
                String name = entry.getName();
                if (!name.endsWith(".class") || !name.startsWith("com/fine/")) continue;
                total++;
                String className = name.substring(0, name.length() - 6).replace('/', '.');
                if (className.contains("package-info") || className.contains("module-info")) continue;
                try {
                    Class.forName(className, true, DumpAgent3.class.getClassLoader());
                    loadedCount++;
                } catch (Throwable t) {
                    failedCount++;
                }
            }
            jar.close();
        } catch (Exception e) {
            log.println("[DumpAgent3] Error reading jar: " + e.getMessage());
        }
        log.println("[DumpAgent3] Total: " + total + ", Loaded: " + loadedCount + ", Failed: " + failedCount);

        // Step 4: Retransform all loaded com.fine.* classes
        int retransformed = 0;
        Class<?>[] allClasses = inst.getAllLoadedClasses();
        for (Class<?> clazz : allClasses) {
            String name = clazz.getName().replace('.', '/');
            if (!name.startsWith("com/fine/")) continue;
            try {
                if (inst.isModifiableClass(clazz) && !clazz.isInterface()) {
                    inst.retransformClasses(clazz);
                    retransformed++;
                }
            } catch (Exception e) { }
        }
        log.println("[DumpAgent3] Retransformed: " + retransformed);
        log.println("[DumpAgent3] === DONE ===");
        log.flush();
    }

    public static void premain(String args, Instrumentation inst) {
        agentmain(args, inst);
    }
}
