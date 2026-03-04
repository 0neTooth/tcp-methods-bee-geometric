package dev.mpr.cia;

import org.objectweb.asm.ClassReader;
import org.objectweb.asm.Type;
import org.objectweb.asm.tree.AbstractInsnNode;
import org.objectweb.asm.tree.ClassNode;
import org.objectweb.asm.tree.FieldInsnNode;
import org.objectweb.asm.tree.FrameNode;
import org.objectweb.asm.tree.IincInsnNode;
import org.objectweb.asm.tree.InsnList;
import org.objectweb.asm.tree.IntInsnNode;
import org.objectweb.asm.tree.InvokeDynamicInsnNode;
import org.objectweb.asm.tree.LabelNode;
import org.objectweb.asm.tree.LdcInsnNode;
import org.objectweb.asm.tree.LineNumberNode;
import org.objectweb.asm.tree.LookupSwitchInsnNode;
import org.objectweb.asm.tree.MethodInsnNode;
import org.objectweb.asm.tree.MethodNode;
import org.objectweb.asm.tree.MultiANewArrayInsnNode;
import org.objectweb.asm.tree.TableSwitchInsnNode;
import org.objectweb.asm.tree.TypeInsnNode;
import org.objectweb.asm.tree.VarInsnNode;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Computes method-level ROC metrics by comparing two sets of compiled classes.
 */
final class AsmRocAnalyzer {

    private AsmRocAnalyzer() {
    }

    static List<MethodMetrics> analyze(Path buggyRoot, Path fixedRoot, Collection<String> includePrefixes) throws IOException {
        Map<MethodId, MethodSummary> buggy = readClasses(buggyRoot, includePrefixes);
        Map<MethodId, MethodSummary> fixed = readClasses(fixedRoot, includePrefixes);

        List<MethodMetrics> results = new ArrayList<>();
        for (Map.Entry<MethodId, MethodSummary> entry : fixed.entrySet()) {
            MethodId methodId = entry.getKey();
            MethodSummary fixedSummary = entry.getValue();
            MethodSummary buggySummary = buggy.get(methodId);
            int changed;
            if (buggySummary == null) {
                changed = fixedSummary.instructionKeys.size();
            } else {
                changed = diff(fixedSummary.instructionKeys, buggySummary.instructionKeys);
            }
            results.add(new MethodMetrics(methodId, fixedSummary.instructionKeys.size(), changed));
        }

        // Include deleted methods (present in buggy but removed in fixed) with total=0 to make tracking easier.
        for (MethodId deleted : difference(buggy.keySet(), fixed.keySet())) {
            MethodSummary summary = buggy.get(deleted);
            results.add(new MethodMetrics(deleted, summary.instructionKeys.size(), summary.instructionKeys.size()));
        }

        results.sort((a, b) -> {
            int ownerCmp = a.methodId().ownerInternalName().compareTo(b.methodId().ownerInternalName());
            if (ownerCmp != 0) {
                return ownerCmp;
            }
            int nameCmp = a.methodId().name().compareTo(b.methodId().name());
            if (nameCmp != 0) {
                return nameCmp;
            }
            return a.methodId().descriptor().compareTo(b.methodId().descriptor());
        });
        return results;
    }

    private static Set<MethodId> difference(Set<MethodId> left, Set<MethodId> right) {
        if (left.isEmpty()) {
            return Collections.emptySet();
        }
        Set<MethodId> copy = new HashSet<>(left);
        copy.removeAll(right);
        return copy;
    }

