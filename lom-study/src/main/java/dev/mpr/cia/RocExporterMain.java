package dev.mpr.cia;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.stream.Collectors;

/**
 * CLI entry point that generates {@code roc.csv} for a pair of buggy/fixed class directories.
 *
 * <p>Usage:
 * <pre>{@code
 *   java -cp lom-study-all.jar dev.mpr.cia.RocExporterMain <buggyClassesDir> <fixedClassesDir> <outputCsv> [includePrefixesFile]
 * }</pre>
 * The optional {@code includePrefixesFile} should contain one internal-class prefix per line
 * (e.g. {@code org/jsoup/} or {@code org/jsoup}). Lines starting with {@code #} are ignored.
 * </p>
 */
public final class RocExporterMain {

    private RocExporterMain() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("Usage: RocExporterMain <buggyClassesDir> <fixedClassesDir> <outputCsv> [includePrefixesFile]");
            System.exit(1);
        }

        Path buggyDir = Paths.get(args[0]).toAbsolutePath();
        Path fixedDir = Paths.get(args[1]).toAbsolutePath();
        Path outputCsv = Paths.get(args[2]).toAbsolutePath();

        if (!Files.isDirectory(buggyDir)) {
            exitWithError(String.format(Locale.ROOT, "Buggy classes directory not found: %s", buggyDir));
        }
        if (!Files.isDirectory(fixedDir)) {
            exitWithError(String.format(Locale.ROOT, "Fixed classes directory not found: %s", fixedDir));
        }

        Collection<String> includePrefixes = List.of();
        if (args.length >= 4) {
            includePrefixes = readIncludePrefixes(Paths.get(args[3]));
        }

        List<MethodMetrics> metrics = AsmRocAnalyzer.analyze(buggyDir, fixedDir, includePrefixes);
        writeCsv(outputCsv, metrics);
    }

    private static void writeCsv(Path csvPath, List<MethodMetrics> metrics) throws IOException {
        Path parent = csvPath.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        try (BufferedWriter writer = Files.newBufferedWriter(csvPath, StandardCharsets.UTF_8)) {
            writer.write("owner_internal,method,descriptor,total_instructions,changed_instructions,roc");
            writer.newLine();
            for (MethodMetrics metric : metrics) {
                writer.write(metric.toCsvLine());
                writer.newLine();
            }
        }
    }

    private static Collection<String> readIncludePrefixes(Path file) throws IOException {
        if (!Files.exists(file)) {
            return List.of();
        }
        return Files.readAllLines(file, StandardCharsets.UTF_8).stream()
                .map(String::trim)
                .filter(line -> !line.isEmpty() && !line.startsWith("#"))
                .map(RocExporterMain::normalizePrefix)
                .collect(Collectors.toList());
    }

    private static String normalizePrefix(String prefix) {
        String normalized = prefix.replace('.', '/');
        if (!normalized.endsWith("/")) {
            normalized = normalized + "/";
        }
        return normalized;
    }

    private static void exitWithError(String message) {
        System.err.println(message);
        System.exit(2);
    }
}
