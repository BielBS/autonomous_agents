import asyncio
import functools
import random
import sys

import py_trees as pt
import py_trees.blackboard
from py_trees import common


class BtAction1(pt.behaviour.Behaviour):
    def __init__(self, name, aagent):
        self.my_task = None
        print("Initializing BtAction1")
        super(BtAction1, self).__init__(name)
        self.my_agent = aagent

    def initialise(self):
        print("Initialise BtAction1")
        self.my_task = asyncio.create_task(self.my_agent.action_1())

    def update(self):
        # print("Checking BtAction1")
        if not self.my_task.done():
            return pt.common.Status.RUNNING
        else:
            if self.my_task.result():
                print("BtAction1 completed with SUCCESS")
                return pt.common.Status.SUCCESS
            else:
                print("BtAction1 completed with FAILURE")
                return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        # Finishing the behaviour, therefore we have to stop the associated task
        self.my_task.cancel()


class BtAction2(pt.behaviour.Behaviour):
    def __init__(self, name, aagent):
        self.my_task = None
        print("Initializing BtAction2")
        super(BtAction2, self).__init__(name)
        self.my_agent = aagent
        self.stop_event = asyncio.Event()

    def initialise(self):
        print("Initialise BtAction2")
        self.my_task = asyncio.create_task(self.my_agent.action_2())

    def update(self):
        # print("Checking BtAction2")
        if not self.my_task.done():
            return pt.common.Status.RUNNING
        else:
            if self.my_task.result():
                print("BtAction2 completed with SUCCESS")
                return pt.common.Status.SUCCESS
            else:
                print("BtAction2 completed with FAILURE")
                return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        # Finishing the behaviour, therefore we have to stop the associated task
        self.my_task.cancel()


class BtAction3(pt.behaviour.Behaviour):
    def __init__(self, name, aagent):
        self.my_task = None
        print("Initializing BtAction3")
        super(BtAction3, self).__init__(name)
        self.my_agent = aagent

    def initialise(self):
        print("Initialise BtAction3")
        self.my_task = asyncio.create_task(self.my_agent.action_3())

    def update(self):
        # print("Checking BtAction3")
        if not self.my_task.done():
            return pt.common.Status.RUNNING
        else:
            if self.my_task.result():
                print("BtAction3 completed with SUCCESS")
                return pt.common.Status.SUCCESS
            else:
                print("BtAction3 completed with FAILURE")
                return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        # Finishing the behaviour, therefore we have to stop the associated task
        self.my_task.cancel()


class AAgent:
    def __init__(self, a_name: str):
        self.a_name = a_name
        self.exit = False

    async def action_1(self):
        try:
            print("Starting action_1.")
            await asyncio.sleep(5)
            decision = True
            print("End: action_1 with result: " + str(decision))
            return decision
        except asyncio.CancelledError:
            print("action_1 cancelled")
            # Do whatever is needed to cancel the task properly

    async def action_2(self):
        try:
            print("Starting action_2.")
            await asyncio.sleep(8)
            decision = random.choice([True, False])
            print("End: action_2 with result: " + str(decision))
            return decision
        except asyncio.CancelledError:
            print("action_2 cancelled")
            # Do whatever is needed to cancel the task properly

    async def action_3(self):
        try:
            print("Starting action_3.")
            await asyncio.sleep(10)
            decision = random.choice([True, False])
            print("End: action_3 with result: " + str(decision))
            return decision
        except asyncio.CancelledError:
            print("action_3 cancelled")
            # Do whatever is needed to cancel the task properly

    async def run(self):
        while not self.exit:
            print("Agent " + self.a_name + " working hard in other things...")
            await asyncio.sleep(1)


async def main():
    a1 = AAgent("Agent_1")
    asyncio.create_task(a1.run())
    # BEHAVIOUR TREE
    root = pt.composites.Parallel(
        name = "Root", policy=pt.common.ParallelPolicy.SuccessOnAll())

    # Add three action nodes to the Parallel
    act1 = BtAction1("Action_1", a1)
    act2 = BtAction2("Action_2", a1)
    act3 = BtAction3("Action_3", a1)

    root.add_children([act1, act2, act3])

    behaviour_tree = pt.trees.BehaviourTree(root)
    behaviour_tree.setup(timeout=15)

    print("Behaviour tree created and waiting to run.")

    behaviour_tree_running = True
    print("Starting the asyncio event loop")
    while True:
        await asyncio.sleep(0)
        if behaviour_tree_running:
            if behaviour_tree.root.status == pt.common.Status.SUCCESS:
                print("Behavior tree has finished. Result: SUCCESS")
                behaviour_tree_running = False
            elif behaviour_tree.root.status == pt.common.Status.FAILURE:
                print("Behavior tree has finished. Result: FAILURE")
                behaviour_tree_running = False
            else:
                # print("Behavior tree is still running")
                await asyncio.sleep(1)
                behaviour_tree.tick()


if __name__ == "__main__":
    # py_trees.logging.level = py_trees.logging.Level.DEBUG
    asyncio.run(main())