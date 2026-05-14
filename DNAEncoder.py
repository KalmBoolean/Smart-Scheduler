#DNAEncoder.py
from enum import Enum

#additional stuff we might implement
class TaskType(Enum):
    Proffessional = 1
    Classical = 2

#dna
class task():
    def __init__(self, type : TaskType, deadline, duration,priority,cognitive_load = 0.1,name = "generic"):
        self.type = type
        self.deadLine = deadline
        self.duration = duration
        self.priority = priority
        self.cognitive_load = cognitive_load
        self.name = name
