package dev.mpr.gzoltar;

import com.gzoltar.internal.core.AgentConfigs;
import com.gzoltar.internal.core.instr.granularity.GranularityLevel;
import com.gzoltar.internal.core.model.Node;
import com.gzoltar.internal.core.model.NodeType;
import com.gzoltar.internal.core.model.Transaction;
import com.gzoltar.internal.core.runtime.Probe;
import com.gzoltar.internal.core.runtime.ProbeGroup;
import com.gzoltar.internal.core.spectrum.Spectrum;
import com.gzoltar.internal.core.spectrum.SpectrumReader;
import com.gzoltar.internal.javassist.CannotCompileException;
import com.gzoltar.internal.javassist.ClassPool;
import com.gzoltar.internal.javassist.CtClass;
import com.gzoltar.internal.javassist.CtConstructor;
import com.gzoltar.internal.javassist.NotFoundException;
import com.gzoltar.internal.org.apache.commons.lang3.tuple.Pair;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

/**
 * Utility that reads a GZoltar {@code gzoltar.ser} file and exports a test-by-method coverage matrix.
 */
public final class GzoltarSerExporter {

    private static final class MethodProbeInfo {
        private final String id;
        private final String probeGroupHash;
        private final int arrayIndex;
        private final String nodeName;
        private final String nodeNameWithLine;
        private final int lineNumber;
        private final NodeType nodeType;

        private MethodProbeInfo(String id,
                                String probeGroupHash,
                                int arrayIndex,
                                String nodeName,
                                String nodeNameWithLine,
                                int lineNumber,
                                NodeType nodeType) {
            this.id = id;
            this.probeGroupHash = probeGroupHash;
            this.arrayIndex = arrayIndex;
            this.nodeName = nodeName;
            this.nodeNameWithLine = nodeNameWithLine;
            this.lineNumber = lineNumber;
            this.nodeType = nodeType;
        }

        private String id() {
            return id;
        }

        private String probeGroupHash() {
            return probeGroupHash;
        }

        private int arrayIndex() {
            return arrayIndex;
        }

        private String nodeName() {
            return nodeName;
        }

        private String nodeNameWithLine() {
            return nodeNameWithLine;
        }

        private int lineNumber() {
            return lineNumber;
        }

        private NodeType nodeType() {
            return nodeType;
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) {
                return true;
            }
            if (!(obj instanceof MethodProbeInfo)) {
                return false;
            }
            MethodProbeInfo other = (MethodProbeInfo) obj;
            return arrayIndex == other.arrayIndex
                    && lineNumber == other.lineNumber
                    && Objects.equals(id, other.id)
                    && Objects.equals(probeGroupHash, other.probeGroupHash)
                    && Objects.equals(nodeName, other.nodeName)
                    && Objects.equals(nodeNameWithLine, other.nodeNameWithLine)
                    && nodeType == other.nodeType;
        }

        @Override
        public int hashCode() {
            return Objects.hash(id, probeGroupHash, arrayIndex, nodeName, nodeNameWithLine, lineNumber, nodeType);
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("Usage: java -jar lom-study.jar <gzoltar.ser> <buildLocation> <outputDir> [classpathFileOrString]");
            System.exit(1);
        }

        Path serPath = Paths.get(args[0]).toAbsolutePath();
        Path buildLocation = Paths.get(args[1]).toAbsolutePath();
        Path outputDir = Paths.get(args[2]).toAbsolutePath();
        String classpathArg = args.length >= 4 ? args[3] : null;

        if (!Files.isRegularFile(serPath)) {
            System.err.printf(Locale.ROOT, "gzoltar.ser not found: %s%n", serPath);
            System.exit(2);
        }
        if (!Files.isDirectory(buildLocation)) {
            System.err.printf(Locale.ROOT, "Build location not found: %s%n", buildLocation);
            System.exit(3);
        }
        Files.createDirectories(outputDir);

        List<String> additionalClassPaths = resolveClassPathEntries(classpathArg);
        configureClassPool(buildLocation, additionalClassPaths);

