import asyncio
import random

import py_trees as pt
from py_trees import common

import Goals_BT_Basic
import Sensors


# Objects with these tags are treated as solid obstacles during roaming.
IMPASSABLE_OBJECT_TAGS = {"Wall", "Rock", "Machine"}


# This object stores the small amount of state that all roaming nodes share.
# The important field is consecutive_failures:
# - it increases when a forward move fails
# - it is reset when a forward move succeeds
# The other fields are configuration values that slightly change how roaming
# behaves for different agents.
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
        # How many forward attempts in a row have failed.
        self.consecutive_failures = 0

        # Extra tags that a caller may also want to treat as blocking.
        # Example: a critter can decide flowers should also be avoided.
        self.extra_impassable_tags = set(extra_impassable_tags or ())

        # If True, the escape branch starts by moving backwards first.
        self.use_reverse_escape = use_reverse_escape

        # If True, escape can also trigger when the front area stays blocked.
        self.escape_on_front_blocked = escape_on_front_blocked

        # How close an obstacle in front must be to count as "blocked".
        self.front_blocked_distance = front_blocked_distance

        # Only rays inside this front cone are checked for "front blocked".
        self.front_blocked_angle = front_blocked_angle

        # If True, roaming tries not to scrape walls on its left or right.
        self.avoid_side_walls = avoid_side_walls

        # Distance used to decide whether a side wall is "too close".
        self.side_wall_distance = side_wall_distance

        # Small bonus for central rays so the agent prefers straighter movement
        # when two directions are similarly open.
        self.center_bias_weight = center_bias_weight


def is_impassable(ray_info, memory):
    # No hit means no obstacle on that ray.
    if not ray_info:
        return False

    # Standard hard obstacles always block movement.
    if ray_info["tag"] in IMPASSABLE_OBJECT_TAGS:
        return True

    # Some trees can add their own extra obstacle tags.
    if ray_info["tag"] in memory.extra_impassable_tags:
        return True

    return False


# This node only decides whether the roaming tree should use the escape branch.
# It does not move the agent by itself.
class BN_ShouldEscape(pt.behaviour.Behaviour):
    def __init__(self, aagent, memory):
        super(BN_ShouldEscape, self).__init__("BN_ShouldEscape")
        self.aagent = aagent
        self.memory = memory

    def initialise(self):
        pass

    def update(self):
        # If several forward moves failed in a row, stop normal roaming and
        # force an escape turn.
        if self.memory.consecutive_failures >= 2:
            return pt.common.Status.SUCCESS

        # Some trees do not use the "front blocked" rule.
        if not self.memory.escape_on_front_blocked:
            return pt.common.Status.FAILURE

        # The front blocked check is only useful after at least one failed
        # movement, otherwise the agent would escape too eagerly.
        if self.memory.consecutive_failures == 0:
            return pt.common.Status.FAILURE

        sensor_obj_info = self.aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        sensor_angles = self.aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]

        for index, value in enumerate(sensor_obj_info):
            # Ignore rays that are too far from the center.
            if abs(sensor_angles[index]) > self.memory.front_blocked_angle:
                continue

            # If a blocking object is close enough in front, switch to escape.
            if is_impassable(value, self.memory):
                if value["distance"] <= self.memory.front_blocked_distance:
                    return pt.common.Status.SUCCESS

        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


# Optional first step of the escape branch.
# Some agents back away before turning, and some skip this completely.
class BN_RoamBackOff(pt.behaviour.Behaviour):
    def __init__(self, aagent, memory):
        super(BN_RoamBackOff, self).__init__("BN_RoamBackOff")
        self.my_agent = aagent
        self.memory = memory
        self.my_goal = None

    def initialise(self):
        # If reverse escape is disabled, this node succeeds immediately and the
        # tree continues to the turn step.
        if not self.memory.use_reverse_escape:
            self.my_goal = None
            return

        # Move backwards a little to create space before turning away.
        self.my_goal = asyncio.create_task(
            Goals_BT_Basic.BackwardDist(self.my_agent, random.uniform(0.7, 1.4), 0, 0).run()
        )

    def update(self):
        # No goal means there is nothing to do.
        if self.my_goal is None:
            return pt.common.Status.SUCCESS

        # Standard async-goal pattern:
        # - RUNNING while the goal is still executing
        # - SUCCESS or FAILURE when the goal finishes
        if not self.my_goal.done():
            return pt.common.Status.RUNNING

        if self.my_goal.result():
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        # If the tree leaves this node early, cancel the unfinished goal.
        if self.my_goal is not None:
            self.my_goal.cancel()


