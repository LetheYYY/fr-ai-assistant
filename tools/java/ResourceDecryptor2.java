import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.*;
import javax.crypto.Cipher;

/**
 * Standalone decryptor for FR plugin encrypted resources.
 * Uses standard Java RSA with hardcoded private key (Java 7 compatible).
 */
public class ResourceDecryptor2 {

    private static final String PRIVATE_KEY_B64 =
        "MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCCnNN1GhD0/LgLyhFfq7LsHC6P2tMSScthIhDJZ094m6lWhGfEOXpleH4vqvkqzLTowoHqkQ9bk6YecqkJZ7+2IenVvgDHfcY7h5CANONKGluDqiMJxFXkVpqm0NL0hxopiEeeCFUKk/GThfhhTcINmukGb15Q27tPsEW5S3YKHmvAaRQf4Pz0vjyySmKrogJbpfuRlYoL+4bx4bupKNNpU4Ek4+q1XtbaRqLAjri/i8s66dxO4bNFk15lxWCdoXV3WsKPmQZAMOUqYPTvePiFy80jjzt9ZIkQCXYqntmYoKdNzbTGfv3DpWsGxGlg8gZ6uB9boHhNdvsD8yrWS5YDAgMBAAECggEABSNKJicaV6jBTKVsPYkxhpwtMLd46hVBDNccNe/8blAhPygCNPPV3rv4qsNc/dQDocxU8/c01XNfa38zKw2LuwxmeGP6/93wuFLC2mg6MKYMx4cfzbiNcGf/uWQpiDjwTIXx20OUpM/hBt6UQK+gXIylcf1bhm6+VYonk/xl7kvpgKzWAcoT/XaXqlSFLKbT3/93wpQM3KPL1SpUdxFKygyZ4OK1JsDX/kjZYelxPjaTgVeJ0OJiuVN20R2pctsLXmn68wLZb1J1P1GhG+eXINc87UNMJifk77Z7FJpr4siiGJmfPfr9wU9B6oseEwKkz92TYMm4Dl+XXY+1qfv/gQKBgQDUgDm4TCNGwFGhUgsrmlscNjZRI12gTKpfboU/LtfRr3M8bOAzvOsTiAzXxI9XhoYDkbz2JLZLrY2gEqafT4pcvFfbbKVCcxM8Yn6h5V+AoqaPitE982DZnEZ0VO/fejEHQb84/8EntIrUpZ1Ciiz/nW8aCRp0fJzLGKBoSlRFYwKBgQCdWV/AD1BNlhRQnAIYKuWH7RkZPysPNwJ13bWyKRyW8VjT9oQ1IycHIa7NsHJBrdHGFIQrb3ZRLiXnLe8IwD0B8eP75DamZBCxiqCLSmCqF1eCqTQ3yMTRc9HS20s6vnV+9NkTJteuTvQinQdQVZsjnICBnLE6BoKhAkEpQVMe4QKBgDevmnCXUy85OqsBqve0LWgJNNayY9ib/pGfjr9t8RR728Db7yzftuKZZnQsiDuxfvD0ggYmvLa8Nj7aZFufJm0C1iskH3J4YXQTg4e9afd1qBw5jnejjZ+4+iWGFI4FoU97hTbUnrNe9nqfI8TKHNynTvQNqqcX+KaoP3DU+ZxtAoGAH+uUmBLDOKocfunXJu302GlJ8Sw2YQTI0/5hML5UVW6qlX1p/pmd/j1gB8wmsZpAdw2Mbn9TIk7ZU5em6UCOX8mhdWUrjP+5vzqfLQKur3LCxvfqZvKssszrIPppvYYLsfCb5N25XVwY/LicVji3mzbRfvm5nkrZzy306BifcyECgYALlaSMd9oqjr6kY1IEwIVThK8TpHJdZJ3e4dochLq3APJvsrDVDg4uvllxNBKvJZn1WSKGXuEKIkn/w6P0trf5y2GlWdUCxH+dGUb8osDisASUlkJpuqVrzWB1/8NM3USmfGwONYocwaY3Wm5OhtWdg+3rLrpxavHqIiwV2mr8Fw==";

    public static void main(String[] args) throws Exception {
        String resourcesDir = "C:\\Users\\admin\\Desktop\\fanruan2\\插件\\com.fr.plugin.design.ai.v11-1.0.6\\decompiled\\resources";
        String outputDir  = resourcesDir + "_decrypted";

        if (args.length >= 1) resourcesDir = args[0];
        if (args.length >= 2) outputDir = args[1];

        System.out.println("=== Resource Decryptor ===");
        System.out.println("Input:  " + resourcesDir);
        System.out.println("Output: " + outputDir);

        byte[] keyBytes = Base64Decode(PRIVATE_KEY_B64);
        PKCS8EncodedKeySpec spec = new PKCS8EncodedKeySpec(keyBytes);
        KeyFactory kf = KeyFactory.getInstance("RSA");
        PrivateKey privateKey = kf.generatePrivate(spec);
        System.out.println("RSA Private Key loaded OK.");

        Path inputPath = Paths.get(resourcesDir);
        Path outPath = Paths.get(outputDir);
        Files.createDirectories(outPath);

        int ok = 0, fail = 0, skip = 0;

        List<Path> files = new ArrayList<Path>();
        addFiles(inputPath, files);

        for (Path file : files) {
            String name = file.getFileName().toString().toLowerCase();
            if (!name.endsWith(".txt") && !name.endsWith(".md")) {
                skip++; continue;
            }
            Path rel = inputPath.relativize(file);
            Path outFile = outPath.resolve(rel);
            try {
                StringBuilder sb = new StringBuilder();
                BufferedReader br = Files.newBufferedReader(file, java.nio.charset.StandardCharsets.UTF_8);
                String line;
                while ((line = br.readLine()) != null) sb.append(line);
                br.close();

                String content = sb.toString().trim();
                if (content.isEmpty()) { skip++; continue; }

                String decrypted = decryptBlocks(privateKey, content);
                Files.createDirectories(outFile.getParent());
                Files.write(outFile, decrypted.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                System.out.println("  [OK] " + rel + " -> " + decrypted.length() + " chars");
                ok++;
            } catch (Exception e) {
                System.out.println("  [FAIL] " + rel + ": " + e.getMessage());
                fail++;
            }
        }

        System.out.println("\n=== Summary ===");
        System.out.println("Decrypted: " + ok);
        System.out.println("Failed:    " + fail);
        System.out.println("Skipped:   " + skip);
    }

    static void addFiles(Path dir, List<Path> result) throws IOException {
        File d = dir.toFile();
        File[] children = d.listFiles();
        if (children == null) return;
        for (File child : children) {
            if (child.isDirectory()) {
                addFiles(child.toPath(), result);
            } else {
                result.add(child.toPath());
            }
        }
    }

    static byte[] Base64Decode(String s) {
        // Java 7 compatible Base64 decode
        try {
            return javax.xml.bind.DatatypeConverter.parseBase64Binary(s);
        } catch (Exception e) {
            throw new RuntimeException("Base64 decode failed", e);
        }
    }

    static String decryptBlocks(PrivateKey key, String b64) throws Exception {
        byte[] all = Base64Decode(b64);
        Cipher c = Cipher.getInstance("RSA/ECB/PKCS1Padding");
        c.init(Cipher.DECRYPT_MODE, key);
        int bs = 256;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < all.length; i += bs) {
            int end = Math.min(i + bs, all.length);
            byte[] block = Arrays.copyOfRange(all, i, end);
            sb.append(new String(c.doFinal(block), "UTF-8"));
        }
        return sb.toString();
    }
}
