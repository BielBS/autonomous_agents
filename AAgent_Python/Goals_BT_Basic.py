import math
import random
import asyncio
import Sensors
from collections import Counter

def calculate_distance(point_a, point_b):
    distance = math.sqrt((point_b['x'] - point_a['x']) ** 2 +
                         (point_b['y'] - point_a['y']) ** 2 +
                         (point_b['z'] - point_a['z']) ** 2)
    return distance

class DoNothing:
    """
    Does nothing
    """
    def __init__(self, a_agent):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state

    async def run(self):
        print("Doing nothing")
        await asyncio.sleep(1)
        return True

class ForwardStop:
    """
        Moves forward till it finds an obstacle. Then stops.
    """
    STOPPED = 0
    MOVING = 1
    END = 2

    def __init__(self, a_agent):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state
        self.state = self.STOPPED

    async def run(self):
        try:
            while True:
                if self.state == self.STOPPED:
                    # Start moving
                    await self.a_agent.send_message("action", "mf")
                    self.state = self.MOVING
                elif self.state == self.MOVING:
                    sensor_hits = self.rc_sensor.sensor_rays[Sensors.RayCastSensor.HIT]
                    if any(ray_hit == 1 for ray_hit in sensor_hits):
                        self.state = self.END
                        await self.a_agent.send_message("action", "stop")
                    else:
                        await asyncio.sleep(0)
                elif self.state == self.END:
                    break
                else:
                    print("Unknown state: " + str(self.state))
                    return False
        except asyncio.CancelledError:
            print("***** TASK Forward CANCELLED")
            await self.a_agent.send_message("action", "stop")
            self.state = self.STOPPED

class ForwardDist:
    """
        Moves forward a certain distance specified in the parameter "dist".
        If "dist" is -1, selects a random distance between the initial
        parameters of the class "d_min" and "d_max"
    """
    STOPPED = 0
    MOVING = 1
    END = 2

    def __init__(self, a_agent, dist, d_min, d_max):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state
        self.original_dist = dist
        self.target_dist = dist
        self.d_min = d_min
        self.d_max = d_max
        self.starting_pos = a_agent.i_state.position
        self.state = self.STOPPED

    async def run(self):
        try:
            previous_dist = 0.0  # Used to detect if we are stuck
            while True:
                if self.state == self.STOPPED:
                    # starting position before moving
                    self.starting_pos = self.a_agent.i_state.position
                    # Before start moving, calculate the distance we want to move
                    if self.original_dist < 0:
                        self.target_dist = random.randint(self.d_min, self.d_max)
                    else:
                        self.target_dist = self.original_dist
                    # Start moving
                    await self.a_agent.send_message("action", "mf")
                    self.state = self.MOVING
                    # print("TARGET DISTANCE: " + str(self.target_dist))
                elif self.state == self.MOVING:
                    # If we are moving
                    await asyncio.sleep(0.5)  # Wait for a little movement
                    current_dist = calculate_distance(self.starting_pos, self.i_state.position)
                    #print(f"Current distance: {current_dist}")
                    if current_dist >= self.target_dist:  # Check if we already have covered the required distance
                        await self.a_agent.send_message("action", "ntm")
                        self.state = self.STOPPED
                        # print("DESTINATION REACHED")
                        return True
                    elif previous_dist == current_dist:  # We are not moving
                        # print(f"previous dist: {previous_dist}, current dist: {current_dist}")
                        # print("NOT MOVING")
                        await self.a_agent.send_message("action", "ntm")
                        self.state = self.STOPPED
                        return False
                    previous_dist = current_dist
                else:
                    print("Unknown state: " + str(self.state))
                    return False
        except asyncio.CancelledError:
            print("***** TASK Forward CANCELLED")
            await self.a_agent.send_message("action", "ntm")
            self.state = self.STOPPED

# I have DELETED the given Turn class, the Turn_customizable class is it's replacement it does the same thing but instead of using random values it uses given ones
# to recreate the previous class simply create a Turn_customaizable(a_agent,random.choice([-1,1]),random.uniform(1,180))
########## New Goals from here downward #########

