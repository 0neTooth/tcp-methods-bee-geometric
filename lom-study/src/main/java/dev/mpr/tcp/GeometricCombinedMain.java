package dev.mpr.tcp;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

public class GeometricCombinedMain {
    public static void main(String[] args) throws Exception {
        if (args.length < 4) {
            System.err.println("Usage: GeometricCombinedMain <coverage_matrix.csv> <impact_probabilities.csv> <testMap.csv> <output_order.csv>");
            System.exit(1);
        }

        Path coveragePath = Paths.get(args[0]);
        Path impactPath = Paths.get(args[1]);
        Path testMapPath = Paths.get(args[2]);
        Path outputPath = Paths.get(args[3]);

        GeometricDataLoader.CoverageData coverageData = GeometricDataLoader.readCoverageMatrix(coveragePath);
        Map<String, Double> impactByKey = GeometricDataLoader.readImpactProbabilities(impactPath);
        Map<String, Double> runtimeByTest = GeometricDataLoader.readRuntimes(testMapPath);

        List<String> order = GeometricCombinedPrioritizer.prioritize(
                coverageData,
                impactByKey,
                runtimeByTest
        );

        OrderWriter.write(outputPath, order);

        System.out.println("[done] Geometric combined order saved to " + outputPath);
        System.out.println("[info] tests=" + coverageData.tests.size() + ", methods=" + coverageData.methodNames.size());
    }
}