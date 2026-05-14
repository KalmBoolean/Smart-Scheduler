from Surrogate import *
from MonteCarlo import *
import sqlite3

class Optimiser:
    popSize = 50
    top    = 20
    def __init__(self):
        self.objSurr  = Objectivesurrogate()
        self.perfSurr = PerformanceSurrogate()
        self.schedGen      = SchedGen()
        self.population     = []
        self.runCount      = 0

    def run(self, tasks):
        self.runCount += 1
        self.objSurr.Train()
        self.perfSurr.Train()

        if not self.population:
            
            self.conn = sqlite3.connect("objective.db")
            population = self.conn.execute("SELECT * FROM tasks").fetchall()

            if len(population) < self.popSize:
                population = [
                    self.schedGen.generate(tasks)
                    for _ in range(self.popSize)
                ]
        else:
            population = self.Evolve(tasks)

        for schedule in population:
            objScore  = self.objSurr.Predict(schedule)
            perfScore = self.perfSurr.Predict(schedule)
            schedule.fitness = (objScore + perfScore) / 2

        population.sort(key=lambda s: s.fitness, reverse=True)
        best = population[0].fitness

        topScheds    = population[:self.top]
        mcScores = {}

        for schedule in topScheds:
            mc = MonteCarloStuff(schedule)
            mcScores[id(schedule)] = mc

            self.schedGen.StoreObjectiveTrainingExample(schedule, mc)

        bestSched = max(topScheds, key=lambda s: mcScores[id(s)])

        self.population = population

        mc_display = {id(s): -mcScores[id(s)] for s in topScheds}
        mc_lo      = min(mc_display.values())
        mc_hi      = max(mc_display.values())
        mc_range   = mc_hi - mc_lo or 1

        candidates = [
            {
                "norm":    1.0 - (mc_display[id(s)] - mc_lo) / mc_range,
                "is_best": s is bestSched,
                "real":    mc_display[id(s)],
                "tasks":   [t.name for t in s.tasks],
            }
            for s in topScheds
        ]

        return {
            "run":           self.runCount,
            "pop_size":      len(population),
            "surr_best":     best,
            "mc_best":       mc_display[id(bestSched)], 
            "candidates":    candidates,
            "best_schedule": bestSched,
            "population":    population,
        }

    def Evolve(self, tasks):
        
        prev = self.population
        children = []

        def PickRandomBestFit():
            contenders = random.sample(prev, min(3, len(prev)))
            return max(contenders, key=lambda s: s.fitness)

        while len(children) < self.popSize:
            a = PickRandomBestFit()
            b = PickRandomBestFit()
            child  = self.schedGen.Crossover(a, b)
            child  = self.schedGen.Mutate(child)
            children.append(child)

        # Replace the last 10 % with fresh random schedules for better exploration ig
        n_fresh = max(1, self.popSize // 10)
        for i in range(n_fresh):
            children[-(i + 1)] = self.schedGen.generate(tasks)

        return children

    def reset(self):
        self.population = []