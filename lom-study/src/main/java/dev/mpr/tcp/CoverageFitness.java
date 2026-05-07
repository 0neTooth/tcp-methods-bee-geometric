package dev.mpr.tcp;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class CoverageFitness {
    public static double calculate(List<String> orderedTests, Map<String, Set<Integer>> testCoverage, int totalItems) {
        if (orderedTests == null || orderedTests.isEmpty()) return 0.0;
        if (testCoverage == null || testCoverage.isEmpty() || totalItems <= 0) return 0.0;

        Set<Integer> covered = new HashSet<>();
        double fitness = 0.0;

        for (int i = 0; i < orderedTests.size(); i++) {
            String test = orderedTests.get(i);
            Set<Integer> items = testCoverage.get(test);
            if (items == null || items.isEmpty()) continue;

            int newlyCovered = 0;
            for (Integer item : items) {
                if (!covered.contains(item)) {
                    newlyCovered++;
                }
            }

            covered.addAll(items);

            double progress = covered.size() / (double) totalItems;
            double earlyGain = newlyCovered / (double) (i + 1);

            fitness += progress + earlyGain;
        }

        return fitness;
    }
}