class Turn_customizable:
    """
    The action of turning a given set of degrees in a given direction (right or left)
    
    Possible BUG:Sometimes it keeps truning over and over, probably because it skips over the desired heading and does another full turn
        Added TURN_THRESHOLD instead of magic number and changed it from 5 to 10, in an attempt to fix it
    
    """
    LEFT = -1
    RIGHT = 1

    SELECTING = 0
    TURNING = 1

    TURN_THRESHOLD=10


    def __init__(self, a_agent,direction,degrees):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state

        self.current_heading = 0
        self.new_heading = 0

        self.state = self.SELECTING

        self.direction=direction
        self.degrees=degrees

    async def run(self):
        try:
            while True:
                if self.state == self.SELECTING:
                    # print("SELECTING NEW TURN")
                    rotation_direction = self.direction
                    # print(f"Rotation direction: {rotation_direction}")
                    rotation_degrees = self.degrees * rotation_direction
                    # print("Degrees: " + str(rotation_degrees))
                    current_heading = self.i_state.rotation["y"]
                    # print(f"Current heading: {current_heading}")
                    self.new_heading = (current_heading + rotation_degrees) % 360
                    if self.new_heading == 360:
                        self.new_heading = 0.0
                    # print(f"New heading: {self.new_heading}")
                    if rotation_direction == self.RIGHT:
                        await self.a_agent.send_message("action", "tr")
                    else:
                        await self.a_agent.send_message("action", "tl")
                    self.state = self.TURNING
                elif self.state == self.TURNING:
                    # check if we have finished the rotation
                    current_heading = self.i_state.rotation["y"]
                    final_condition = abs(current_heading - self.new_heading)
                    if final_condition < self.TURN_THRESHOLD:
                        await self.a_agent.send_message("action", "nt")
                        current_heading = self.i_state.rotation["y"]
                        # print(f"Current heading: {current_heading}")
                        # print("TURNING DONE.")
                        self.state = self.SELECTING
                        return True
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            print("***** TASK Turn_customizable CANCELLED")
            await self.a_agent.send_message("action", "nt")


from AAgent_BT import AAgent

"""
WIP
Teleports to a given destination
"""
class Teleport_To:


    def __init__(self,a_agent:AAgent,destination:str) -> None:
        self.a_agent=a_agent
        self.destination=destination

    async def run(self):
        try:
            await self.a_agent.send_message("action","teleport_to," + self.destination)
        except asyncio.CancelledError:
            print("***** TASK Teleport_To CANCELLED")
            await self.a_agent.send_message("action", "stop")


"""
WIP
Walks to a given destination using the navMesh
"""
class Walk_To:

    VALID_LOCATIONS=["BaseAlpha","BaseBeta","BaseGamma","BaseDelta"]

    def __init__(self,a_agent:AAgent,destination:str) -> None:
        self.a_agent=a_agent
        self.destination=destination

    async def run(self):
        try:
            await self.a_agent.send_message("action","stop") #Just in case
            while True:
                await self.a_agent.send_message("action","walk_to," + self.destination)
                if self.a_agent.i_state.currentNamedLoc == self.destination:
                    await self.a_agent.send_message("action","stop") #Just in case
                    return True
        except asyncio.CancelledError:
            print("***** TASK Walk_To CANCELLED")
            await self.a_agent.send_message("action", "stop")


"""
TO BE TESTED
Sends leave,AlienFlower command adding in the desired amount
"""
class Drop_Off_Flowers:

    def __init__(self,a_agent: AAgent,amount:int) -> None:
        self.a_agent=a_agent
        self.amount_to_drop =amount
        self.initial_amount=0

        inventory=self.a_agent.i_state.myInventoryList
        for _, value in enumerate(inventory):
            if value["name"] != "AlienFlower":
                continue

            self.initial_amount =value["amount"]
            break
    async def run(self):
        try:
            while True:
                if self.a_agent.i_state.nearbyContainerInventory:
                    await self.a_agent.send_message("action","leave,AlienFlower," + str(self.amount_to_drop))
                inventory=self.a_agent.i_state.myInventoryList
                for _, value in enumerate(inventory):
                    if value["name"] != "AlienFlower":
                        continue

                    if value["amount"] <= self.initial_amount - self.amount_to_drop or value["amount"] == 0:
                        return True

        except asyncio.CancelledError:
            print("***** TASK Drop_Off_Flowers CANCELLED")
            await self.a_agent.send_message("action", "stop")
        