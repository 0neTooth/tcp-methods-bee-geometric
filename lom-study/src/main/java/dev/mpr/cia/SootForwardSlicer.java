package dev.mpr.cia;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Deque;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

import soot.ArrayType;
import soot.Body;
import soot.G;
import soot.jimple.IdentityStmt;
import soot.options.Options;
import soot.PrimType;
import soot.RefType;
import soot.Scene;
import soot.SootClass;
import soot.SootMethod;
import soot.Type;
import soot.Unit;
import soot.Value;
import soot.VoidType;
import soot.jimple.ParameterRef;
import soot.toolkits.graph.ExceptionalUnitGraph;

/**
 * Выполняет упрощённый forward slicing: для каждого метода строится CFG,
 * определяется достижимый срез, стартующий от параметров метода, и сохраняется
 * отношение |slice| / |CFG|.
 */
public final class SootForwardSlicer {

    private SootForwardSlicer() {
    }

    public static void main(String[] args) throws IOException {
        if (args.length < 1) {
            System.err.println("Usage: SootForwardSlicer <input-jar-or-dir> [include-file] [output-csv] [classpath-file]");
            System.exit(1);
        }

        String input = args[0];
        List<String> includeFilters = args.length >= 2 && !args[1].isBlank()
                ? readFilters(Path.of(args[1]))
                : Collections.emptyList();
        Path outputCsv = args.length >= 3 && !args[2].isBlank()
                ? Path.of(args[2])
                : null;
        String extraClasspath = args.length >= 4 ? args[3] : null;

        configureSoot(input, extraClasspath);
        Scene.v().loadNecessaryClasses();

        List<SlicingResult> results = new ArrayList<>();
        List<SootClass> classes = new ArrayList<>(Scene.v().getApplicationClasses());
        classes.sort((a, b) -> a.getName().compareTo(b.getName()));

        for (SootClass clazz : classes) {
            String className = clazz.getName();
            if (!includeFilters.isEmpty() && includeFilters.stream().noneMatch(className::startsWith)) {
                continue;
            }
            List<SootMethod> methods = new ArrayList<>(clazz.getMethods());
            methods.sort((a, b) -> a.getSignature().compareTo(b.getSignature()));
            for (SootMethod method : methods) {
                if (!method.isConcrete()) {
                    continue;
                }
                try {
                    Body body = method.retrieveActiveBody();
                    SlicingResult result = analyzeMethod(method, body);
                    results.add(result);
                } catch (RuntimeException ex) {
                    System.err.printf(Locale.ROOT, "[warn] Skip %s: %s%n", method.getSignature(), ex.getMessage());
                }
            }
        }

        results.sort((a, b) -> {
            int owner = a.ownerInternal.compareTo(b.ownerInternal);
            if (owner != 0) {
                return owner;
            }
            int name = a.methodName.compareTo(b.methodName);
            if (name != 0) {
                return name;
            }
            return a.descriptor.compareTo(b.descriptor);
        });

        if (outputCsv != null) {
            Files.createDirectories(outputCsv.getParent());
        }
        try (BufferedWriter writer = outputCsv != null
                ? Files.newBufferedWriter(outputCsv, StandardCharsets.UTF_8)
                : new BufferedWriter(new OutputStreamWriter(System.out, StandardCharsets.UTF_8))) {
            writer.write("owner_internal,method,descriptor,total_units,sliced_units,probability");
            writer.newLine();
            for (SlicingResult result : results) {
                writer.write(result.toCsv());
                writer.newLine();
            }
        }
    }

    private static SlicingResult analyzeMethod(SootMethod method, Body body) {
        int totalUnits = body.getUnits().size();
        if (totalUnits == 0) {
            return new SlicingResult(method, 0, 0);
        }

        ExceptionalUnitGraph graph = new ExceptionalUnitGraph(body);

        Set<Unit> slice = new LinkedHashSet<>();
        Deque<Unit> worklist = new ArrayDeque<>();

        for (Unit unit : body.getUnits()) {
            if (unit instanceof IdentityStmt) {
                Value right = ((IdentityStmt) unit).getRightOp();
                if (right instanceof ParameterRef) {
                    slice.add(unit);
                    worklist.add(unit);
                }
            }
        }

        if (slice.isEmpty()) {
            return new SlicingResult(method, totalUnits, 0);
        }

        while (!worklist.isEmpty()) {
            Unit current = worklist.removeFirst();
            for (Unit successor : graph.getSuccsOf(current)) {
                if (slice.add(successor)) {
                    worklist.addLast(successor);
                }
            }
        }

        return new SlicingResult(method, totalUnits, slice.size());
    }

