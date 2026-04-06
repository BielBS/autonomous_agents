import asyncio
import random

import py_trees as pt
from py_trees import common

import Goals_BT_Basic
import Sensors

from Utils import common_goal_update

IMPASSABLE_OBJECT_TAGS = {"Wall", "Rock", "Machine"}


class RoamMemory:
    def __init__(
        self,
        extra_impassable_tags=None,
        use_reverse_escape=False,
        escape_on_front_blocked=False,
        front_blocked_distance=1.4,
        front_blocked_angle=30.0,
        avoid_side_walls=False,
        side_wall_distance=1.8,
        center_bias_weight=0.4,
    ):
        self.consecutive_failures = 0
        self.extra_impassable_tags = set(extra_impassable_tags or ())
        self.use_reverse_escape = use_reverse_escape
        self.escape_on_front_blocked = escape_on_front_blocked
        self.front_blocked_distance = front_blocked_distance
        self.front_blocked_angle = front_blocked_angle
        self.avoid_side_walls = avoid_side_walls
        self.side_wall_distance = side_wall_distance
        self.center_bias_weight = center_bias_weight



def _is_impassable(ray_info, memory):
    if not ray_info:
        return False
    return ray_info["tag"] in IMPASSABLE_OBJECT_TAGS or ray_info["tag"] in memory.extra_impassable_tags


def _get_impassable_clearance(aagent, ray_info, memory):
    if not _is_impassable(ray_info, memory):
        return aagent.rc_sensor.ray_length
    return ray_info["distance"]


def _get_hard_clearance(aagent, ray_info):
    if not ray_info or ray_info["tag"] not in IMPASSABLE_OBJECT_TAGS:
        return aagent.rc_sensor.ray_length
    return ray_info["distance"]


def _get_front_cone_clearance(aagent, memory):
    sensor_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
    cone_clearances = [
        _get_impassable_clearance(aagent, value, memory)
        for index, value in enumerate(sensor_info)
        if abs(sensor_angles[index]) <= memory.front_blocked_angle
    ]

    if not cone_clearances:
        return aagent.rc_sensor.ray_length

    return min(cone_clearances)


def _get_side_min_clearance(aagent, memory, side):
    sensor_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
    side_clearances = [
        _get_hard_clearance(aagent, value)
        for index, value in enumerate(sensor_info)
        if (side < 0 and sensor_angles[index] < 0) or (side > 0 and sensor_angles[index] > 0)
    ]

    if not side_clearances:
        return aagent.rc_sensor.ray_length

    return min(side_clearances)


def _choose_inward_wall_avoidance_angle(aagent, memory):
    if not memory.avoid_side_walls:
        return None

    left_clearance = _get_side_min_clearance(aagent, memory, -1)
    right_clearance = _get_side_min_clearance(aagent, memory, 1)

    if left_clearance <= memory.side_wall_distance and right_clearance > left_clearance + 0.5:
        return random.uniform(25, 65)

    if right_clearance <= memory.side_wall_distance and left_clearance > right_clearance + 0.5:
        return -random.uniform(25, 65)

    return None


def choose_clear_side_direction(aagent, memory):
    sensor_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
    left_clearance = 0.0
    right_clearance = 0.0

    for index, value in enumerate(sensor_info):
        clearance = _get_impassable_clearance(aagent, value, memory)
        if sensor_angles[index] < 0:
            left_clearance += clearance
        elif sensor_angles[index] > 0:
            right_clearance += clearance

    if left_clearance == right_clearance:
        return random.choice([-1, 1])

    return -1 if left_clearance > right_clearance else 1


def _choose_escape_angle(aagent, memory):
    direction = choose_clear_side_direction(aagent, memory)
    return direction * random.uniform(110, 170)


def choose_roam_angle(aagent, memory):
    sensor_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
    max_angle = max(1.0, float(aagent.rc_sensor.max_ray_degrees))
    candidates = []

    inward_turn = _choose_inward_wall_avoidance_angle(aagent, memory)
    if inward_turn is not None:
        return inward_turn

    if (
        memory.escape_on_front_blocked
        and memory.consecutive_failures > 0
        and _get_front_cone_clearance(aagent, memory) <= memory.front_blocked_distance
    ):
        return _choose_escape_angle(aagent, memory)

    for index, value in enumerate(sensor_info):
        clearance = _get_impassable_clearance(aagent, value, memory)
        angle = sensor_angles[index]
        center_bias = 1.0 - (abs(angle) / max_angle)
        if memory.consecutive_failures > 0:
            center_bias *= 0.3
        score = clearance + (memory.center_bias_weight * center_bias)
        candidates.append((score, clearance, angle, index))

    candidates.sort(key=lambda item: (item[0], item[1], -abs(item[2])), reverse=True)
    _, clearance, angle, index = random.choice(candidates[: min(2, len(candidates))])

    if memory.consecutive_failures >= 2:
        return _choose_escape_angle(aagent, memory)

    if clearance < 1.5 and abs(angle) < 15:
        return random.choice([-1, 1]) * random.uniform(90, 150)

    left_bound = -max_angle if index == 0 else (sensor_angles[index - 1] + angle) / 2
    right_bound = max_angle if index == len(sensor_angles) - 1 else (sensor_angles[index + 1] + angle) / 2
    return random.uniform(left_bound, right_bound)


