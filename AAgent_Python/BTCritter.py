import asyncio
import random

import py_trees as pt
from py_trees import common

import BNs_SmartRoam
import Goals_BT_Basic
import Sensors


def get_astronaut(aagent):
    sensor_obj_info = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
    sensor_angles = aagent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]

    for index, value in enumerate(sensor_obj_info):
        if value:
            if "Astronaut" in value["tag"]:
                return {
                    "distance": value["distance"],
                    "angle": sensor_angles[index],
                    "index": index,
                }

    return None


class BN_DetectAstronaut(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_DetectAstronaut, self).__init__("BN_DetectAstronaut")
        self.my_agent = aagent

    def initialise(self):
        pass

    def update(self):
        if get_astronaut(self.my_agent):
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_CanTouchAstronaut(pt.behaviour.Behaviour):
    TOUCH_DISTANCE = 0.6
    TOUCH_ANGLE = 18.0

    def __init__(self, aagent):
        self.my_goal = None
        super(BN_CanTouchAstronaut, self).__init__("BN_CanTouchAstronaut")
        self.my_agent = aagent

    def initialise(self):
        pass

    def update(self):
        astronaut = get_astronaut(self.my_agent)
        if astronaut is None:
            return pt.common.Status.FAILURE

        if astronaut["distance"] <= self.TOUCH_DISTANCE and abs(astronaut["angle"]) <= self.TOUCH_ANGLE:
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass


class BN_MoveToAstronaut(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_MoveToAstronaut, self).__init__("BN_MoveToAstronaut")
        self.my_agent = aagent

    def initialise(self):
        astronaut = get_astronaut(self.my_agent)
        central_ray_index = self.my_agent.rc_sensor.central_ray_index

        if astronaut is None:
            self.my_goal = None
        elif astronaut["index"] == central_ray_index:
            self.my_goal = asyncio.create_task(
                Goals_BT_Basic.ForwardDist(self.my_agent, astronaut["distance"], 0, 5).run()
            )
        else:
            self.my_goal = asyncio.create_task(
                Goals_BT_Basic.Turn_customizable(self.my_agent, 0, astronaut["angle"]).run()
            )

    def update(self):
        if self.my_goal is None:
            return pt.common.Status.FAILURE

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


class BN_RetreatFromAstronaut(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_RetreatFromAstronaut, self).__init__("BN_RetreatFromAstronaut")
        self.my_agent = aagent

    async def retreat(self, astronaut_angle):
        backed_off = await Goals_BT_Basic.BackwardDist(
            self.my_agent,
            random.uniform(0.8, 1.4),
            0,
            0,
        ).run()

        if abs(astronaut_angle) < 5:
            retreat_turn = random.choice([-1, 1]) * random.uniform(145, 180)
        elif astronaut_angle > 0:
            retreat_turn = -random.uniform(130, 175)
        else:
            retreat_turn = random.uniform(130, 175)

        turned = await Goals_BT_Basic.Turn_customizable(self.my_agent, 0, retreat_turn).run()
        if not turned:
            return False

        escaped = await Goals_BT_Basic.ForwardDist(
            self.my_agent,
            random.uniform(4.5, 6.5),
            0,
            0,
        ).run()
        return bool(backed_off or escaped)

    def initialise(self):
        astronaut = get_astronaut(self.my_agent)
        if astronaut is None:
            self.my_goal = asyncio.create_task(self.retreat(0.0))
        else:
            self.my_goal = asyncio.create_task(self.retreat(astronaut["angle"]))

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


class BTCritter:
    def __init__(self, aagent):
        self.aagent = aagent

        touch_astronaut = pt.composites.Sequence(name="TouchAstronaut", memory=True)
        touch_astronaut.add_children([
            BN_CanTouchAstronaut(aagent),
            BN_RetreatFromAstronaut(aagent),
        ])

        engage_astronaut = pt.composites.Sequence(name="EngageAstronaut", memory=True)
        engage_astronaut.add_children([
            BN_DetectAstronaut(aagent),
            pt.composites.Selector(name="TouchOrMove", memory=False, children=[
                touch_astronaut,
                BN_MoveToAstronaut(aagent),
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
            engage_astronaut,
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
