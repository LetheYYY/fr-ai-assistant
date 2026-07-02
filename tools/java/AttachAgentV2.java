import com.sun.tools.attach.VirtualMachine;
import com.sun.tools.attach.VirtualMachineDescriptor;

/**
 * Attach agent jar to running JVM.
 */
public class AttachAgent {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.out.println("Usage: java AttachAgent <pid> [class_prefix]");
            for (VirtualMachineDescriptor vmd : VirtualMachine.list()) {
                System.out.println("  PID: " + vmd.id() + " -> " + vmd.displayName());
            }
            return;
        }

        if ("--list".equals(args[0])) {
            for (VirtualMachineDescriptor vmd : VirtualMachine.list()) {
                System.out.println("  PID: " + vmd.id() + " -> " + vmd.displayName());
            }
            return;
        }

        String pid = args[0];
        String agentArgs = args.length > 1 ? args[1] : "com/fine/";
        String agentJar = "C:\\workspace\\da.jar";

        System.out.println("Attaching to PID: " + pid);
        System.out.println("Agent jar: " + agentJar);
        System.out.println("Class prefix: " + agentArgs);

        VirtualMachine vm = VirtualMachine.attach(pid);
        try {
            vm.loadAgent(agentJar, agentArgs);
            System.out.println("Agent loaded successfully!");
        } catch (Exception e) {
            System.err.println("Failed: " + e.getMessage());
        } finally {
            vm.detach();
        }
    }
}
