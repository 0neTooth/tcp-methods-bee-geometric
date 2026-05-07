package dev.mpr.tcp;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class GeometricDataLoader {

    public static CoverageData readCoverageMatrix(Path path) throws IOException {
        List<String> methodNames = new ArrayList<>();
        List<TestCoverage> tests = new ArrayList<>();

        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String header = reader.readLine();
            if (header == null) {
                throw new IOException("Empty coverage matrix: " + path);
            }

            List<String> columns = parseCsvLine(header);
            for (int i = 1; i < columns.size(); i++) {
                methodNames.add(columns.get(i));
            }

            String line;
            while ((line = reader.readLine()) != null) {
                List<String> parts = parseCsvLine(line);
                if (parts.isEmpty()) {
                    continue;
                }

                String testName = parts.get(0).trim();
                boolean[] hits = new boolean[methodNames.size()];

                int limit = Math.min(parts.size() - 1, methodNames.size());
                for (int i = 0; i < limit; i++) {
                    String value = parts.get(i + 1).trim();
                    hits[i] = "1".equals(value) || "true".equalsIgnoreCase(value);
                }

                tests.add(new TestCoverage(testName, hits));
            }
        }

        return new CoverageData(methodNames, tests);
    }

    public static Map<String, Double> readImpactProbabilities(Path path) throws IOException {
        Map<String, Double> result = new HashMap<>();

        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String header = reader.readLine();
            if (header == null) {
                return result;
            }

            String line;
            while ((line = reader.readLine()) != null) {
                List<String> parts = parseCsvLine(line);
                if (parts.size() < 6) {
                    continue;
                }

                String owner = parts.get(0).trim();
                String method = parts.get(1).trim();
                double impact = parseDoubleSafe(parts.get(5).trim(), 0.0);

                String key = normalizeImpactKey(owner, method);
                result.merge(key, impact, Math::max);
            }
        }

        return result;
    }

    public static Map<String, Double> readRuntimes(Path path) throws IOException {
        Map<String, Double> result = new LinkedHashMap<>();

        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String header = reader.readLine();
            if (header == null) {
                return result;
            }

            String line;
            while ((line = reader.readLine()) != null) {
                List<String> parts = parseCsvLine(line);
                if (parts.size() < 3) {
                    continue;
                }

                String testName = parts.get(1).trim();
                double runtime = parseDoubleSafe(parts.get(2).trim(), 0.0);
                result.put(testName, runtime);
            }
        }

        return result;
    }

    private static String normalizeImpactKey(String ownerInternal, String method) {
        String owner = ownerInternal.replace("/", ".").replace("$", ".");
        return owner + "#" + method;
    }

    public static String normalizeCoverageKey(String coverageMethod) {
        String value = coverageMethod.trim();

        int colon = value.lastIndexOf(':');
        if (colon >= 0) {
            value = value.substring(0, colon);
        }

        int hash = value.indexOf('#');
        if (hash < 0) {
            return value.replace("$", ".");
        }

        String owner = value.substring(0, hash).replace("$", ".");
        String rest = value.substring(hash + 1);

        int paren = rest.indexOf('(');
        String method = paren >= 0 ? rest.substring(0, paren) : rest;

        return owner + "#" + method;
    }

    private static double parseDoubleSafe(String value, double fallback) {
        try {
            return Double.parseDouble(value);
        } catch (Exception ignored) {
            return fallback;
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

    public static final class CoverageData {
        public final List<String> methodNames;
        public final List<TestCoverage> tests;

        public CoverageData(List<String> methodNames, List<TestCoverage> tests) {
            this.methodNames = methodNames;
            this.tests = tests;
        }
    }

    public static final class TestCoverage {
        public final String name;
        public final boolean[] hits;

        public TestCoverage(String name, boolean[] hits) {
            this.name = name;
            this.hits = hits;
        }
    }
}