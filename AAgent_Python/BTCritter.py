import asyncio
import random
import time

import py_trees
import py_trees as pt
from py_trees import common

import BTAlone
import BNs_SmartRoam
import Goals_BT_Basic
import Sensors


ASTRONAUT_TAG_FRAGMENTS = ("Astronaut",)
CHASE_IMPASSABLE_TAGS = {"Wall", "Rock", "Machine"}


def normalize_heading(angle):
    return angle % 360.0


def normalize_signed_angle(angle):
    return ((angle + 180.0) % 360.0) - 180.0


def critter_debug(memory, channel, message):
    if memory is None:
        return
    if not getattr(memory, "debug_enabled", False):
        return

    last_message = memory.debug_messages.get(channel)
    if last_message == message:
        return

    memory.debug_messages[channel] = message
    print(f"[CritterDebug:{channel}] {message}")


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


def find_tracking_astronaut(aagent):
    sensor_obj_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
    candidates = []

    for index, value in enumerate(sensor_obj_info):
        if not value or not is_target_tag(value["tag"], ASTRONAUT_TAG_FRAGMENTS):
            continue

        candidates.append({
            "index": index,
            "distance": value["distance"],
            "angle": sensor_angles[index],
            "tag": value["tag"],
        })

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: (abs(candidate["angle"]), candidate["distance"]))
    selected = candidates[0]
    selected["astronaut_ray_count"] = len(candidates)
    return selected


def is_front_path_blocked(aagent, distance_threshold=1.2, max_angle=25.0):
    sensor_obj_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]

    for index, value in enumerate(sensor_obj_info):
        if abs(sensor_angles[index]) > max_angle:
            continue
        if not value or value["tag"] not in CHASE_IMPASSABLE_TAGS:
            continue
        if value["distance"] <= distance_threshold:
            return True

    return False


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
        self.last_target_world_heading = 0.0
        self.chase_blocked_ticks = 0
        self.debug_enabled = False
        self.debug_messages = {}


def update_target_memory(memory, target, aagent, hold_seconds=0.6):
    if target is None:
        return

    memory.target_lock_until = time.monotonic() + hold_seconds
    memory.last_target_angle = target["angle"]
    memory.last_target_distance = target["distance"]
    memory.last_target_world_heading = normalize_heading(aagent.i_state.rotation["y"] + target["angle"])


def get_chase_target(aagent, memory):
    visible_target = find_closest_astronaut(aagent)
    if visible_target is not None:
        update_target_memory(memory, visible_target, aagent)
        visible_target["remembered"] = False
        return visible_target

    if time.monotonic() < memory.target_lock_until and memory.last_target_distance is not None:
        current_heading = aagent.i_state.rotation["y"]
        return {
            "index": None,
            "distance": memory.last_target_distance,
            "angle": normalize_signed_angle(memory.last_target_world_heading - current_heading),
            "tag": "AstronautMemory",
            "remembered": True,
        }

    return None


def clear_target_memory(memory):
    memory.target_lock_until = 0.0
    memory.last_target_angle = 0.0
    memory.last_target_distance = None
    memory.last_target_world_heading = 0.0