        Spectrum spectrum = readSpectrum(serPath, buildLocation);
        ExportData exportData = buildExportData(spectrum);
        writeMethodsCsv(outputDir.resolve("methods.csv"), exportData);
        writeMatrixCsv(outputDir.resolve("matrix.csv"), exportData);
    }

    private static void configureClassPool(Path buildLocation, List<String> extraPaths) throws Exception {
        ClassPool pool = ClassPool.getDefault();
        pool.appendSystemPath();
        pool.insertClassPath(buildLocation.toString());
        if (extraPaths != null) {
            for (String entry : extraPaths) {
                if (entry != null && !entry.isBlank()) {
                    pool.insertClassPath(entry.trim());
                }
            }
        }
        installGzoltarAccessStubs(pool);
    }

    private static void installGzoltarAccessStubs(ClassPool pool) throws CannotCompileException {
        String[] syntheticNames = {
                "java.lang.UnknownError$$gzoltarAccess",
                "java.lang.Throwable$$gzoltarAccess"
        };
        for (String name : syntheticNames) {
            try {
                pool.get(name);
            } catch (NotFoundException e) {
                CtClass stub = pool.makeClass(name);
                CtConstructor ctor = new CtConstructor(new CtClass[0], stub);
                ctor.setBody("{}");
                stub.addConstructor(ctor);
                stub.freeze();
            }
        }
    }

    private static List<String> resolveClassPathEntries(String classpathArg) throws IOException {
        if (classpathArg == null || classpathArg.isBlank()) {
            return List.of();
        }
        Path potentialFile = Paths.get(classpathArg);
        if (Files.exists(potentialFile) && Files.isRegularFile(potentialFile)) {
            List<String> lines = Files.readAllLines(potentialFile);
            for (String line : lines) {
                if (line.startsWith("cp_test=")) {
                    String cp = line.substring("cp_test=".length());
                    return splitClassPath(cp);
                }
            }
            // fallback: treat entire file as classpath string (first line)
            if (!lines.isEmpty()) {
                return splitClassPath(lines.get(0));
            }
        }
        return splitClassPath(classpathArg);
    }

    private static List<String> splitClassPath(String cp) {
        if (cp == null || cp.isBlank()) {
            return List.of();
        }
        String[] parts = cp.split(java.io.File.pathSeparator);
        List<String> result = new ArrayList<>(parts.length);
        for (String part : parts) {
            if (!part.isBlank()) {
                result.add(part.trim());
            }
        }
        return result;
    }

    private static Spectrum readSpectrum(Path serPath, Path buildLocation) throws Exception {
        AgentConfigs configs = new AgentConfigs();
        configs.setBuildLocation(buildLocation.toString());
        configs.setGranularity(GranularityLevel.METHOD.name());
        configs.setIncludes("*");
        configs.setExcludes("java.*");
        try (InputStream in = Files.newInputStream(serPath)) {
            SpectrumReader reader = new SpectrumReader("export", configs, in);
            if (!reader.read()) {
                throw new IllegalStateException("Unable to read spectrum from " + serPath);
            }
            return reader.getSpectrum();
        }
    }

    private static final class ExportData {
        private final List<MethodProbeInfo> methods;
        private final List<Transaction> transactions;
        private final Map<String, List<MethodProbeInfo>> methodsByGroup;
        private final Map<MethodProbeInfo, Integer> methodIndexByInfo;

        private ExportData(List<MethodProbeInfo> methods,
                           List<Transaction> transactions,
                           Map<String, List<MethodProbeInfo>> methodsByGroup,
                           Map<MethodProbeInfo, Integer> methodIndexByInfo) {
            this.methods = methods;
            this.transactions = transactions;
            this.methodsByGroup = methodsByGroup;
            this.methodIndexByInfo = methodIndexByInfo;
        }

        private List<MethodProbeInfo> methods() {
            return methods;
        }

        private List<Transaction> transactions() {
            return transactions;
        }

        private Map<String, List<MethodProbeInfo>> methodsByGroup() {
            return methodsByGroup;
        }

        private Map<MethodProbeInfo, Integer> methodIndexByInfo() {
            return methodIndexByInfo;
        }
    }

    private static ExportData buildExportData(Spectrum spectrum) {
        List<MethodProbeInfo> methods = new ArrayList<>();
        Map<String, List<MethodProbeInfo>> methodsByGroup = new LinkedHashMap<>();

        for (ProbeGroup group : spectrum.getProbeGroups()) {
            List<MethodProbeInfo> groupMethods = new ArrayList<>();
            for (Probe probe : group.getProbes()) {
                Node node = probe.getNode();
                if (node == null) {
                    continue;
                }
                NodeType nodeType = node.getNodeType();
                if (nodeType != NodeType.METHOD) {
                    continue;
                }
                String nodeName = node.getName();
                if (!isSupportedMethod(nodeName)) {
                    continue;
                }
                MethodProbeInfo info = new MethodProbeInfo(
                        "m" + methods.size(),
                        group.getHash(),
                        probe.getArrayIndex(),
                        nodeName,
                        node.getNameWithLineNumber(),
                        node.getLineNumber(),
                        nodeType
                );
                methods.add(info);
                groupMethods.add(info);
            }
            if (!groupMethods.isEmpty()) {
                methodsByGroup.put(group.getHash(), groupMethods);
            }
        }

        // stable order by method id
        methods.sort(Comparator.comparing(MethodProbeInfo::id));
        Map<String, List<MethodProbeInfo>> sortedByGroup = new LinkedHashMap<>();
        Map<MethodProbeInfo, Integer> indexByInfo = new HashMap<>();
        for (int i = 0; i < methods.size(); i++) {
            MethodProbeInfo info = methods.get(i);
            sortedByGroup.computeIfAbsent(info.probeGroupHash, k -> new ArrayList<>()).add(info);
            indexByInfo.put(info, i);
        }

        return new ExportData(methods, spectrum.getTransactions(), sortedByGroup, indexByInfo);
    }

    private static boolean isSupportedMethod(String nodeName) {
        if (nodeName == null || nodeName.isBlank()) {
            return false;
        }
        if (nodeName.startsWith("java.")) {
            return false;
        }
        if (nodeName.contains("$$gzoltarAccess")) {
            return false;
        }
        return true;
    }

    private static void writeMethodsCsv(Path methodsCsv, ExportData exportData) throws IOException {
        try (BufferedWriter writer = Files.newBufferedWriter(methodsCsv, StandardCharsets.UTF_8)) {
            writer.write("method_id,method_name,method_name_with_line,line,probe_group,array_index");
            writer.newLine();
            for (MethodProbeInfo info : exportData.methods()) {
                writer.write(joinCsv(
                        info.id(),
                        info.nodeName(),
                        info.nodeNameWithLine(),
                        Integer.toString(info.lineNumber()),
                        info.probeGroupHash(),
                        Integer.toString(info.arrayIndex())
                ));
                writer.newLine();
            }
        }
    }

    private static void writeMatrixCsv(Path matrixCsv, ExportData exportData) throws IOException {
        List<MethodProbeInfo> methods = exportData.methods();
        List<Transaction> transactions = exportData.transactions();
        Map<String, List<MethodProbeInfo>> methodsByGroup = exportData.methodsByGroup();
        Map<MethodProbeInfo, Integer> methodIndexByInfo = exportData.methodIndexByInfo();

        try (BufferedWriter writer = Files.newBufferedWriter(matrixCsv, StandardCharsets.UTF_8)) {
            // header
            StringBuilder header = new StringBuilder();
            header.append("test");
            for (MethodProbeInfo info : methods) {
                header.append(',').append(csv(info.id()));
            }
            writer.write(header.toString());
            writer.newLine();

            for (Transaction tx : transactions) {
                boolean[] row = new boolean[methods.size()];
                Map<String, Pair<String, boolean[]>> activity = tx.getActivity();
                if (activity != null) {
                    for (Map.Entry<String, Pair<String, boolean[]>> entry : activity.entrySet()) {
                        String groupHash = entry.getKey();
                        boolean[] hits = entry.getValue().getRight();
                        List<MethodProbeInfo> groupMethods = methodsByGroup.get(groupHash);
                        if (groupMethods == null || hits == null) {
                            continue;
                        }
                        for (MethodProbeInfo info : groupMethods) {
                            int idx = info.arrayIndex();
                            if (idx >= 0 && idx < hits.length && hits[idx]) {
                                Integer globalIndex = methodIndexByInfo.get(info);
                                if (globalIndex != null) {
                                    row[globalIndex] = true;
                                }
                            }
                        }
                    }
                }

                StringBuilder line = new StringBuilder();
                line.append(csv(tx.getName()));
                for (boolean value : row) {
                    line.append(',').append(value ? '1' : '0');
                }
                writer.write(line.toString());
                writer.newLine();
            }
        }
    }

    private static String joinCsv(String... values) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < values.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(csv(values[i]));
        }
        return sb.toString();
    }

    private static String csv(String value) {
        if (value == null) {
            return "";
        }
        boolean needsQuote = value.contains(",") || value.contains("\"") || value.contains("\n");
        String escaped = value.replace("\"", "\"\"");
        if (needsQuote) {
            return '"' + escaped + '"';
        }
        return escaped;
    }
}
