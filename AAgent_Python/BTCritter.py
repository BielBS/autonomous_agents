import asyncio
import random
import time

import py_trees
import py_trees as pt
from py_trees import common

import BTAlone
import AAgent_Python.BNs_SmartRoam as BNs_SmartRoam
import Goals_BT_Basic
import Sensors


ASTRONAUT_TAG_FRAGMENTS = ("Astronaut",)
CHASE_IMPASSABLE_TAGS = {"Wall", "Rock", "Machine", "AlienFlower"}


def is_target_tag(tag, target_fragments):
    return any(fragment in tag for fragment in target_fragments)


def find_closest_astronaut(aagent):
    sensor_obj_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
    closest_target = None

    for index, value in enumerate(sensor_obj_info):
        if not value or not is_target_tag(value["tag"], ASTRONAUT_TAG_FRAGMENTS):
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


def is_front_path_blocked(aagent, distance_threshold=1.2):
    front_ray = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO][aagent.rc_sensor.central_ray_index]
    return bool(front_ray and front_ray["tag"] in CHASE_IMPASSABLE_TAGS and front_ray["distance"] <= distance_threshold)


def choose_clear_turn_direction(aagent):
    sensor_obj_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
    left_clearance = 0.0
    right_clearance = 0.0

    for index, value in enumerate(sensor_obj_info):
        if not value or value["tag"] not in CHASE_IMPASSABLE_TAGS:
            clearance = aagent.rc_sensor.ray_length
        else:
            clearance = value["distance"]

        if sensor_angles[index] < 0:
            left_clearance += clearance
        elif sensor_angles[index] > 0:
            right_clearance += clearance

    if left_clearance == right_clearance:
        return random.choice([-1, 1])
    return -1 if left_clearance > right_clearance else 1


class CritterMemory:
    def __init__(self):
        self.cooldown_until = 0.0
        self.retreat_requested = False
        self.target_lock_until = 0.0
        self.last_target_angle = 0.0
        self.last_target_distance = None
        self.chase_blocked_ticks = 0


def update_target_memory(memory, target, hold_seconds=0.9):
    if target is None:
        return

    memory.target_lock_until = time.monotonic() + hold_seconds
    memory.last_target_angle = target["angle"]
    memory.last_target_distance = target["distance"]


def get_chase_target(aagent, memory):
    visible_target = find_closest_astronaut(aagent)
    if visible_target is not None:
        update_target_memory(memory, visible_target)
        visible_target["remembered"] = False
        return visible_target

    if time.monotonic() < memory.target_lock_until and memory.last_target_distance is not None:
        return {
            "index": None,
            "distance": memory.last_target_distance,
            "angle": memory.last_target_angle,
            "tag": "AstronautMemory",
            "remembered": True,
        }

    return None


def clear_target_memory(memory):
    memory.target_lock_until = 0.0
    memory.last_target_angle = 0.0
    memory.last_target_distance = None


class BN_ShouldRetreat(pt.behaviour.Behaviour):
    def __init__(self, memory):
        super(BN_ShouldRetreat, self).__init__("BN_ShouldRetreat")
        self.memory = memory

    def initialise(self):
        pass

    def update(self):
        if self.memory.retreat_requested or time.monotonic() < self.memory.cooldown_until:
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_DetectAstronaut(pt.behaviour.Behaviour):
    def __init__(self, aagent, memory):
        super(BN_DetectAstronaut, self).__init__("BN_DetectAstronaut")
        self.my_agent = aagent
        self.memory = memory

    def initialise(self):
        pass

    def update(self):
        if get_chase_target(self.my_agent, self.memory):
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_CanAttackAstronaut(pt.behaviour.Behaviour):
    ATTACK_DISTANCE = 0.6
    ATTACK_ANGLE = 18.0

    def __init__(self, aagent):
        super(BN_CanAttackAstronaut, self).__init__("BN_CanAttackAstronaut")
        self.my_agent = aagent

    def initialise(self):
        pass

    def update(self):
        target = find_closest_astronaut(self.my_agent)
        if target and target["distance"] <= self.ATTACK_DISTANCE and abs(target["angle"]) <= self.ATTACK_ANGLE:
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_StartRetreat(pt.behaviour.Behaviour):
    RECOVERY_SECONDS = 6.0

    def __init__(self, memory):
        super(BN_StartRetreat, self).__init__("BN_StartRetreat")
        self.memory = memory

    def initialise(self):
        pass

    def update(self):
        self.memory.cooldown_until = time.monotonic() + self.RECOVERY_SECONDS
        self.memory.retreat_requested = True
        return pt.common.Status.SUCCESS

    def terminate(self, new_status: common.Status):
        pass