class BN_ShouldRetreat(pt.behaviour.Behaviour):
    def __init__(self, memory):
        super(BN_ShouldRetreat, self).__init__("BN_ShouldRetreat")
        self.memory = memory

    def initialise(self):
        pass

    def update(self):
        if self.memory.retreat_requested:
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
        if time.monotonic() < self.memory.cooldown_until:
            critter_debug(self.memory, "detect", "cooldown_active")
            return pt.common.Status.FAILURE
        target = find_tracking_astronaut(self.my_agent)
        if target is not None:
            critter_debug(
                self.memory,
                "detect",
                f"target distance={target['distance']:.2f} angle={target['angle']:.1f} rays={target.get('astronaut_ray_count', 1)} remembered=False",
            )
            return pt.common.Status.SUCCESS
        critter_debug(self.memory, "detect", "no_target")
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_CanAttackAstronaut(pt.behaviour.Behaviour):
    ATTACK_DISTANCE = 0.8
    ATTACK_ANGLE = 45.0
    GUARANTEED_CONTACT_DISTANCE = 0.6

    def __init__(self, aagent):
        super(BN_CanAttackAstronaut, self).__init__("BN_CanAttackAstronaut")
        self.my_agent = aagent
        self.memory = None

    def initialise(self):
        pass

    def update(self):
        target = find_closest_astronaut(self.my_agent)
        if target and (
            target["distance"] <= self.GUARANTEED_CONTACT_DISTANCE
            or (target["distance"] <= self.ATTACK_DISTANCE and abs(target["angle"]) <= self.ATTACK_ANGLE)
        ):
            critter_debug(
                self.memory,
                "attack",
                f"contact distance={target['distance']:.2f} angle={target['angle']:.1f}",
            )
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_StartRetreat(pt.behaviour.Behaviour):
    RECOVERY_SECONDS = 5.0

    def __init__(self, memory):
        super(BN_StartRetreat, self).__init__("BN_StartRetreat")
        self.memory = memory

    def initialise(self):
        pass

    def update(self):
        self.memory.cooldown_until = time.monotonic() + self.RECOVERY_SECONDS
        clear_target_memory(self.memory)
        self.memory.retreat_requested = True
        critter_debug(self.memory, "retreat", f"start cooldown={self.RECOVERY_SECONDS:.1f}s")
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
            critter_debug(self.memory, "retreat", "execute")
            self.my_goal = asyncio.create_task(self._run_retreat())

    def update(self):
        if self.my_goal is not None:
            if not self.my_goal.done():
                return pt.common.Status.RUNNING
            goal_succeeded = self.my_goal.result()
            self.my_goal = None
            if not goal_succeeded:
                critter_debug(self.memory, "retreat", "retry")
                self.my_goal = asyncio.create_task(self._run_retreat())
                return pt.common.Status.RUNNING
            critter_debug(self.memory, "retreat", "success")
            return pt.common.Status.SUCCESS

        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BN_ChaseAstronaut(pt.behaviour.Behaviour):
    CLOSE_COMMIT_DISTANCE = 1.2
    CHARGE_ANGLE = 15.0
    TURN_BURST_SECONDS = 0.16
    FORWARD_BURST_SECONDS = 0.30
    BLOCKED_TURN_SECONDS = 0.22

    def __init__(self, aagent, memory):
        super(BN_ChaseAstronaut, self).__init__("BN_ChaseAstronaut")
        self.my_agent = aagent
        self.memory = memory
        self.last_translation = None
        self.last_rotation = None
        self.last_translation_sent_at = 0.0
        self.phase = None
        self.phase_until = 0.0
        self.phase_rotation = "nt"
        self.phase_label = ""
        self.forward_after_turn = False

    def _translation_matches(self, translation):
        if translation == "mf":
            return self.my_agent.i_state.movingForwards and not self.my_agent.i_state.movingBackwards
        if translation == "mb":
            return self.my_agent.i_state.movingBackwards and not self.my_agent.i_state.movingForwards
        if translation == "ntm":
            return not self.my_agent.i_state.movingForwards and not self.my_agent.i_state.movingBackwards
        return False

    def _queue_action(self, action):
        asyncio.create_task(self.my_agent.send_message("action", action))

    def _set_motion(self, translation=None, rotation=None):
        now = time.monotonic()
        if (
            translation is not None
            and (
                translation != self.last_translation
                or not self._translation_matches(translation)
                or now - self.last_translation_sent_at >= 0.2
            )
        ):
            self.last_translation = translation
            self.last_translation_sent_at = now
            self._queue_action(translation)

        if rotation is not None and rotation != self.last_rotation:
            self.last_rotation = rotation
            self._queue_action(rotation)

    def _set_logged_motion(self, label, translation, rotation, target):
        self._set_motion(translation, rotation)
        critter_debug(
            self.memory,
            "chase",
            f"{label} distance={target['distance']:.2f} angle={target['angle']:.1f} rays={target.get('astronaut_ray_count', 1)} remembered={target.get('remembered', False)} blocked_ticks={self.memory.chase_blocked_ticks}",
        )

    def _start_turn_burst(self, label, rotation, target, duration, *, forward_after_turn=False):
        self.phase = "turn"
        self.phase_until = time.monotonic() + duration
        self.phase_rotation = rotation
        self.phase_label = label
        self.forward_after_turn = forward_after_turn
        self._set_logged_motion(label, "ntm", rotation, target)

    def _start_forward_burst(self, label, target, duration=None):
        self.phase = "forward"
        self.phase_until = time.monotonic() + (duration or self.FORWARD_BURST_SECONDS)
        self.phase_rotation = "nt"
        self.phase_label = label
        self.forward_after_turn = False
        self._set_logged_motion(label, "mf", "nt", target)

    def initialise(self):
        self.last_translation = None
        self.last_rotation = None
        self.last_translation_sent_at = 0.0
        self.memory.chase_blocked_ticks = 0
        self.phase = None
        self.phase_until = 0.0
        self.phase_rotation = "nt"
        self.phase_label = ""
        self.forward_after_turn = False

    def update(self):
        target = find_tracking_astronaut(self.my_agent)
        if target is None:
            self.memory.chase_blocked_ticks = 0
            clear_target_memory(self.memory)
            self.phase = None
            self.phase_until = 0.0
            self.phase_label = ""
            self.forward_after_turn = False
            self._set_motion("ntm", "nt")
            critter_debug(self.memory, "chase", "lost_target -> roam")
            return pt.common.Status.FAILURE

        now = time.monotonic()

        if is_front_path_blocked(self.my_agent):
            self.memory.chase_blocked_ticks += 1
            turn_direction = choose_clear_turn_direction(self.my_agent)
            self._start_turn_burst(
                "blocked_turn",
                "tr" if turn_direction > 0 else "tl",
                target,
                self.BLOCKED_TURN_SECONDS,
                forward_after_turn=False,
            )
            return pt.common.Status.RUNNING

        self.memory.chase_blocked_ticks = 0

        if self.phase is not None and now < self.phase_until:
            if self.phase == "turn":
                self._set_logged_motion(self.phase_label, "ntm", self.phase_rotation, target)
            else:
                self._set_logged_motion(self.phase_label, "mf", "nt", target)
            return pt.common.Status.RUNNING

        self.phase = None

        if self.forward_after_turn:
            self._start_forward_burst("forward_burst", target)
        elif target["distance"] <= self.CLOSE_COMMIT_DISTANCE:
            self._start_forward_burst("close_commit", target, duration=0.36)
        elif abs(target["angle"]) <= self.CHARGE_ANGLE:
            self._start_forward_burst("charge", target)
        else:
            self._start_turn_burst(
                "turn_burst",
                "tr" if target["angle"] > 0 else "tl",
                target,
                self.TURN_BURST_SECONDS,
                forward_after_turn=True,
            )
        return pt.common.Status.RUNNING

    def terminate(self, new_status: common.Status):
        self._queue_action("stop")
        self.last_translation = None
        self.last_rotation = None
        self.last_translation_sent_at = 0.0
        self.memory.chase_blocked_ticks = 0
        self.phase = None
        self.phase_until = 0.0
        self.phase_label = ""
        self.forward_after_turn = False


class BTCritter:
    def __init__(self, aagent):
        self.aagent = aagent
        self.memory = CritterMemory()
        self.memory.debug_enabled = bool(getattr(aagent, "AgentParameters", {}).get("debug_mode", False))

        retreat = pt.composites.Sequence(name="Retreat", memory=True)
        retreat.add_children([
            BN_ShouldRetreat(self.memory),
            BN_ExecuteRetreat(aagent, self.memory),
        ])

        attack_check = BN_CanAttackAstronaut(aagent)
        attack_check.memory = self.memory
        attack = pt.composites.Sequence(name="AttackAstronaut", memory=False)
        attack.add_children([
            attack_check,
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
            use_reverse_escape=False,
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
        critter_debug(
            self.memory,
            "tree",
            " | ".join(f"{child.name}={child.status.name}" for child in self.root.children),
        )
        await asyncio.sleep(0)