    private static void configureSoot(String input, String extraClasspath) {
        G.reset();
        Options.v().set_prepend_classpath(true);
        Options.v().set_allow_phantom_refs(true);
        Options.v().set_output_format(Options.output_format_none);
        Options.v().set_whole_program(false);
        Options.v().set_no_bodies_for_excluded(true);
        Options.v().set_keep_line_number(true);
        Options.v().set_keep_offset(true);

        Options.v().set_process_dir(Collections.singletonList(input));

        String classPath = input;
        if (extraClasspath != null && !extraClasspath.isBlank()) {
            classPath = extraClasspath + java.io.File.pathSeparator + classPath;
        }
        String defaultCp = Scene.v().defaultClassPath();
        if (defaultCp != null && !defaultCp.isBlank()) {
            classPath = classPath + java.io.File.pathSeparator + defaultCp;
        }
        Options.v().set_soot_classpath(classPath);
    }

    private static List<String> readFilters(Path file) throws IOException {
        if (!Files.exists(file)) {
            return Collections.emptyList();
        }
        return Files.readAllLines(file, StandardCharsets.UTF_8).stream()
                .map(String::trim)
                .filter(line -> !line.isEmpty() && !line.startsWith("#"))
                .map(SootForwardSlicer::normalizeFilter)
                .collect(Collectors.toList());
    }

    private static String normalizeFilter(String raw) {
        String normalized = raw.replace('/', '.');
        while (normalized.endsWith(".")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return normalized;
    }

    private static final class SlicingResult {
        private final String ownerInternal;
        private final String methodName;
        private final String descriptor;
        private final int totalUnits;
        private final int slicedUnits;

        private SlicingResult(SootMethod method, int totalUnits, int slicedUnits) {
            this.ownerInternal = method.getDeclaringClass().getName().replace('.', '/');
            this.methodName = method.getName();
            this.descriptor = toDescriptor(method);
            this.totalUnits = Math.max(totalUnits, 0);
            this.slicedUnits = Math.min(Math.max(slicedUnits, 0), this.totalUnits);
        }

        private String toCsv() {
            double probability = totalUnits == 0 ? 0.0d : (double) slicedUnits / totalUnits;
            return String.format(
                    Locale.ROOT,
                    "%s,%s,%s,%d,%d,%.6f",
                    CsvUtils.escape(ownerInternal),
                    CsvUtils.escape(methodName),
                    CsvUtils.escape(descriptor),
                    totalUnits,
                    slicedUnits,
                    probability
            );
        }
    }

    private static String toDescriptor(SootMethod method) {
        StringBuilder sb = new StringBuilder();
        sb.append('(');
        for (Type type : method.getParameterTypes()) {
            sb.append(toDescriptor(type));
        }
        sb.append(')');
        sb.append(toDescriptor(method.getReturnType()));
        return sb.toString();
    }

    private static String toDescriptor(Type type) {
        if (type instanceof RefType) {
            RefType ref = (RefType) type;
            return "L" + ref.getClassName().replace('.', '/') + ";";
        }
        if (type instanceof ArrayType) {
            ArrayType arrayType = (ArrayType) type;
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < arrayType.numDimensions; i++) {
                sb.append('[');
            }
            sb.append(toDescriptor(arrayType.baseType));
            return sb.toString();
        }
        if (type instanceof PrimType) {
            return primitiveDescriptor((PrimType) type);
        }
        if (type instanceof VoidType) {
            return "V";
        }
        // fallback for uncommon types
        return "L" + type.toString().replace('.', '/') + ";";
    }

    private static String primitiveDescriptor(PrimType type) {
        String name = type.toString();
        switch (name) {
            case "boolean":
                return "Z";
            case "byte":
                return "B";
            case "char":
                return "C";
            case "short":
                return "S";
            case "int":
                return "I";
            case "long":
                return "J";
            case "float":
                return "F";
            case "double":
                return "D";
            default:
                throw new IllegalArgumentException("Unknown primitive type: " + name);
        }
    }
}
