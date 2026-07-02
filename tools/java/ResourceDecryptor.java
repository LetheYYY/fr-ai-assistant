import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.Base64;
import javax.crypto.Cipher;

/**
 * Standalone decryptor for FR plugin encrypted resources.
 * Uses the hardcoded RSA private key from EmbedFileManager.ALPHA
 * to decrypt .txt and .md files.
 */
public class ResourceDecryptor {

    // RSA Private Key in PKCS8 Base64 format (from EmbedFileManager.ALPHA)
    private static final String PRIVATE_KEY_B64 =
        "MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCCnNN1GhD0/LgLyhFfq7LsHC6P2tMSScthIhDJZ094m6lWhGfEOXpleH4vqvkqzLTowoHqkQ9bk6YecqkJZ7+2IenVvgDHfcY7h5CANONKGluDqiMJxFXkVpqm0NL0hxopiEeeCFUKk/GThfhhTcINmukGb15Q27tPsEW5S3YKHmvAaRQf4Pz0vjyySmKrogJbpfuRlYoL+4bx4bupKNNpU4Ek4+q1XtbaRqLAjri/i8s66dxO4bNFk15lxWCdoXV3WsKPmQZAMOUqYPTvePiFy80jjzt9ZIkQCXYqntmYoKdNzbTGfv3DpWsGxGlg8gZ6uB9boHhNdvsD8yrWS5YDAgMBAAECggEABSNKJicaV6jBTKVsPYkxhpwtMLd46hVBDNccNe/8blAhPygCNPPV3rv4qsNc/dQDocxU8/c01XNfa38zKw2LuwxmeGP6/93wuFLC2mg6MKYMx4cfzbiNcGf/uWQpiDjwTIXx20OUpM/hBt6UQK+gXIylcf1bhm6+VYonk/xl7kvpgKzWAcoT/XaXqlSFLKbT3/93wpQM3KPL1SpUdxFKygyZ4OK1JsDX/kjZYelxPjaTgVeJ0OJiuVN20R2pctsLXmn68wLZb1J1P1GhG+eXINc87UNMJifk77Z7FJpr4siiGJmfPfr9wU9B6oseEwKkz92TYMm4Dl+XXY+1qfv/gQKBgQDUgDm4TCNGwFGhUgsrmlscNjZRI12gTKpfboU/LtfRr3M8bOAzvOsTiAzXxI9XhoYDkbz2JLZLrY2gEqafT4pcvFfbbKVCcxM8Yn6h5V+AoqaPitE982DZnEZ0VO/fejEHQb84/8EntIrUpZ1Ciiz/nW8aCRp0fJzLGKBoSlRFYwKBgQCdWV/AD1BNlhRQnAIYKuWH7RkZPysPNwJ13bWyKRyW8VjT9oQ1IycHIa7NsHJBrdHGFIQrb3ZRLiXnLe8IwD0B8eP75DamZBCxiqCLSmCqF1eCqTQ3yMTRc9HS20s6vnV+9NkTJteuTvQinQdQVZsjnICBnLE6BoKhAkEpQVMe4QKBgDevmnCXUy85OqsBqve0LWgJNNayY9ib/pGfjr9t8RR728Db7yzftuKZZnQsiDuxfvD0ggYmvLa8Nj7aZFufJm0C1iskH3J4YXQTg4e9afd1qBw5jnejjZ+4+iWGFI4FoU97hTbUnrNe9nqfI8TKHNynTvQNqqcX+KaoP3DU+ZxtAoGAH+uUmBLDOKocfunXJu302GlJ8Sw2YQTI0/5hML5UVW6qlX1p/pmd/j1gB8wmsZpAdw2Mbn9TIk7ZU5em6UCOX8mhdWUrjP+5vzqfLQKur3LCxvfqZvKssszrIPppvYYLsfCb5N25XVwY/LicVji3mzbRfvm5nkrZzy306BifcyECgYALlaSMd9oqjr6kY1IEwIVThK8TpHJdZJ3e4dochLq3APJvsrDVDg4uvllxNBKvJZn1WSKGXuEKIkn/w6P0trf5y2GlWdUCxH+dGUb8osDisASUlkJpuqVrzWB1/8NM3USmfGwONYocwaY3Wm5OhtWdg+3rLrpxavHqIiwV2mr8Fw==";

