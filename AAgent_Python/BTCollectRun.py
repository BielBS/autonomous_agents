import asyncio
import random

import py_trees as pt
from py_trees import common

import BTAlone
import BNs_SmartRoam
import Goals_BT_Basic
import Sensors


class BN_DetectNearbyCritter(pt.behaviour.Behaviour):
    DANGER_DISTANCE = 6.0

    def __init__(self, aagent):
        super(BN_DetectNearbyCritter, self).__init__("BN_DetectNearbyCritter")
        self.my_agent = aagent

    def initialise(self):
        pass

    def update(self):
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]

        for value in sensor_obj_info:
            if value:
                if "Critter" in value["tag"] and value["distance"] <= self.DANGER_DISTANCE:
                    return pt.common.Status.SUCCESS

        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_EvadeCritter(pt.behaviour.Behaviour):
    TOO_CLOSE_DISTANCE = 1.8

    def __init__(self, aagent):
        self.my_goal = None
        super(BN_EvadeCritter, self).__init__("BN_EvadeCritter")
        self.my_agent = aagent

    async def evade(self, critter_distance, critter_angle):
        # If the critter is almost touching the astronaut, back up first.
        if critter_distance is not None and critter_distance <= self.TOO_CLOSE_DISTANCE:
            backed_off = await Goals_BT_Basic.BackwardDist(
                self.my_agent,
                random.uniform(0.8, 1.5),
                0,
                0,
            ).run()
            if not backed_off:
                return False

        # Turn away from the critter. If it is directly ahead, choose a random side.
        if critter_distance is None or abs(critter_angle) < 10:
            escape_turn = random.choice([-1, 1]) * random.uniform(135, 170)
        elif critter_angle > 0:
            escape_turn = -random.uniform(100, 145)
        else:
            escape_turn = random.uniform(100, 145)

        turned = await Goals_BT_Basic.Turn_customizable(self.my_agent, 0, escape_turn).run()
        if not turned:
            return False

        # After turning away, run forward to create space.
        return await Goals_BT_Basic.ForwardDist(
            self.my_agent,
            random.uniform(4.5, 6.5),
            0,
            0,
        ).run()

    def initialise(self):
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        sensor_angles = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]

        critter_distance = None
        critter_angle = 0.0

        for index, value in enumerate(sensor_obj_info):
            if value:
                if "Critter" in value["tag"]:
                    if critter_distance is None or value["distance"] < critter_distance:
                        critter_distance = value["distance"]
                        critter_angle = sensor_angles[index]

        self.my_goal = asyncio.create_task(self.evade(critter_distance, critter_angle))

    def update(self):
        if not self.my_goal.done():
            return pt.common.Status.RUNNING
        else:
            if self.my_goal.result():
                return pt.common.Status.SUCCESS
            else:
                return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BTCollectRun:
    def __init__(self, aagent):
        self.aagent = aagent

        # Priority order:
        # 1. If frozen, wait until the critter releases the astronaut.
        # 2. If a critter is nearby, evade it.
        # 3. If the inventory is full, return flowers to base.
        # 4. If a flower is visible, collect it.
        # 5. Otherwise roam.
        frozen = pt.composites.Sequence(name="Sequence_frozen", memory=True)
        frozen.add_children([
            BTAlone.BN_DetectFrozen(aagent),
            BTAlone.BN_DoNothing(aagent),
        ])

        evade_critter = pt.composites.Sequence(name="EvadeCritter", memory=True)
        evade_critter.add_children([
            BN_DetectNearbyCritter(aagent),
            BN_EvadeCritter(aagent),
        ])

        flower_protocol = pt.composites.Sequence(name="MoveToFlower", memory=True)
        flower_protocol.add_children([
            BTAlone.BN_DetectFlower(aagent),
            BTAlone.BN_MoveToFlower(aagent),
        ])

        return_to_base = pt.composites.Selector(name="ReturnToBase", memory=False)
        return_to_base.add_children([
            BTAlone.BN_IsInBaseNearContainer(aagent),
            BTAlone.BN_ReturnToBase(aagent),
        ])

        store_flowers = pt.composites.Sequence(name="StoreFlowers", memory=True)
        store_flowers.add_children([
            BTAlone.BN_CheckInventory(aagent),
            return_to_base,
            BTAlone.BN_DropOffFlowers(aagent),
        ])

        smart_roaming = BNs_SmartRoam.create_roaming_subtree(
            aagent,
            name="SmartRoaming",
            avoid_side_walls=True,
            side_wall_distance=2.0,
            center_bias_weight=1.1,
        )

        false_root = pt.composites.Selector(name="Selector", memory=False)
        false_root.add_children([
            evade_critter,
            store_flowers,
            flower_protocol,
            smart_roaming,
        ])

        self.root = pt.composites.Selector(name="Selector_root", memory=False)
        self.root.add_children([frozen, false_root])

        self.behaviour_tree = pt.trees.BehaviourTree(self.root)

    def stop_behaviour_tree(self):
        print("Stopping the BehaviorTree")
        self.root.tick_once()

        for node in self.root.iterate():
            if node.status != pt.common.Status.INVALID:
                node.status = pt.common.Status.INVALID
                if hasattr(node, "terminate"):
                    node.terminate(pt.common.Status.INVALID)

    async def tick(self):
        self.behaviour_tree.tick()
        await asyncio.sleep(0)
