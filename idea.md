Alright, so basically its gonna generate a whole bunch of schedules with the chromosomes being different params 
of the schedule, then it'll use llms to evaluate true fitness using a basic simulkation type stuff where the llms simulate real humans.
then its gonna genetically crossover the chromosmes using some algo (like job shop scheduling) and mutate to get the new set of schedules.
We use a surrogate neural network to estimate the fitness for all, and then use llms to simulate the top 20. we train the nn on the original datatset we create with llm simulated fitness, then just correct model drift eventually.
Boom