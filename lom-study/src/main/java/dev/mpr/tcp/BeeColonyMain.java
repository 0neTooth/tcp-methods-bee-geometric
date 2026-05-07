package dev.mpr.tcp;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class BeeColonyMain {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: BeeColonyMain <coverage_matrix.csv> <output_order.csv>");
            System.exit(1);
        }

        Path matrixPath = Paths.get(args[0]);
        Path outputPath = Paths.get(args[1]);

        CoverageData coverageData = readCoverageMatrix(matrixPath);

        List<String> order = BeeColonyPrioritizer.prioritize(
                coverageData.tests,
                coverageData.testCoverage,
                coverageData.totalMethods,
                30,
                200,
                20,
                38L
        );

        OrderWriter.write(outputPath, order);

        System.out.println("[done] Bee Colony order saved to " + outputPath);
        System.out.println("[info] tests=" + coverageData.tests.size() + ", methods=" + coverageData.totalMethods);
    }

    private static CoverageData readCoverageMatrix(Path path) throws IOException {
        List<String> tests = new ArrayList<>();
        Map<String, Set<Integer>> testCoverage = new LinkedHashMap<>();

        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String header = reader.readLine();
            if (header == null) {
                throw new IOException("Empty coverage matrix: " + path);
            }

            List<String> columns = parseCsvLine(header);
            int totalMethods = columns.size() - 1;

            String line;
            while ((line = reader.readLine()) != null) {
                List<String> parts = parseCsvLine(line);
                if (parts.size() < 2) {
                    continue;
                }

                String testName = parts.get(0).trim();
                tests.add(testName);

                Set<Integer> covered = new LinkedHashSet<>();
                int limit = Math.min(parts.size() - 1, totalMethods);

                for (int i = 0; i < limit; i++) {
                    String value = parts.get(i + 1).trim();
                    if ("1".equals(value) || "true".equalsIgnoreCase(value)) {
                        covered.add(i);
                    }
                }

                testCoverage.put(testName, covered);
            }

            return new CoverageData(tests, testCoverage, totalMethods);
        }
    }

    private static List<String> parseCsvLine(String line) {
        List<String> result = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean inQuotes = false;

        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);

            if (ch == '"') {
                if (inQuotes && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    current.append('"');
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (ch == ',' && !inQuotes) {
                result.add(current.toString());
                current.setLength(0);
            } else {
                current.append(ch);
            }
        }

        result.add(current.toString());
        return result;
    }


    private static class CoverageData {
        final List<String> tests;
        final Map<String, Set<Integer>> testCoverage;
        final int totalMethods;

        CoverageData(List<String> tests, Map<String, Set<Integer>> testCoverage, int totalMethods) {
            this.tests = tests;
            this.testCoverage = testCoverage;
            this.totalMethods = totalMethods;
        }
    }
}