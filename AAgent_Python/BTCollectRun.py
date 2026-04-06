import asyncio
import random

import py_trees
import py_trees as pt
from py_trees import common

import BTAlone
import BNs_SmartRoam
import Goals_BT_Basic
import Sensors


CRITTER_TAG_FRAGMENTS = ("Critter",)


def find_closest_visible_object(aagent, target_tags):
    sensor_obj_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
    closest_target = None

    for index, value in enumerate(sensor_obj_info):
        if not value or not any(fragment in value["tag"] for fragment in target_tags):
            continue

        candidate = {
            "index": index,
            "distance": value["distance"],
            "angle": sensor_angles[index],
            "tag": value["tag"],
        }
        if closest_target is None or candidate["distance"] < closest_target["distance"]:
            closest_target = candidate

    return closest_target


class CollectRunMemory:
    def __init__(self):
        self.was_frozen = False
        self.pending_recovery = False


class BN_DetectFrozenState(pt.behaviour.Behaviour):
    def __init__(self, aagent, memory):
        super(BN_DetectFrozenState, self).__init__("BN_DetectFrozenState")
        self.my_agent = aagent
        self.memory = memory

    def initialise(self):
        pass

    def update(self):
        if self.my_agent.i_state.isFrozen:
            self.memory.was_frozen = True
            return pt.common.Status.SUCCESS

        if self.memory.was_frozen:
            self.memory.was_frozen = False
            self.memory.pending_recovery = True

        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_WaitUntilThawed(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super(BN_WaitUntilThawed, self).__init__("BN_WaitUntilThawed")
        self.my_agent = aagent

    def initialise(self):
        asyncio.create_task(self.my_agent.send_message("action", "stop"))

    def update(self):
        if self.my_agent.i_state.isFrozen:
            return pt.common.Status.RUNNING
        return pt.common.Status.SUCCESS

    def terminate(self, new_status: common.Status):
        pass


class BN_ShouldRecoverAfterFreeze(pt.behaviour.Behaviour):
    def __init__(self, memory):
        super(BN_ShouldRecoverAfterFreeze, self).__init__("BN_ShouldRecoverAfterFreeze")
        self.memory = memory

    def initialise(self):
        pass

    def update(self):
        if self.memory.pending_recovery:
            self.memory.pending_recovery = False
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_DetectNearbyCritter(pt.behaviour.Behaviour):
    DANGER_DISTANCE = 6.0

    def __init__(self, aagent):
        super(BN_DetectNearbyCritter, self).__init__("BN_DetectNearbyCritter")
        self.my_agent = aagent

    def initialise(self):
        pass

    def update(self):
        target = find_closest_visible_object(self.my_agent, CRITTER_TAG_FRAGMENTS)
        if target and target["distance"] <= self.DANGER_DISTANCE:
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_EvadeCritter(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super(BN_EvadeCritter, self).__init__("BN_EvadeCritter")
        self.my_agent = aagent
        self.my_goal = None

    def _choose_escape_turn(self, target):
        if target is None:
            return random.choice([-1, 1]) * random.uniform(120, 165)

        angle = target["angle"]
        if abs(angle) < 10:
            return random.choice([-1, 1]) * random.uniform(135, 170)

        if angle > 0:
            return -random.uniform(100, 145)
        return random.uniform(100, 145)

    async def _run_escape(self, escape_turn, escape_distance):
        target = find_closest_visible_object(self.my_agent, CRITTER_TAG_FRAGMENTS)
        if target and target["distance"] <= 1.8:
            backed_off = await Goals_BT_Basic.BackwardDist(
                self.my_agent,
                random.uniform(0.8, 1.5),
                0,
                0,
            ).run()
            if not backed_off:
                return False

        turned = await Goals_BT_Basic.Turn_customizable(self.my_agent, 0, escape_turn).run()
        if not turned:
            return False
        return await Goals_BT_Basic.ForwardDist(self.my_agent, escape_distance, 0, 0).run()

    def initialise(self):
        target = find_closest_visible_object(self.my_agent, CRITTER_TAG_FRAGMENTS)
        self.my_goal = asyncio.create_task(
            self._run_escape(
                self._choose_escape_turn(target),
                random.uniform(4.5, 6.5),
            )
        )

    def update(self):
        return BTAlone.common_goal_update(self.my_goal)

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BN_ForcedRecoverAfterHit(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        super(BN_ForcedRecoverAfterHit, self).__init__("BN_ForcedRecoverAfterHit")
        self.my_agent = aagent
        self.my_goal = None

    def _choose_escape_turn(self):
        target = find_closest_visible_object(self.my_agent, CRITTER_TAG_FRAGMENTS)
        if target is None or abs(target["angle"]) < 12:
            return random.choice([-1, 1]) * random.uniform(120, 165)
        if target["angle"] > 0:
            return -random.uniform(105, 150)
        return random.uniform(105, 150)

    async def _run_recovery(self):
        await self.my_agent.send_message("action", "stop")
        await asyncio.sleep(0)

        backed_off = await Goals_BT_Basic.BackwardDist(
            self.my_agent,
            random.uniform(1.0, 1.8),
            0,
            0,
        ).run()

        turned = await Goals_BT_Basic.Turn_customizable(
            self.my_agent,
            0,
            self._choose_escape_turn(),
        ).run()
        if not turned:
            return False

        escaped = await Goals_BT_Basic.ForwardDist(
            self.my_agent,
            random.uniform(4.0, 5.5),
            0,
            0,
        ).run()
        return bool(backed_off or escaped)

    def initialise(self):
        self.my_goal = asyncio.create_task(self._run_recovery())

    def update(self):
        return BTAlone.common_goal_update(self.my_goal)

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BTCollectRun:
    def __init__(self, aagent):
        self.aagent = aagent
        self.memory = CollectRunMemory()

        frozen = pt.composites.Sequence(name="DetectFrozen", memory=True)
        frozen.add_children([
            BN_DetectFrozenState(aagent, self.memory),
            BN_WaitUntilThawed(aagent),
        ])

        recover_from_hit = pt.composites.Sequence(name="RecoverFromHit", memory=True)
        recover_from_hit.add_children([
            BN_ShouldRecoverAfterFreeze(self.memory),
            BN_ForcedRecoverAfterHit(aagent),
        ])

        evade_critter = pt.composites.Sequence(name="EvadeCritter", memory=True)
        evade_critter.add_children([BN_DetectNearbyCritter(aagent), BN_EvadeCritter(aagent)])

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

        self.root = pt.composites.Selector(name="Selector", memory=False)
        self.root.add_children([frozen, recover_from_hit, false_root])

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
