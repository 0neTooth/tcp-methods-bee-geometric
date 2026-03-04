package dev.mpr.cia;

import java.util.Locale;

/**
 * Holds instruction counts and change ratio for a single method.
 */
final class MethodMetrics {

    private final MethodId methodId;
    private final int totalInstructions;
    private final int changedInstructions;

    MethodMetrics(MethodId methodId, int totalInstructions, int changedInstructions) {
        if (totalInstructions < 0) {
            throw new IllegalArgumentException("totalInstructions must be >= 0");
        }
        if (changedInstructions < 0) {
            throw new IllegalArgumentException("changedInstructions must be >= 0");
        }
        this.methodId = methodId;
        this.totalInstructions = totalInstructions;
        this.changedInstructions = Math.min(changedInstructions, totalInstructions);
    }

    MethodId methodId() {
        return methodId;
    }

    int totalInstructions() {
        return totalInstructions;
    }

    int changedInstructions() {
        return changedInstructions;
    }

    double roc() {
        if (totalInstructions == 0) {
            return 0.0d;
        }
        return changedInstructions / (double) totalInstructions;
    }

    String toCsvLine() {
        return String.format(
                Locale.ROOT,
                "%s,%s,%s,%d,%d,%.6f",
                CsvUtils.escape(methodId.ownerInternalName()),
                CsvUtils.escape(methodId.name()),
                CsvUtils.escape(methodId.descriptor()),
                totalInstructions,
                changedInstructions,
                roc()
        );
    }
}
