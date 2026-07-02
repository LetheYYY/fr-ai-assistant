import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.Path;

/**
 * Java Agent: dump decrypted class bytes from running JVM.
 * Attach to FR Designer process to dump ALL com.fine.* classes
 * that have been decrypted by the custom class loader at runtime.
 */
public class DumpAgent {

    public static void agentmain(String args, Instrumentation inst) {
        String prefix = (args != null && !args.isEmpty()) ? args.replace('.', '/') : "com/fine/";
        Path outputDir = Paths.get("C:\\workspace\\dumped_classes");

        System.out.println("[DumpAgent] === Starting dump ===");
        System.out.println("[DumpAgent] Prefix filter: " + prefix);
        System.out.println("[DumpAgent] Output dir: " + outputDir.toAbsolutePath());

        // Add transformer with retransform capability
        inst.addTransformer(new ClassFileTransformer() {
            @Override
            public byte[] transform(ClassLoader loader, String className,
                    Class<?> classBeingRedefined, ProtectionDomain protectionDomain,
                    byte[] classfileBuffer) {
                if (className != null && className.startsWith(prefix)) {
                    try {
                        Path filePath = outputDir.resolve(className + ".class");
                        Files.createDirectories(filePath.getParent());
                        Files.write(filePath, classfileBuffer);
                        System.out.println("[DumpAgent] DUMPED: " + className
                                + " (" + classfileBuffer.length + " bytes)");
                    } catch (Exception e) {
                        System.err.println("[DumpAgent] ERROR writing " + className + ": " + e.getMessage());
                    }
                }
                return null; // don't modify the class
            }
        }, true); // canRetransform = true

        // Now retransform ALL matching classes that are already loaded
        Class<?>[] loadedClasses = inst.getAllLoadedClasses();
        int retransformed = 0;
        int skipped = 0;

        for (Class<?> clazz : loadedClasses) {
            String name = clazz.getName().replace('.', '/');
            if (!name.startsWith(prefix)) {
                continue;
            }
            try {
                if (inst.isModifiableClass(clazz) && !clazz.isInterface()) {
                    inst.retransformClasses(clazz);
                    retransformed++;
                } else {
                    skipped++;
                }
            } catch (Exception e) {
                System.err.println("[DumpAgent] Retransform FAILED for "
                        + name + ": " + e.getMessage());
            }
        }

        System.out.println("[DumpAgent] === Summary ===");
        System.out.println("[DumpAgent] Retransformed: " + retransformed);
        System.out.println("[DumpAgent] Skipped (interface/unmodifiable): " + skipped);
        System.out.println("[DumpAgent] === Done ===");
    }

    public static void premain(String args, Instrumentation inst) {
        agentmain(args, inst);
    }
}