    public static void main(String[] args) throws Exception {
        // Default: decrypt all files in the extracted resources directory
        String resourcesDir = "C:\\Users\\admin\\Desktop\\fanruan2\\插件\\com.fr.plugin.design.ai.v11-1.0.6\\decompiled\\resources";
        String outputDir = resourcesDir + "_decrypted";

        if (args.length >= 1) resourcesDir = args[0];
        if (args.length >= 2) outputDir = args[1];

        System.out.println("=== Resource Decryptor ===");
        System.out.println("Input:  " + resourcesDir);
        System.out.println("Output: " + outputDir);

        // Decode private key
        byte[] keyBytes = Base64.getDecoder().decode(PRIVATE_KEY_B64);
        PKCS8EncodedKeySpec spec = new PKCS8EncodedKeySpec(keyBytes);
        KeyFactory keyFactory = KeyFactory.getInstance("RSA");
        PrivateKey privateKey = keyFactory.generatePrivate(spec);

        System.out.println("RSA Private Key loaded: " + privateKey.getAlgorithm());

        // Walk through resources directory and decrypt .txt and .md files
        Path inputPath = Paths.get(resourcesDir);
        Path outputPath = Paths.get(outputDir);
        Files.createDirectories(outputPath);

        int decrypted = 0;
        int failed = 0;
        int skipped = 0;

        Files.walk(inputPath)
            .filter(Files::isRegularFile)
            .forEach(file -> {
                String name = file.getFileName().toString().toLowerCase();
                if (!name.endsWith(".txt") && !name.endsWith(".md")) {
                    skipped++;
                    return;
                }
                try {
                    // Read encrypted content
                    String encrypted = new String(Files.readAllBytes(file), "UTF-8");
                    String decryptedText = decryptLarge(privateKey, encrypted);

                    // Write to output preserving directory structure
                    Path relativePath = inputPath.relativize(file);
                    Path outFile = outputPath.resolve(relativePath);
                    Files.createDirectories(outFile.getParent());
                    Files.write(outFile, decryptedText.getBytes("UTF-8"));

                    System.out.println("  [OK] " + relativePath + " (" + decryptedText.length() + " chars)");
                    decrypted++;
                } catch (Exception e) {
                    System.out.println("  [FAIL] " + inputPath.relativize(file) + ": " + e.getMessage());
                    failed++;
                }
            });

        System.out.println("\n=== Summary ===");
        System.out.println("Decrypted: " + decrypted);
        System.out.println("Failed:    " + failed);
        System.out.println("Skipped:   " + skipped);
    }

    /**
     * Decrypt large content by splitting into RSA blocks.
     * RSA 2048-bit with PKCS1Padding can decrypt max 256 bytes per block.
     * Each encrypted chunk is a separate Base64 string.
     */
    private static String decryptLarge(PrivateKey key, String encryptedContent) throws Exception {
        Cipher cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding");

        // Try first as single chunk
        try {
            byte[] encryptedBytes = Base64.getDecoder().decode(encryptedContent.trim());
            cipher.init(Cipher.DECRYPT_MODE, key);
            byte[] decrypted = cipher.doFinal(encryptedBytes);
            return new String(decrypted, "UTF-8");
        } catch (Exception e) {
            // Not a single chunk - try line-by-line
        }

        // Try as multiple lines, each line is a separate Base64-encoded RSA block
        StringBuilder result = new StringBuilder();
        String[] lines = encryptedContent.split("\n");
        cipher.init(Cipher.DECRYPT_MODE, key);

        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.isEmpty()) continue;
            try {
                byte[] encryptedBytes = Base64.getDecoder().decode(trimmed);
                byte[] decrypted = cipher.doFinal(encryptedBytes);
                result.append(new String(decrypted, "UTF-8"));
            } catch (Exception e) {
                // If line-by-line fails, try as concatenated Base64
            }
        }

        if (result.length() > 0) return result.toString();

        // Last resort: try to decrypt whole content as one big Base64 blob
        // (EncryptionToolBox might use a different format)
        throw new Exception("Could not decrypt with standard RSA. May need EncryptionToolBox library.");
    }
}