    private static Map<MethodId, MethodSummary> readClasses(Path root, Collection<String> includePrefixes) throws IOException {
        if (root == null) {
            return Map.of();
        }
        Map<MethodId, MethodSummary> methods = new HashMap<>();
        Files.walkFileTree(root, EnumSet.noneOf(java.nio.file.FileVisitOption.class), Integer.MAX_VALUE,
                new SimpleFileVisitor<>() {
                    @Override
                    public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                        if (file.getFileName().toString().endsWith(".class")) {
                            readClass(file, methods, includePrefixes);
                        }
                        return FileVisitResult.CONTINUE;
                    }
                });
        return methods;
    }

    private static void readClass(Path classFile, Map<MethodId, MethodSummary> out, Collection<String> includePrefixes) throws IOException {
        try (InputStream in = Files.newInputStream(classFile)) {
            ClassReader reader = new ClassReader(in);
            ClassNode node = new ClassNode();
            reader.accept(node, ClassReader.SKIP_FRAMES);

            String internalName = node.name;
            if (!includePrefixes.isEmpty()
                    && includePrefixes.stream().noneMatch(prefix -> matchesPrefix(internalName, prefix))) {
                return;
            }

            @SuppressWarnings("unchecked")
            List<MethodNode> methods = (List<MethodNode>) node.methods;
            for (MethodNode method : methods) {
                MethodId id = new MethodId(internalName, method.name, method.desc);
                MethodSummary summary = MethodSummary.from(method);
                out.put(id, summary);
            }
        }
    }

    private static boolean matchesPrefix(String internalName, String prefix) {
        if (internalName.startsWith(prefix)) {
            return true;
        }
        if (!prefix.endsWith("/")) {
            return internalName.equals(prefix)
                    || internalName.startsWith(prefix + "/")
                    || internalName.startsWith(prefix + "$");
        }
        if (prefix.length() <= 1) {
            return true;
        }
        String withoutSlash = prefix.substring(0, prefix.length() - 1);
        return internalName.equals(withoutSlash)
                || internalName.startsWith(withoutSlash + "$");
    }

    private static int diff(List<String> current, List<String> previous) {
        int min = Math.min(current.size(), previous.size());
        int diff = Math.abs(current.size() - previous.size());
        for (int i = 0; i < min; i++) {
            if (!Objects.equals(current.get(i), previous.get(i))) {
                diff++;
            }
        }
        return diff;
    }

    private static final class MethodSummary {
        private final List<String> instructionKeys;

        private MethodSummary(List<String> instructionKeys) {
            this.instructionKeys = instructionKeys;
        }

        private static MethodSummary from(MethodNode method) {
            InsnList insns = method.instructions;
            if (insns == null || insns.size() == 0) {
                return new MethodSummary(Collections.emptyList());
            }
            List<String> result = new ArrayList<>(insns.size());
            for (AbstractInsnNode insn : insns) {
                if (!isRealInstruction(insn)) {
                    continue;
                }
                result.add(instructionKey(insn));
            }
            return new MethodSummary(result);
        }

        private static boolean isRealInstruction(AbstractInsnNode insn) {
            if (insn == null) {
                return false;
            }
            if (insn instanceof LabelNode
                    || insn instanceof LineNumberNode
                    || insn instanceof FrameNode) {
                return false;
            }
            return insn.getOpcode() >= 0;
        }

        private static String instructionKey(AbstractInsnNode insn) {
            StringBuilder key = new StringBuilder();
            key.append(insn.getOpcode());
            switch (insn.getType()) {
                case AbstractInsnNode.INT_INSN:
                    key.append(':').append(((IntInsnNode) insn).operand);
                    break;
                case AbstractInsnNode.VAR_INSN:
                    key.append(':').append(((VarInsnNode) insn).var);
                    break;
                case AbstractInsnNode.TYPE_INSN:
                    key.append(':').append(((TypeInsnNode) insn).desc);
                    break;
                case AbstractInsnNode.FIELD_INSN:
                    FieldInsnNode fieldInsn = (FieldInsnNode) insn;
                    key.append(':').append(fieldInsn.owner).append('.').append(fieldInsn.name).append(':').append(fieldInsn.desc);
                    break;
                case AbstractInsnNode.METHOD_INSN:
                    MethodInsnNode methodInsn = (MethodInsnNode) insn;
                    key.append(':').append(methodInsn.owner).append('.').append(methodInsn.name).append(methodInsn.desc);
                    key.append(':').append(methodInsn.itf ? "itf" : "cls");
                    break;
                case AbstractInsnNode.INVOKE_DYNAMIC_INSN:
                    InvokeDynamicInsnNode indy = (InvokeDynamicInsnNode) insn;
                    key.append(':').append(indy.name).append(indy.desc);
                    key.append(':').append(indy.bsm.getOwner()).append('.')
                            .append(indy.bsm.getName()).append(indy.bsm.getDesc());
                    break;
                case AbstractInsnNode.JUMP_INSN:
                    key.append(":jump");
                    break;
                case AbstractInsnNode.LDC_INSN:
                    key.append(':').append(stringify(((LdcInsnNode) insn).cst));
                    break;
                case AbstractInsnNode.IINC_INSN:
                    IincInsnNode iinc = (IincInsnNode) insn;
                    key.append(':').append(iinc.var).append(':').append(iinc.incr);
                    break;
                case AbstractInsnNode.TABLESWITCH_INSN:
                    TableSwitchInsnNode ts = (TableSwitchInsnNode) insn;
                    key.append(':').append(ts.min).append(':').append(ts.max);
                    break;
                case AbstractInsnNode.LOOKUPSWITCH_INSN:
                    LookupSwitchInsnNode ls = (LookupSwitchInsnNode) insn;
                    key.append(':').append(ls.keys);
                    break;
                case AbstractInsnNode.MULTIANEWARRAY_INSN:
                    MultiANewArrayInsnNode mna = (MultiANewArrayInsnNode) insn;
                    key.append(':').append(mna.desc).append(':').append(mna.dims);
                    break;
                default:
                    // other instruction types do not carry extra payload
                    break;
            }
            return key.toString();
        }

        private static String stringify(Object cst) {
            if (cst == null) {
                return "null";
            }
            if (cst instanceof String) {
                return '"' + ((String) cst).replace("\"", "\\\"") + '"';
            }
            if (cst instanceof Type) {
                return ((Type) cst).getDescriptor();
            }
            return cst.getClass().getName() + ":" + cst;
        }
    }
}
