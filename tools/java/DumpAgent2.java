import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.Path;
import java.io.PrintStream;
import java.io.FileOutputStream;

/**
 * Java Agent v2: Dump decrypted class bytes from running JVM.
 * Uses multiple strategies to extract class bytes.
 */
public class DumpAgent2 {

    private static PrintStream log;

    public static void agentmain(String args, Instrumentation inst) {
        try {
            log = new PrintStream(new FileOutputStream("C:\\workspace\\dump_agent.log", true));
        } catch (Exception e) {
            log = System.out;
        }

        String prefix = (args != null && !args.isEmpty()) ? args : "com/fine/";
        Path outputDir = Paths.get("C:\\workspace\\dumped_classes");

        log.println("[DumpAgent2] === Starting dump ===");
        log.println("[DumpAgent2] Prefix filter: " + prefix);

        // List ALL loaded classes matching prefix
        Class<?>[] loadedClasses = inst.getAllLoadedClasses();
        int matching = 0;
        int modifiable = 0;
        int dumped = 0;

        log.println("[DumpAgent2] Scanning " + loadedClasses.length + " total loaded classes...");

        for (Class<?> clazz : loadedClasses) {
            String name = clazz.getName().replace('.', '/');
            if (!name.startsWith(prefix)) {
                continue;
            }
            matching++;
            log.println("[DumpAgent2] FOUND: " + name
                    + " modifiable=" + inst.isModifiableClass(clazz)
                    + " interface=" + clazz.isInterface());
        }

        // Try strategy 1: retransformClasses
        log.println("[DumpAgent2] === Strategy 1: retransformClasses ===");
        final Path outputDirFinal = outputDir;
        final int[] dumpedCount = {0};

        inst.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader, String className,
                    Class<?> classBeingRedefined, ProtectionDomain protectionDomain,
                    byte[] classfileBuffer) {
                if (className != null && className.startsWith(prefix)) {
                    try {
                        Path filePath = outputDirFinal.resolve(className + ".class");
                        Files.createDirectories(filePath.getParent());
                        Files.write(filePath, classfileBuffer);
                        dumpedCount[0]++;
                        log.println("[DumpAgent2] DUMPED via retransform: " + className
                                + " (" + classfileBuffer.length + " bytes)");
                    } catch (Exception e) {
                        log.println("[DumpAgent2] ERROR writing " + className + ": " + e.getMessage());
                    }
                }
                return null;
            }
        }, true);

        for (Class<?> clazz : loadedClasses) {
            String name = clazz.getName().replace('.', '/');
            if (!name.startsWith(prefix)) continue;
            if (!inst.isModifiableClass(clazz) || clazz.isInterface()) continue;
            try {
                inst.retransformClasses(clazz);
                dumped++;
                log.println("[DumpAgent2] Called retransform for: " + name);
            } catch (Throwable e) {
                log.println("[DumpAgent2] retransform FAILED for " + name + ": " + e);
            }
        }

        log.println("[DumpAgent2] === Summary ===");
        log.println("[DumpAgent2] Matching classes: " + matching);
        log.println("[DumpAgent2] Dumped via retransform: " + dumpedCount[0]);
        log.println("[DumpAgent2] === Done ===");
        log.flush();
    }
}
