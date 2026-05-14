#Surrogate.py

import sqlite3
import NeuralNet as nn
from ScheduleUtils import *
import torch as tc
import torch.nn as nn2
import torch.optim as optim


def _train(brain, db_path, epochs, lr):
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    try:
        cur.execute("""
            SELECT totalDuration, avgPriority, weightedPriority,
                   switchingCost, cumulativeTime, Maxdeadline,
                   type1Sum, type2Sum, fitness
            FROM tasks
        """)
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return
    finally:
        conn.close()

    if len(rows) < 2:
        return

    X = tc.tensor([[r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]]
                   for r in rows], dtype=tc.float32)
    y = tc.tensor([[r[8]] for r in rows], dtype=tc.float32)

    optimizer = optim.Adam(brain.parameters(), lr=lr)
    lossfn    = nn2.MSELoss()

    for _ in range(epochs):
        loss = lossfn(brain(X), y)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()


class Objectivesurrogate:
    def __init__(self):
        self.brain = nn.SurrogateBuild()

    def Predict(self, schedule: Schedule):
        out = self.brain(schedule.encodeAsTensor())
        return out.view(-1)[0].item()

    def Train(self, epochs=50, lr=0.001):
        _train(self.brain, "objective.db", epochs, lr)


class PerformanceSurrogate:
    def __init__(self):
        self.brain = nn.SurrogateBuild()

    def Predict(self, schedule: Schedule):
        out = self.brain(schedule.encodeAsTensor())
        return out.view(-1)[0].item()

    def Train(self, epochs=50, lr=0.005):
        _train(self.brain, "performance.db", epochs, lr)