# This node decides which direction the agent should face next.
# It is used both in normal roaming and in escape mode.
class BN_RoamTurn(pt.behaviour.Behaviour):
    MIN_TURN_THRESHOLD = 7.0

    def __init__(self, aagent, memory):
        super(BN_RoamTurn, self).__init__("BN_RoamTurn")
        self.my_agent = aagent
        self.memory = memory
        self.my_goal = None

    def initialise(self):
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        sensor_angles = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
        ray_length = self.my_agent.rc_sensor.ray_length
        max_angle = max(1.0, float(self.my_agent.rc_sensor.max_ray_degrees))

        # left_wall_distance / right_wall_distance:
        # nearest blocking obstacle found on each side.
        left_wall_distance = ray_length
        right_wall_distance = ray_length

        # left_open_space / right_open_space:
        # total visible free space on each side.
        left_open_space = 0.0
        right_open_space = 0.0

        # best_angle:
        # the direction that currently looks best for normal roaming.
        best_angle = 0.0
        best_clearance = 0.0
        best_score = -1.0

        # front_blocked becomes True if the front cone is still blocked after a
        # failed move. This pushes the tree into a stronger escape turn.
        front_blocked = False

        for index, value in enumerate(sensor_obj_info):
            angle = sensor_angles[index]

            # Each ray contributes a "clearance" value:
            # - obstacle distance if blocked
            # - full ray length if open
            if is_impassable(value, self.memory):
                clearance = value["distance"]
            else:
                clearance = ray_length

            # Keep track of open space on both sides so escape turns can go
            # towards the clearer side.
            if angle < 0:
                left_open_space += clearance
            elif angle > 0:
                right_open_space += clearance

            # Side wall avoidance only cares about hard walls.
            if is_impassable(value, self.memory):
                if angle < 0:
                    left_wall_distance = min(left_wall_distance, value["distance"])
                elif angle > 0:
                    right_wall_distance = min(right_wall_distance, value["distance"])

            # Front blocked check is used when the previous move failed.
            if (
                self.memory.escape_on_front_blocked
                and self.memory.consecutive_failures > 0
                and abs(angle) <= self.memory.front_blocked_angle
                and is_impassable(value, self.memory)
                and value["distance"] <= self.memory.front_blocked_distance
            ):
                front_blocked = True

            # Normal roaming does not just choose the farthest ray.
            # It also gives a small bonus to central rays so the movement looks
            # smoother and less zig-zaggy.
            center_bias = 1.0 - (abs(angle) / max_angle)

            # After a failure, reduce the center bonus so the agent is more
            # willing to take a wider turn.
            if self.memory.consecutive_failures > 0:
                center_bias *= 0.3

            score = clearance + (self.memory.center_bias_weight * center_bias)

            # Keep the best-scoring ray found so far.
            if score > best_score:
                best_score = score
                best_clearance = clearance
                best_angle = angle

        # Priority order:
        # 1. Turn inward if the agent is scraping a side wall.
        # 2. If it just failed or the front is blocked, do a large escape turn.
        # 3. Otherwise, turn towards the clearest ray.
        if (
            self.memory.avoid_side_walls
            and left_wall_distance <= self.memory.side_wall_distance
            and right_wall_distance > left_wall_distance + 0.5
        ):
            # Wall too close on the left, so turn right.
            chosen_angle = random.uniform(25, 65)
        elif (
            self.memory.avoid_side_walls
            and right_wall_distance <= self.memory.side_wall_distance
            and left_wall_distance > right_wall_distance + 0.5
        ):
            # Wall too close on the right, so turn left.
            chosen_angle = -random.uniform(25, 65)
        elif front_blocked or self.memory.consecutive_failures >= 2:
            # Escape mode: make a big turn toward the side with more open space.
            if left_open_space == right_open_space:
                chosen_angle = random.choice([-1, 1]) * random.uniform(110, 170)
            elif right_open_space > left_open_space:
                chosen_angle = random.uniform(110, 170)
            else:
                chosen_angle = -random.uniform(110, 170)
        elif best_clearance < 1.5 and abs(best_angle) < 15:
            # If the best direction is still narrow and almost straight ahead,
            # force a wider turn instead of walking into a cramped area.
            chosen_angle = random.choice([-1, 1]) * random.uniform(90, 150)
        else:
            # Normal case: face the best direction found by the ray scan.
            chosen_angle = best_angle

        # Tiny turns are not worth creating a goal for.
        if abs(chosen_angle) < self.MIN_TURN_THRESHOLD:
            self.my_goal = None
            return

        # Start the actual turn goal.
        self.my_goal = asyncio.create_task(
            Goals_BT_Basic.Turn_customizable(self.my_agent, 0, chosen_angle).run()
        )

    def update(self):
        # No goal means we decided no turn was necessary.
        if self.my_goal is None:
            return pt.common.Status.SUCCESS

        if not self.my_goal.done():
            return pt.common.Status.RUNNING

        if self.my_goal.result():
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