class BN_ExecuteRetreat(pt.behaviour.Behaviour):
    def __init__(self, aagent, memory):
        super(BN_ExecuteRetreat, self).__init__("BN_ExecuteRetreat")
        self.my_agent = aagent
        self.memory = memory
        self.my_goal = None

    def _choose_retreat_turn(self):
        target = find_closest_astronaut(self.my_agent)
        if target is None or abs(target["angle"]) < 5:
            return random.choice([-1, 1]) * random.uniform(145, 180)

        if target["angle"] > 0:
            return -random.uniform(130, 175)
        return random.uniform(130, 175)

    async def _run_retreat(self):
        backed_off = await Goals_BT_Basic.BackwardDist(
            self.my_agent,
            random.uniform(0.8, 1.4),
            0,
            0,
        ).run()

        turned = await Goals_BT_Basic.Turn_customizable(
            self.my_agent,
            0,
            self._choose_retreat_turn(),
        ).run()
        if not turned:
            return False
        escaped = await Goals_BT_Basic.ForwardDist(self.my_agent, random.uniform(4.5, 6.5), 0, 0).run()
        return bool(backed_off or escaped)

    def initialise(self):
        if self.memory.retreat_requested:
            self.memory.retreat_requested = False
            self.my_goal = asyncio.create_task(self._run_retreat())

    def update(self):
        if self.my_goal is not None:
            if not self.my_goal.done():
                return pt.common.Status.RUNNING
            goal_succeeded = self.my_goal.result()
            self.my_goal = None
            if not goal_succeeded and time.monotonic() < self.memory.cooldown_until:
                self.my_goal = asyncio.create_task(self._run_retreat())
                return pt.common.Status.RUNNING

        if time.monotonic() < self.memory.cooldown_until:
            return pt.common.Status.RUNNING
        return pt.common.Status.SUCCESS

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BN_ChaseAstronaut(pt.behaviour.Behaviour):
    TURN_THRESHOLD = 10.0
    ARC_TURN_THRESHOLD = 50.0
    BLOCKED_ESCAPE_TICKS = 2

    def __init__(self, aagent, memory):
        super(BN_ChaseAstronaut, self).__init__("BN_ChaseAstronaut")
        self.my_agent = aagent
        self.memory = memory
        self.last_translation = None
        self.last_rotation = None

    def _queue_action(self, action):
        asyncio.create_task(self.my_agent.send_message("action", action))

    def _set_motion(self, translation=None, rotation=None):
        if translation is not None and translation != self.last_translation:
            self.last_translation = translation
            self._queue_action(translation)

        if rotation is not None and rotation != self.last_rotation:
            self.last_rotation = rotation
            self._queue_action(rotation)

    def initialise(self):
        self.last_translation = None
        self.last_rotation = None
        self.memory.chase_blocked_ticks = 0

    def update(self):
        target = get_chase_target(self.my_agent, self.memory)
        if target is None:
            self.memory.chase_blocked_ticks = 0
            self._set_motion("ntm", "nt")
            return pt.common.Status.FAILURE

        if is_front_path_blocked(self.my_agent):
            self.memory.chase_blocked_ticks += 1
            if self.memory.chase_blocked_ticks >= self.BLOCKED_ESCAPE_TICKS:
                clear_target_memory(self.memory)
                self.memory.retreat_requested = True
                self._set_motion("ntm", "nt")
                return pt.common.Status.FAILURE
            turn_direction = choose_clear_turn_direction(self.my_agent)
            self._set_motion("ntm", "tr" if turn_direction > 0 else "tl")
        elif abs(target["angle"]) <= self.TURN_THRESHOLD:
            self.memory.chase_blocked_ticks = 0
            self._set_motion("mf", "nt")
        elif abs(target["angle"]) <= self.ARC_TURN_THRESHOLD:
            self.memory.chase_blocked_ticks = 0
            self._set_motion("mf", "tr" if target["angle"] > 0 else "tl")
        elif target["angle"] > 0:
            self.memory.chase_blocked_ticks = 0
            self._set_motion("ntm", "tr")
        else:
            self.memory.chase_blocked_ticks = 0
            self._set_motion("ntm", "tl")

        return pt.common.Status.RUNNING

    def terminate(self, new_status: common.Status):
        self._queue_action("stop")
        self.last_translation = None
        self.last_rotation = None
        self.memory.chase_blocked_ticks = 0


class BTCritter:
    def __init__(self, aagent):
        self.aagent = aagent
        self.memory = CritterMemory()

        retreat = pt.composites.Sequence(name="Retreat", memory=False)
        retreat.add_children([
            BN_ShouldRetreat(self.memory),
            BN_ExecuteRetreat(aagent, self.memory),
        ])

        attack = pt.composites.Sequence(name="AttackAstronaut", memory=False)
        attack.add_children([
            BN_CanAttackAstronaut(aagent),
            BN_StartRetreat(self.memory),
        ])

        engage = pt.composites.Sequence(name="EngageAstronaut", memory=True)
        engage.add_children([
            BN_DetectAstronaut(aagent, self.memory),
            pt.composites.Selector(name="AttackOrChase", memory=False, children=[
                attack,
                BN_ChaseAstronaut(aagent, self.memory),
            ]),
        ])

        smart_roaming = BNs_SmartRoam.create_roaming_subtree(
            aagent,
            name="SmartRoaming",
            extra_impassable_tags={"AlienFlower"},
            use_reverse_escape=True,
            escape_on_front_blocked=True,
            front_blocked_distance=1.6,
            avoid_side_walls=True,
            side_wall_distance=2.0,
            center_bias_weight=1.0,
        )

        self.root = pt.composites.Selector(name="Selector", memory=False)
        self.root.add_children([
            retreat,
            engage,
            smart_roaming,
        ])

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
