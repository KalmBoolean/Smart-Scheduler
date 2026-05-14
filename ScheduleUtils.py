#ScheduleUtils.py

from DNAEncoder import *
import torch as tc
import random
import sqlite3
from datetime import datetime


class Schedule():
    def __init__(self, tasks=None):
        self.tasks           = tasks or []
        self.totalDurn       = 0
        self.avgPrior        = 0
        self.maxDedline      = 0
        self.type1Sum        = 0
        self.type2Sum        = 0
        self.weightedPriority = 0
        self.switchingCost   = 0
        self.cumulativeTime  = 0
        self.fitness = 0
    def encodeAsTensor(self):
        self.totalDurn  = sum(t.duration for t in self.tasks)
        self.avgPrior   = sum(t.priority for t in self.tasks) / len(self.tasks)
        self.maxDedline = max(datetime.fromisoformat(t.deadLine).timestamp()
                              for t in self.tasks)
        self.type1Sum   = sum(1 for t in self.tasks if t.type == TaskType.Proffessional)
        self.type2Sum   = sum(1 for t in self.tasks if t.type == TaskType.Classical)

        self.weightedPriority = 0
        self.switchingCost    = 0
        self.cumulativeTime   = 0

        for i, t in enumerate(self.tasks):
            self.weightedPriority += t.priority / (i + 1)
            if i > 0:
                self.switchingCost += abs(t.cognitive_load -
                                         self.tasks[i-1].cognitive_load)
            self.cumulativeTime += t.duration * (i + 1)  # position-weighted

        return tc.tensor([
            self.totalDurn,
            self.avgPrior,
            self.weightedPriority,
            self.switchingCost,
            self.cumulativeTime,
            self.maxDedline,
            self.type1Sum,
            self.type2Sum
        ], dtype=tc.float32)


def _store(db_path, schedule, fitness):
    features = (
        schedule.totalDurn,
        schedule.avgPrior,
        schedule.weightedPriority,
        schedule.switchingCost,
        schedule.cumulativeTime,
        schedule.maxDedline,
        schedule.type1Sum,
        schedule.type2Sum,
        fitness
    )
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            totalDuration    REAL NOT NULL,
            avgPriority      REAL NOT NULL,
            weightedPriority REAL NOT NULL,
            switchingCost    REAL NOT NULL,
            cumulativeTime   REAL NOT NULL,
            Maxdeadline      REAL NOT NULL,
            type1Sum         REAL NOT NULL,
            type2Sum         REAL NOT NULL,
            fitness          REAL NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO tasks (totalDuration, avgPriority, weightedPriority,"
        " switchingCost, cumulativeTime, Maxdeadline, type1Sum, type2Sum, fitness)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        features
    )
    conn.commit()
    conn.close()


class SchedGen():
    def __init__(self):
        self.w_priority = 3
        self.w_deadline = 1
        self.w_duration = 0.5

    def score(self, t):
        now              = datetime.now()
        deadline         = datetime.fromisoformat(t.deadLine)
        hours_remaining  = max((deadline - now).total_seconds() / 3600, 0.1)
        urgency          = (t.duration / 60) / hours_remaining
        return (
            self.w_priority * float(t.priority)
            + self.w_deadline * urgency
            - self.w_duration * float(t.duration / 60)
        )

    def generate(self, tasks):
        t = tasks[:]
        if random.random() < 0.2:
            random.shuffle(t)
        else:
            t.sort(key=lambda x: self.score(x) + random.uniform(-2, 2),
                   reverse=True)
        return Schedule(t)

    def Crossover(self, schedule1, schedule2):
        p1, p2 = schedule1.tasks, schedule2.tasks
        size   = len(p1)
        if size < 2:
            return Schedule(p1[:])
        a, b = sorted(random.sample(range(size), 2))
        child = [None] * size
        child[a:b] = p1[a:b]
        pos = b
        for t in p2:
            if t not in child:
                if pos >= size:
                    pos = 0
                child[pos] = t
                pos += 1
        child = [t for t in child if t is not None]
        return Schedule(child)

    def Mutate(self, schedule, prob=0.2):
        tasks = schedule.tasks[:]
        if len(tasks) >= 2 and random.random() < prob:
            i, j = random.sample(range(len(tasks)), 2)
            tasks[i], tasks[j] = tasks[j], tasks[i]
        return Schedule(tasks)

    def StoreObjectiveTrainingExample(self, schedule: Schedule, fitness):
        _store("objective.db", schedule, fitness)

    def StorePerformanceTrainingExample(self, schedule: Schedule, fitness):
        _store("performance.db", schedule, fitness)