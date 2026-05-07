package dev.mpr.tcp;

import java.util.List;

public class BeeSolution {
    public List<String> testOrder;
    public double fitness;
    public int trialsWithoutImprovement;

    public BeeSolution(List<String> testOrder, double fitness, int trialsWithoutImprovement) {
        this.testOrder = testOrder;
        this.fitness = fitness;
        this.trialsWithoutImprovement = trialsWithoutImprovement;
    }
}