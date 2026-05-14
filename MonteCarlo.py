#MonteCarlo.py

import random
import math
from datetime import datetime

def circadian_factor(time_minutes):
    hour = (time_minutes / 60) % 24
    
    peak = 14
    trough = 3

    p = math.exp(-((hour - peak) ** 2) / 18)
    t = math.exp(-((hour - trough) ** 2) / 8)

    return 0.6 + p - 0.4 * t

def InverseFatigue(fatigue):
    return max(0.3, math.exp(-fatigue))

def switching_penalty(prev_task, next_task):
    if prev_task is None:
        return 0

    diff = abs(prev_task.cognitive_load - next_task.cognitive_load)

    return 5 + diff * 10

def random_interruptions():
    if random.random() < 0.08:
        return random.uniform(5, 20)
    return 0


def simulate_once(schedule):

    time = 8 * 60
    fatigue = 0
    penalty = 0
    prev_task = None

    for task in schedule.tasks:

        time += switching_penalty(prev_task, task)

        duration = random.gauss(task.duration, task.duration * 0.15)

        circ = circadian_factor(time)
        fatigue_mod = InverseFatigue(fatigue)

        productivity = circ * fatigue_mod

        actual_duration = duration / productivity

        actual_duration += random_interruptions()

        time += actual_duration

        fatigue += task.cognitive_load * actual_duration / 300
        fatigue = min(fatigue, 1.5)

        fatigue *= 0.97

        deadline_dt = datetime.fromisoformat(task.deadLine)
        sim_epoch = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deadline_minutes = (deadline_dt - sim_epoch).total_seconds() / 60

        if time > deadline_minutes:
            penalty += (time - deadline_minutes) * task.priority

        prev_task = task

    return penalty

def MonteCarloStuff(schedule, simulations=300):

    total = 0

    for _ in range(simulations):
        total += simulate_once(schedule)
        print(simulate_once(schedule))

    avg_penalty = total / simulations

    return -avg_penalty

def CalculateActualUserPerformance(schedule, execution_log):

    completed = 0
    lateness_penalty = 0
    efficiency_total = 0

    for record in execution_log:

        task = record["task"]
        start = record["start"]
        end = record["end"]
        completed_flag = record["completed"]

        actual_duration = (end - start).total_seconds() / 60

        if completed_flag:
            completed += 1

        # efficiency
        expected = task.duration
        efficiency_total += min(expected / actual_duration, 1)

        # lateness
        deadline = datetime.fromisoformat(task.deadLine)

        if end > deadline:
            late_minutes = (end - deadline).total_seconds() / 60
            lateness_penalty += late_minutes * task.priority

    task_score = completed / max(len(schedule.tasks), 1)

    efficiency_score = efficiency_total / max(len(schedule.tasks), 1)

    lateness_score = 1 / (1 + lateness_penalty / 60)

    performance = (
        0.5 * task_score +
        0.3 * efficiency_score +
        0.2 * lateness_score
    )

    return performance