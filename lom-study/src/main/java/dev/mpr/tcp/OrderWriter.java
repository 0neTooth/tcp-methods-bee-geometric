package dev.mpr.tcp;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public class OrderWriter {
    public static void write(Path path, List<String> order) throws IOException {
        Files.createDirectories(path.getParent());

        try (BufferedWriter writer = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
            writer.write("rank,test");
            writer.newLine();

            int rank = 1;
            for (String test : order) {
                writer.write(rank + "," + test);
                writer.newLine();
                rank++;
            }
        }
    }
}