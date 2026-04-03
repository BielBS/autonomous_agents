import py_trees
import time

class HighPriorityCheck(py_trees.behaviour.Behaviour):
    def __init__(self, name):
        super(HighPriorityCheck, self).__init__(name)
        self.count = 0

    def initialise(self):
        print(f"{self.name}: INITIALISE")

    def update(self):
        self.count += 1
        # Fail for the first 3 ticks, then succeed
        if self.count <= 3:
            print(f"{self.name}: is FAILURE (Condition not met) [Internal counter = {self.count}]")
            return py_trees.common.Status.FAILURE
        else:
            print(f"{self.name}: is SUCCESS (Condition met!)")
            return py_trees.common.Status.SUCCESS

    def terminate(self, new_status):
        print(f"{self.name}: is TERMINATING")

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


def run_test(use_memory):
    print(f"\n{'=' * 10} TESTING SELECTOR (memory={use_memory}) {'=' * 10}")

    condition = HighPriorityCheck("SafetyCheck")
    work = CounterBehavior("Counter5", 5)

    root = py_trees.composites.Selector(name="Root", memory=use_memory)
    root.add_child(condition)
    root.add_child(work)

    tree = py_trees.trees.BehaviourTree(root)

    for t in range(20):
        print(f"\nTick {t + 1}:")
        tree.tick()


# Run both scenarios
run_test(use_memory=False)
run_test(use_memory=True)