# This node decides how far to move forward after the turn is done.
class BN_RoamForward(pt.behaviour.Behaviour):
    MIN_TRAVEL_DISTANCE = 1.0

    def __init__(self, aagent, memory):
        super(BN_RoamForward, self).__init__("BN_RoamForward")
        self.my_agent = aagent
        self.memory = memory
        self.my_goal = None
        self.blocked = False

    def initialise(self):
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        sensor_angles = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
        central_ray_index = self.my_agent.rc_sensor.central_ray_index
        ray_length = self.my_agent.rc_sensor.ray_length

        self.blocked = False

        # After a failure, use a shorter move so the agent can recover more
        # carefully. Otherwise, use a longer normal roaming move.
        if self.memory.consecutive_failures > 0:
            target_distance = random.uniform(1.5, 3.0)
        else:
            target_distance = random.uniform(2.5, 5.0)

        # We only need three measurements here:
        # - nearest wall on the left
        # - nearest wall on the right
        # - clearance straight ahead
        left_wall_distance = ray_length
        right_wall_distance = ray_length
        front_clearance = ray_length

        for index, value in enumerate(sensor_obj_info):
            angle = sensor_angles[index]

            # Side distances are used to shorten the move if we are too close to
            # a wall while roaming along it.
            if is_impassable(value, self.memory):
                if angle < 0:
                    left_wall_distance = min(left_wall_distance, value["distance"])
                elif angle > 0:
                    right_wall_distance = min(right_wall_distance, value["distance"])

            # The central ray tells us whether there is enough room straight
            # ahead for the chosen forward distance.
            if index == central_ray_index and is_impassable(value, self.memory):
                front_clearance = value["distance"]

        # If there is a wall very close to one side, shorten the forward step.
        if self.memory.avoid_side_walls:
            if min(left_wall_distance, right_wall_distance) <= self.memory.side_wall_distance:
                target_distance = min(target_distance, random.uniform(1.2, 2.2))

        # Never choose a distance that would hit the obstacle in front.
        if front_clearance < ray_length:
            target_distance = min(target_distance, front_clearance - 0.75)

        # If there is not even enough room for a minimal move, mark this node
        # as blocked. The update() method will count it as a failure.
        if target_distance < self.MIN_TRAVEL_DISTANCE:
            self.blocked = True
            self.my_goal = None
            return

        # Start the actual forward goal.
        self.my_goal = asyncio.create_task(
            Goals_BT_Basic.ForwardDist(self.my_agent, target_distance, 0, 0).run()
        )

    def update(self):
        # No movement was possible, so tell the tree this attempt failed.
        if self.blocked:
            self.memory.consecutive_failures += 1
            return pt.common.Status.FAILURE

        if not self.my_goal.done():
            return pt.common.Status.RUNNING

        # Successful move: clear the failure counter.
        if self.my_goal.result():
            self.memory.consecutive_failures = 0
            return pt.common.Status.SUCCESS

        # Failed move: remember it so the escape branch can react next tick.
        self.memory.consecutive_failures += 1
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


# This helper builds the whole roaming subtree used by the other behavior trees.
#
# Tree structure:
# - Selector
#   - Escape sequence
#   - Normal roaming sequence
#
# Because the root is a selector, escape has priority over normal roaming.
# Because the root uses memory=False, escape is checked again every tick.
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
    # All roaming nodes share the same memory object.
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

    # Escape branch:
    # 1. Decide whether the agent is stuck enough to escape.
    # 2. Optionally back away first.
    # 3. Turn to a safer direction.
    # 4. Try a shorter, safer forward move.
    #
    # memory=True means that if one child is RUNNING, next tick the sequence
    # continues from that child instead of starting again from the first one.
    escape = pt.composites.Sequence(name=f"{name}_Escape", memory=True)
    escape.add_children([
        BN_ShouldEscape(aagent, memory),
        BN_RoamBackOff(aagent, memory),
        BN_RoamTurn(aagent, memory),
        BN_RoamForward(aagent, memory),
    ])

    # Normal roaming branch:
    # 1. Pick a good direction from the ray sensor data.
    # 2. Move forward in that direction.
    roaming = pt.composites.Sequence(name=f"{name}_Normal", memory=True)
    roaming.add_children([
        BN_RoamTurn(aagent, memory),
        BN_RoamForward(aagent, memory),
    ])

    # Root selector:
    # - try escape first
    # - if escape is not needed, use normal roaming
    root = pt.composites.Selector(name=name, memory=False)
    root.add_children([escape, roaming])
    return root
