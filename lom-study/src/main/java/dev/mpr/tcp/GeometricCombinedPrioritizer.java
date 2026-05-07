package dev.mpr.tcp;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

public class GeometricCombinedPrioritizer {
    private static final double EPS = 1e-6;
    private static final double W_COVERAGE = 0.40;
    private static final double W_IMPACT = 0.45;
    private static final double W_SPEED = 0.15;

    public static List<String> prioritize(
            GeometricDataLoader.CoverageData coverageData,
            Map<String, Double> impactByKey,
            Map<String, Double> runtimeByTest
    ) {
        List<TestScore> scores = computeScores(coverageData, impactByKey, runtimeByTest);

        scores.sort(
                Comparator.comparingDouble(TestScore::priorityScore).reversed()
                        .thenComparing(Comparator.comparingInt(TestScore::coveredMethods).reversed())
                        .thenComparingDouble(TestScore::durationMs)
                        .thenComparing(TestScore::name)
        );

        List<String> order = new ArrayList<>();
        for (TestScore score : scores) {
            order.add(score.name);
        }

        return order;
    }

    private static List<TestScore> computeScores(
            GeometricDataLoader.CoverageData coverageData,
            Map<String, Double> impactByKey,
            Map<String, Double> runtimeByTest
    ) {
        List<TestScore> scores = new ArrayList<>();

        int maxCovered = 0;
        double maxImpact = 0.0;
        double maxLogRuntime = 0.0;

        for (Double runtime : runtimeByTest.values()) {
            maxLogRuntime = Math.max(maxLogRuntime, Math.log(runtime + 1.0));
        }

        for (GeometricDataLoader.TestCoverage test : coverageData.tests) {
            int covered = 0;
            double impact = 0.0;

            for (int i = 0; i < test.hits.length; i++) {
                if (!test.hits[i]) {
                    continue;
                }

                covered++;
                String methodName = coverageData.methodNames.get(i);
                String key = GeometricDataLoader.normalizeCoverageKey(methodName);
                impact += impactByKey.getOrDefault(key, 0.0);
            }

            double runtime = runtimeByTest.getOrDefault(test.name, 0.0);
            double logRuntime = Math.log(runtime + 1.0);

            maxCovered = Math.max(maxCovered, covered);
            maxImpact = Math.max(maxImpact, impact);

            scores.add(new TestScore(test.name, runtime, covered, impact, logRuntime));
        }

        for (TestScore score : scores) {
            double coverageScore = maxCovered > 0
                    ? score.coveredMethods / (double) maxCovered
                    : 0.0;

            double impactScore = maxImpact > 0.0
                    ? score.rawImpact / maxImpact
                    : 0.0;

            double speedScore = maxLogRuntime > 0.0
                    ? 1.0 - (score.logRuntime / maxLogRuntime)
                    : 1.0;

            if (speedScore < 0.0) {
                speedScore = 0.0;
            }

            double priorityScore =
                    Math.pow(Math.max(coverageScore, EPS), W_COVERAGE) *
                    Math.pow(Math.max(impactScore, EPS), W_IMPACT) *
                    Math.pow(Math.max(speedScore, EPS), W_SPEED);

            score.coverageScore = coverageScore;
            score.impactScore = impactScore;
            score.speedScore = speedScore;
            score.priorityScore = priorityScore;
        }

        return scores;
    }

    private static final class TestScore {
        final String name;
        final double durationMs;
        final int coveredMethods;
        final double rawImpact;
        final double logRuntime;

        double coverageScore;
        double impactScore;
        double speedScore;
        double priorityScore;

        TestScore(String name, double durationMs, int coveredMethods, double rawImpact, double logRuntime) {
            this.name = name;
            this.durationMs = durationMs;
            this.coveredMethods = coveredMethods;
            this.rawImpact = rawImpact;
            this.logRuntime = logRuntime;
        }

        String name() {
            return name;
        }

        int coveredMethods() {
            return coveredMethods;
        }

        double durationMs() {
            return durationMs;
        }

        double priorityScore() {
            return priorityScore;
        }
    }
}