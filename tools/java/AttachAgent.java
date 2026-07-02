import com.sun.tools.attach.VirtualMachine;
import com.sun.tools.attach.VirtualMachineDescriptor;
public class AttachAgent {
    public static void main(String[] args) throws Exception {
        if (args.length < 1 || "--list".equals(args[0])) {
            for (VirtualMachineDescriptor vmd : VirtualMachine.list())
                System.out.println("  PID: " + vmd.id() + " -> " + vmd.displayName());
            return;
        }
        String pid = args[0];
        String agentArgs = args.length > 1 ? args[1] : "com/fine/";
        String agentJar = "C:\\workspace\\da3.jar";
        System.out.println("Attaching PID: " + pid + " jar=" + agentJar + " prefix=" + agentArgs);
        VirtualMachine vm = VirtualMachine.attach(pid);
        try { vm.loadAgent(agentJar, agentArgs); System.out.println("OK"); }
        catch (Exception e) { System.err.println("Failed: " + e.getMessage()); }
        finally { vm.detach(); }
    }
}