def choose_roam_distance(aagent, memory):
    front_ray = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO][aagent.rc_sensor.central_ray_index]
    if memory.consecutive_failures > 0:
        target_distance = random.uniform(1.5, 3.0)
    else:
        target_distance = random.uniform(2.5, 5.0)

    if memory.avoid_side_walls:
        left_clearance = _get_side_min_clearance(aagent, memory, -1)
        right_clearance = _get_side_min_clearance(aagent, memory, 1)
        if min(left_clearance, right_clearance) <= memory.side_wall_distance:
            target_distance = min(target_distance, random.uniform(1.2, 2.2))

    if _is_impassable(front_ray, memory):
        target_distance = min(target_distance, front_ray["distance"] - 0.75)

    return max(0.0, target_distance)


class BN_ShouldEscape(pt.behaviour.Behaviour):
    def __init__(self, aagent, memory, escape_threshold=2):
        super(BN_ShouldEscape, self).__init__("BN_ShouldEscape")
        self.aagent = aagent
        self.memory = memory
        self.escape_threshold = escape_threshold

    def initialise(self):
        pass

    def update(self):
        if self.memory.consecutive_failures >= self.escape_threshold:
            return pt.common.Status.SUCCESS
        if (
            self.memory.escape_on_front_blocked
            and self.memory.consecutive_failures > 0
            and _get_front_cone_clearance(self.aagent, self.memory) <= self.memory.front_blocked_distance
        ):
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_RoamTurn(pt.behaviour.Behaviour):
    MIN_TURN_THRESHOLD = 7.0

    def __init__(self, aagent, memory):
        super(BN_RoamTurn, self).__init__("BN_RoamTurn")
        self.my_agent = aagent
        self.memory = memory
        self.my_goal = None

    def initialise(self):
        chosen_angle = choose_roam_angle(self.my_agent, self.memory)
        if abs(chosen_angle) < self.MIN_TURN_THRESHOLD:
            self.my_goal = None
            return

        self.my_goal = asyncio.create_task(
            Goals_BT_Basic.Turn_customizable(self.my_agent, 0, chosen_angle).run()
        )

    def update(self):
        if self.my_goal is None:
            return pt.common.Status.SUCCESS
        return common_goal_update(self.my_goal)

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BN_RoamForward(pt.behaviour.Behaviour):
    MIN_TRAVEL_DISTANCE = 1.0

    def __init__(self, aagent, memory):
        super(BN_RoamForward, self).__init__("BN_RoamForward")
        self.my_agent = aagent
        self.memory = memory
        self.my_goal = None
        self.blocked = False

    def initialise(self):
        self.blocked = False
        target_distance = choose_roam_distance(self.my_agent, self.memory)
        if target_distance < self.MIN_TRAVEL_DISTANCE:
            self.blocked = True
            self.my_goal = None
            return

        self.my_goal = asyncio.create_task(
            Goals_BT_Basic.ForwardDist(self.my_agent, target_distance, 0, 0).run()
        )

    def update(self):
        if self.blocked:
            self.memory.consecutive_failures += 1
            return pt.common.Status.FAILURE

        status = common_goal_update(self.my_goal)
        if status == pt.common.Status.SUCCESS:
            self.memory.consecutive_failures = 0
        elif status == pt.common.Status.FAILURE:
            self.memory.consecutive_failures += 1
        return status

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BN_RoamBackOff(pt.behaviour.Behaviour):
    def __init__(self, aagent, memory):
        super(BN_RoamBackOff, self).__init__("BN_RoamBackOff")
        self.my_agent = aagent
        self.memory = memory
        self.my_goal = None

    def initialise(self):
        if not self.memory.use_reverse_escape:
            self.my_goal = None
            return

        self.my_goal = asyncio.create_task(
            Goals_BT_Basic.BackwardDist(self.my_agent, random.uniform(0.7, 1.4), 0, 0).run()
        )

    def update(self):
        if self.my_goal is None:
            return pt.common.Status.SUCCESS
        return common_goal_update(self.my_goal)

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


def create_roaming_subtree(
    aagent,
    name="SmartRoaming",
    extra_impassable_tags=None,
    use_reverse_escape=False,
    escape_on_front_blocked=False,
    front_blocked_distance=1.4,
    front_blocked_angle=30.0,
    avoid_side_walls=False,
    side_wall_distance=1.8,
    center_bias_weight=0.4,
):
    memory = RoamMemory(
        extra_impassable_tags=extra_impassable_tags,
        use_reverse_escape=use_reverse_escape,
        escape_on_front_blocked=escape_on_front_blocked,
        front_blocked_distance=front_blocked_distance,
        front_blocked_angle=front_blocked_angle,
        avoid_side_walls=avoid_side_walls,
        side_wall_distance=side_wall_distance,
        center_bias_weight=center_bias_weight,
    )

    escape = pt.composites.Sequence(name=f"{name}_Escape", memory=True)
    escape.add_children([
        BN_ShouldEscape(aagent, memory),
        BN_RoamBackOff(aagent, memory),
        BN_RoamTurn(aagent, memory),
        BN_RoamForward(aagent, memory),
    ])

    roaming = pt.composites.Sequence(name=f"{name}_Normal", memory=True)
    roaming.add_children([
        BN_RoamTurn(aagent, memory),
        BN_RoamForward(aagent, memory),
    ])

    root = pt.composites.Selector(name=name, memory=False)
    root.add_children([escape, roaming])
    return root
