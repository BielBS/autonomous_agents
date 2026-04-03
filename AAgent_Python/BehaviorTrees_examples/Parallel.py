import py_trees
import time


class QuickWorker(py_trees.behaviour.Behaviour):
    """Succeeds very fast (Tick 2)."""

    def __init__(self, name):
        super().__init__(name)
        self.count = 0

    def initialise(self):
        print(f"{self.name}: INITIALISE")
        self.count = 0

    def update(self):
        self.count += 1
        if self.count >= 2:
            print(f"{self.name}: SUCCESS")
            return py_trees.common.Status.SUCCESS
        print(f"{self.name}: RUNNING, Counter={self.count}")
        return py_trees.common.Status.RUNNING

    def terminate(self, new_status):
        print(f"{self.name}: is TERMINATING")


class SlowWorker(py_trees.behaviour.Behaviour):
    """Succeeds slowly (Tick 4)."""

    def __init__(self, name):
        super().__init__(name)
        self.count = 0

    def initialise(self):
        print(f"{self.name}: INITIALISE")
        self.count = 0

    def update(self):
        self.count += 1
        if self.count >= 4:
            print(f"{self.name}: SUCCESS")
            return py_trees.common.Status.SUCCESS
        print(f"{self.name}: RUNNING, Counter={self.count}")
        return py_trees.common.Status.RUNNING

    def terminate(self, new_status):
        print(f"{self.name}: is TERMINATING")


def test_parallel(policy, name):
    print(f"\n{'=' * 10} POLICY: {name} {'=' * 10}")

    # Define children
    fast = QuickWorker("Fast")
    slow = SlowWorker("Slow")

    # Create Parallel with specific policy
    # Note: SuccessOnSelected requires a list of children to watch
    if name == "SuccessOnSelected":
        root = py_trees.composites.Parallel(
            name="Parallel",
            policy=py_trees.common.ParallelPolicy.SuccessOnSelected([fast])
        )
    else:
        root = py_trees.composites.Parallel(name="Parallel", policy=policy)

    root.add_child(fast)
    root.add_child(slow)

    tree = py_trees.trees.BehaviourTree(root)

    # Add the SnapshotVisitor
    # This visitor captures the state of the tree at the end of every tick
    visitor = py_trees.visitors.SnapshotVisitor()
    tree.visitors.append(visitor)

    for t in range(10):
        print(f"\nTick {t}:")
        tree.tick()

        status = root.status
        print(f"Root status: {status}")
        if (status == py_trees.common.Status.SUCCESS) or (status == py_trees.common.Status.FAILURE):
            break

# 1. SuccessOnAll: Wait for everyone
test_parallel(py_trees.common.ParallelPolicy.SuccessOnAll(), "SuccessOnAll")

# 2. SuccessOnOne: Finish as soon as the fastest one finishes
test_parallel(py_trees.common.ParallelPolicy.SuccessOnOne(), "SuccessOnOne")

# 3. SuccessOnSelected: Only care about the 'Fast' worker
test_parallel(None, "SuccessOnSelected")