package dev.mpr.tcp;

import java.util.*;

public class BeeColonyPrioritizer {

    public static List<String> prioritize(
            List<String> testNames,
            Map<String, Set<Integer>> testCoverage,
            int totalItems,
            int populationSize,
            int maxIterations,
            int scoutLimit,
            long seed
    ) {
        Random random = new Random(seed);
        List<BeeSolution> population = new ArrayList<>();

        for (int i = 0; i < populationSize; i++) {
            List<String> order = shuffle(testNames, random);
            double fitness = CoverageFitness.calculate(order, testCoverage, totalItems);
            population.add(new BeeSolution(order, fitness, 0));
        }

        for (int iteration = 0; iteration < maxIterations; iteration++) {
            for (BeeSolution solution : population) {
                improveSolution(solution, testCoverage, totalItems, random);
            }

            List<BeeSolution> selected = selectSolutions(population, random, populationSize / 2);
            for (BeeSolution solution : selected) {
                improveSolution(solution, testCoverage, totalItems, random);
            }

            for (int i = 0; i < population.size(); i++) {
                if (population.get(i).trialsWithoutImprovement >= scoutLimit) {
                    List<String> newOrder = shuffle(testNames, random);
                    double fitness = CoverageFitness.calculate(newOrder, testCoverage, totalItems);
                    population.set(i, new BeeSolution(newOrder, fitness, 0));
                }
            }
        }

        return population.stream()
                .max(Comparator.comparingDouble(x -> x.fitness))
                .orElseThrow()
                .testOrder;
    }

    public static List<String> prioritize(
            List<String> testNames,
            Map<String, Set<Integer>> testCoverage,
            int totalItems
    ) {
        return prioritize(testNames, testCoverage, totalItems, 30, 200, 20, 38L);
    }

    private static void improveSolution(
            BeeSolution solution,
            Map<String, Set<Integer>> testCoverage,
            int totalItems,
            Random random
    ) {
        List<String> candidateOrder = mutate(solution.testOrder, random);
        double candidateFitness = CoverageFitness.calculate(candidateOrder, testCoverage, totalItems);

        if (candidateFitness > solution.fitness) {
            solution.testOrder = candidateOrder;
            solution.fitness = candidateFitness;
            solution.trialsWithoutImprovement = 0;
        } else {
            solution.trialsWithoutImprovement++;
        }
    }

    private static List<BeeSolution> selectSolutions(
            List<BeeSolution> population,
            Random random,
            int count
    ) {
        double totalFitness = population.stream().mapToDouble(x -> x.fitness).sum();

        if (totalFitness <= 0.0) {
            List<BeeSolution> shuffled = new ArrayList<>(population);
            Collections.shuffle(shuffled, random);
            return shuffled.subList(0, Math.min(count, shuffled.size()));
        }

        List<BeeSolution> selected = new ArrayList<>();

        for (int i = 0; i < count; i++) {
            double r = random.nextDouble() * totalFitness;
            double cumulative = 0.0;

            for (BeeSolution solution : population) {
                cumulative += solution.fitness;
                if (cumulative >= r) {
                    selected.add(solution);
                    break;
                }
            }
        }

        return selected;
    }

    private static List<String> mutate(List<String> order, Random random) {
        List<String> result = new ArrayList<>(order);

        if (result.size() < 2) return result;

        int mutationType = random.nextInt(2);

        if (mutationType == 0) {
            int i = random.nextInt(result.size());
            int j = random.nextInt(result.size());
            Collections.swap(result, i, j);
        } else {
            int from = random.nextInt(result.size());
            int to = random.nextInt(result.size());
            String item = result.remove(from);
            result.add(to, item);
        }

        return result;
    }

    private static List<String> shuffle(List<String> source, Random random) {
        List<String> result = new ArrayList<>(source);
        for (int i = result.size() - 1; i > 0; i--) {
            int j = random.nextInt(i + 1);
            Collections.swap(result, i, j);
        }
        return result;
    }
}