import time
import io

import py_trees

class CounterBehavior(py_trees.behaviour.Behaviour):
    def __init__(self, name, threshold):
        super(CounterBehavior, self).__init__(name)
        self.success_threshold = threshold
        self.counter = 0

    def initialise(self):
        # print(f"{self.name}: INITIALISE - We DO NOT Reset the counter in initialise")

        print(f"{self.name} INITIALISE - We Reset the counter in initialise")
        self.counter = 0

    def update(self):
        if self.counter == self.success_threshold:
            print(f"{self.name}: is SUCCESS")
            return py_trees.common.Status.SUCCESS
        else:
            print(f"{self.name}: is RUNNING - Counter: {self.counter}")
            self.counter += 1
            return py_trees.common.Status.RUNNING

    def terminate(self, new_status):
        print(f"{self.name}: is TERMINATING")


# Create the behaviors
counter3 = CounterBehavior("Counter3", 3)
counter2 = CounterBehavior("Counter2", 2)

# Create a Sequence
root = py_trees.composites.Sequence(name="Sequence", memory=True)
# root = py_trees.composites.Sequence(name="Sequence", memory=False)

# Add behaviors to the Sequence
root.add_child(counter3)
root.add_child(counter2)

# Initialize the behavior tree
tree = py_trees.trees.BehaviourTree(root)

# Tick the tree and observe the output
for t in range(16):
    print(f"\nTick {t + 1}")  # Print the tick number (starting from 1)
    tree.tick()
    #time.sleep(1)  # Simulate time between ticks
