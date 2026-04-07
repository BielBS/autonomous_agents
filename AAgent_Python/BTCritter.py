import asyncio
import random

import py_trees as pt
from py_trees import common

import BNs_SmartRoam
import Goals_BT_Basic
import Sensors


class BN_CanTouchAstronaut(pt.behaviour.Behaviour):
    TOUCH_DISTANCE = 0.6

    def __init__(self, aagent):
        super(BN_CanTouchAstronaut, self).__init__("BN_CanTouchAstronaut")
        self.my_agent = aagent

    def initialise(self):
        pass

    def update(self):
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]

        for value in sensor_obj_info:
            if (
                value
                and "Astronaut" in value["tag"]
                and value["distance"] <= self.TOUCH_DISTANCE
            ):
                return pt.common.Status.SUCCESS

        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_MoveToAstronaut(pt.behaviour.Behaviour):
    MOVE_ANGLE = 20.0
    MAX_FORWARD_STEP = 2.5

    def __init__(self, aagent):
        self.my_goal = None
        super(BN_MoveToAstronaut, self).__init__("BN_MoveToAstronaut")
        self.my_agent = aagent

    def initialise(self):
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        sensor_angles = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]

        for index, value in enumerate(sensor_obj_info):
            if not value or "Astronaut" not in value["tag"]:
                continue

            # Keep moving if the astronaut is already roughly in front. This
            # avoids the left-right jitter caused by demanding the exact center
            # ray before every forward step.
            if abs(sensor_angles[index]) <= self.MOVE_ANGLE:
                self.my_goal = asyncio.create_task(
                    Goals_BT_Basic.ForwardDist(
                        self.my_agent,
                        min(value["distance"], self.MAX_FORWARD_STEP),
                        0,
                        0,
                    ).run()
                )
            else:
                self.my_goal = asyncio.create_task(
                    Goals_BT_Basic.Turn_customizable(self.my_agent, 0, sensor_angles[index]).run()
                )
            return

        self.my_goal = None

    def update(self):
        if self.my_goal is None:
            return pt.common.Status.FAILURE

        if not self.my_goal.done():
            return pt.common.Status.RUNNING

        if self.my_goal.result():
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BN_RetreatFromAstronaut(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_RetreatFromAstronaut, self).__init__("BN_RetreatFromAstronaut")
        self.my_agent = aagent

    async def retreat(self, astronaut_angle):
        # Step 1: move backward to stop touching the astronaut.
        backed_off = await Goals_BT_Basic.BackwardDist(
            self.my_agent,
            1.0,
            0,
            0,
        ).run()

        # Step 2: turn away from the astronaut.
        if abs(astronaut_angle) < 5:
            retreat_turn = random.choice([-150, 150])
        elif astronaut_angle > 0:
            retreat_turn = -150
        else:
            retreat_turn = 150

        turned = await Goals_BT_Basic.Turn_customizable(
            self.my_agent,
            0,
            retreat_turn,
        ).run()
        if not turned:
            return False

        # Step 3: move forward so the critter keeps some distance afterwards.
        escaped = await Goals_BT_Basic.ForwardDist(
            self.my_agent,
            5.0,
            0,
            0,
        ).run()
        return bool(backed_off or escaped)

    def initialise(self):
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        sensor_angles = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]

        astronaut_angle = 0.0

        for index, value in enumerate(sensor_obj_info):
            if value and "Astronaut" in value["tag"]:
                astronaut_angle = sensor_angles[index]
                break

        self.my_goal = asyncio.create_task(self.retreat(astronaut_angle))

    def update(self):
        if not self.my_goal.done():
            return pt.common.Status.RUNNING

        if self.my_goal.result():
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        if self.my_goal is not None:
            self.my_goal.cancel()


class BTCritter:
    def __init__(self, aagent):
        self.aagent = aagent

        # Priority order:
        # 1. If the critter is already touching the astronaut, retreat.
        # 2. If the astronaut is visible but not in touch range, move towards it.
        # 3. If no astronaut is visible, roam around the map.
        touch_astronaut = pt.composites.Sequence(name="TouchAstronaut", memory=True)
        touch_astronaut.add_children([
            BN_CanTouchAstronaut(aagent),
            BN_RetreatFromAstronaut(aagent),
        ])

        move_to_astronaut = BN_MoveToAstronaut(aagent)

        smart_roaming = BNs_SmartRoam.create_roaming_subtree(
            aagent,
            name="SmartRoaming",
            extra_impassable_tags={"AlienFlower", "Location", "Container"},
            use_reverse_escape=True,
            escape_on_front_blocked=True,
            front_blocked_distance=1.6,
            avoid_side_walls=True,
            side_wall_distance=2.0,
            center_bias_weight=1.0,
        )

        self.root = pt.composites.Selector(name="Selector", memory=False)
        self.root.add_children([
            touch_astronaut,
            move_to_astronaut,
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
