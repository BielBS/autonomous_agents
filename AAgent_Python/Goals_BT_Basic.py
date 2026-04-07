import math
import random
import asyncio
import Sensors
from typing import TYPE_CHECKING
from Utils import get_inventory_amount

if TYPE_CHECKING:
    from AAgent_BT import AAgent

def calculate_distance(point_a, point_b):
    """
    Calculates the euclidean distance between 2 points

    Author -- Professor
    """
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

        Author -- Professor
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

        Author -- Professor
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
            if self.a_agent.i_state.movingForwards: 
                #This is an atempt to fix the stuttering bug, it seems to work but it created a smaller
                # BUG: Everytime the agent would stutter to collect a flower it now stops, thinks for a second and then colects it
                #       This is because we avoid 1 NTM but not both.
                # The original bug is still present in some form or another since MoveToFLower still becomes INVALID when it shouldn't
                await self.a_agent.send_message("action", "ntm")
            else:
                print("NTM avoided.")
            self.state = self.STOPPED


class BackwardDist:
    """
        Moves backward a certain distance specified in the parameter "dist".
        If "dist" is -1, selects a random distance between the initial
        parameters of the class "d_min" and "d_max"
    """
    STOPPED = 0
    MOVING = 1

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
            previous_dist = 0.0
            while True:
                if self.state == self.STOPPED:
                    self.starting_pos = self.a_agent.i_state.position
                    if self.original_dist < 0:
                        self.target_dist = random.uniform(self.d_min, self.d_max)
                    else:
                        self.target_dist = self.original_dist
                    await self.a_agent.send_message("action", "mb")
                    self.state = self.MOVING
                elif self.state == self.MOVING:
                    await asyncio.sleep(0.25)
                    current_dist = calculate_distance(self.starting_pos, self.i_state.position)
                    if current_dist >= self.target_dist:
                        await self.a_agent.send_message("action", "ntm")
                        self.state = self.STOPPED
                        return True
                    elif previous_dist == current_dist:
                        await self.a_agent.send_message("action", "ntm")
                        self.state = self.STOPPED
                        return False
                    previous_dist = current_dist
                else:
                    print("Unknown state: " + str(self.state))
                    return False
        except asyncio.CancelledError:
            print("***** TASK Backward CANCELLED")
            if self.a_agent.i_state.movingBackwards:
                await self.a_agent.send_message("action", "ntm")
            self.state = self.STOPPED


########## New Goals from here downward #########

class Turn_customizable:
    """
    The action of turning a given set of degrees in a given direction (right or left)
    
    Possible BUG:Sometimes it keeps truning over and over, probably because it skips over the desired heading and does another full turn
        Added TURN_THRESHOLD instead of magic number and changed it from 5 to 10, in an attempt to fix it [03/04/26] --> Appears to work so far [04/04/26]
    
    Author -- Mainly our professor but with some modifications so that the turn can be specified.    
        
    Attributes:
    LEFT            : int -- Left identifyer
    RIGHT           : int -- Right identifyer
    DEDUCE_IT       : int -- Identifyer representing that the direction should be deduced by the degrees (if they're positive or negative)
    VALID_DIRECTIONS: int -- List of valid directiosn
    SELECTING       : int -- Selecting status identifyer
    TURNING         : int -- Turning status identifyer
    TURN_THRESHOLD  : int 
        How close do we need to be to the desired heading to consider it a SUCCESS.
        NOTE: It's in degrees, low values may cause the agent to spin repeatedly on itself since it skipped over the desired heading.

    Methods: 
    __init__  -- Initialization. Raises assertion error if direction isn't in VALID_DIRECTIONS.
    async run -- Inside a while loop first selects new heading based on given attributes then constantly turns until it is within TURNING_THRESHOLD of the desired heading.
        
    """
    LEFT = -1
    RIGHT = 1
    DEDUCE_IT = 0

    VALID_DIRECTIONS=[LEFT,RIGHT,DEDUCE_IT]

    SELECTING = 0
    TURNING = 1

    TURN_THRESHOLD=10


    def __init__(self, a_agent,direction:int,degrees:float):
        self.a_agent = a_agent
        self.rc_sensor = a_agent.rc_sensor
        self.i_state = a_agent.i_state

        self.current_heading = 0
        self.new_heading = 0

        self.state = self.SELECTING

        assert direction in self.VALID_DIRECTIONS

        self.direction=direction
        self.degrees=degrees

    async def run(self):
        try:
            while True:
                if self.state == self.SELECTING:
                    # print("SELECTING NEW TURN")

                    if self.direction == self.DEDUCE_IT:
                        rotation_direction = -1 if self.degrees<0 else 1
                        rotation_degrees=self.degrees
                    else:
                        rotation_direction = self.direction
                        rotation_degrees = self.degrees * rotation_direction
    
                    # print(f"Rotation direction: {rotation_direction}")
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
                    final_condition = abs((current_heading - self.new_heading + 180) % 360 - 180)
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

class Turn(Turn_customizable):
    """
    Backwards-compatible version of the example Turn goal.
    """
    def __init__(self, a_agent):
        super().__init__(a_agent, random.choice([-1, 1]), random.uniform(0, 180))


class Teleport_To:
    """
    UNTESTED
    Teleports to a given destination

    On cancel stops all actions.
    
    Author -- Us

    Attributes:
      a_agent       : AAgent_BT.AAgent
        The agent to teleport.
     destination    : str
        The keyword name of the destination, if an invalid name is set nothing will happen.

    Methods:
    __init__  -- intitialization
    asnyc run -- inside a while loop sends the action to teleport, stops all actions if canceled 
    """

    def __init__(self, a_agent: "AAgent", destination: str) -> None:
        self.a_agent=a_agent
        self.destination=destination

    async def run(self):
        try:
            await self.a_agent.send_message("action","teleport_to," + self.destination)
            return True
        except asyncio.CancelledError:
            print("***** TASK Teleport_To CANCELLED")
            await self.a_agent.send_message("action", "stop")



class Walk_To:
    """
    Walks to a given destination using the navMesh

    BUG: When it finally returns to base the agent doesn't seem to stop, if you move it manually it will continue to walk_to base, sometimes
    
    Author -- Us

    Attributes:
    a_agent         : AAgent_BT.AAgent
        The agent to move.
    destination     : str
        The keyword name of the destination, if an invalid name is set nothing will happen.
    VALID_LOCATIONS : list[str]
        A non-exhaustive list of valid locations. 
        Currently only ontains base names.
        Currently unused.

    Methods:
    __init__  -- intialization
    async run -- stops current actions (just in case), then in a while loop awaits the 'walk_to action'
    """

    VALID_LOCATIONS=["BaseAlpha","BaseBeta","BaseGamma","BaseDelta"]

    def __init__(self, a_agent: "AAgent", destination: str) -> None:
        self.a_agent=a_agent
        self.destination=destination

    async def run(self):
        """
        Moves using NavMesh to the given location.
        
        Stops current actions (just in case)
        Then in a while loop awaits the 'walk_to action', if succesfull stops current actions.
        
        On cancel stops current actions.

        Returns:
        True -- if the destination was reached
        None -- in any other case
        """
        try:
            while True:
                #print("On Route: ",self.a_agent.i_state.onRoute)
                if not self.a_agent.i_state.onRoute:
                    await self.a_agent.send_message("action",f"walk_to,{self.destination}")
                
                await asyncio.sleep(0.1) 
                
                if (self.a_agent.i_state.currentNamedLoc == self.destination
                    and (not self.destination.startswith("Base")
                         or self.a_agent.i_state.nearbyContainerInventory)):
                    #await self.a_agent.send_message("action","stop") #Just in case
                    return True
                
                #await asyncio.sleep(0)
                
        except asyncio.CancelledError:
            print("***** TASK Walk_To CANCELLED")
            await self.a_agent.send_message("action", "stop")



class Drop_Off_Flowers:
    """
    Sends 'leave,AlienFlower,x' command where x is the desired amount set at init.

    Author -- Us

    Attributes:
    MAX_ATTEMPTS    : int
        Maximum number of attempts to send the action before concluding it's a failure 
    a_agent         : AAgent_BT.AAgent
        The agent meant to perform the action.
    amount          : int
        The amount to drop off.
    intial_amount : int
        The amount of flowers the agent has upon creating the class

        
    Methods:
    __init__ -- intialization, recieves AAgent and amount to drop off.
    async run -- awaits 'leave action' inside a while loop.
    """
    MAX_ATTEMPTS= 5

    def __init__(self, a_agent: "AAgent", amount: int) -> None:
        self.a_agent=a_agent
        self.amount_to_drop =amount
        self.initial_amount = get_inventory_amount(self.a_agent.i_state.myInventoryList)
        print("Initial ammount:",self.initial_amount)

    async def run(self):
        try:
            #await self.a_agent.send_message("action","ntm") # maybe this fixes the dropOff bug, no it does not
            for _ in range(self.MAX_ATTEMPTS):
                if getattr(self.a_agent.i_state, 'nearbyContainerInventory', False):
                    #print("Sending leave command...")
                    await self.a_agent.send_message("action","leave,AlienFlower,"+ str(self.amount_to_drop))
                    await asyncio.sleep(2)
                    #print(f"Inventory after send: {self.a_agent.i_state.myInventoryList}")

                    current_amount = get_inventory_amount(self.a_agent.i_state.myInventoryList)
                    if current_amount <= max(0, self.initial_amount - self.amount_to_drop):
                        print("Drop off successful!")
                        return True
                    #print("Drop off not successful, retrying...")
            #print("Drop off not successful, Max attempts reached, giving up.")
            return False
        
        except asyncio.CancelledError:
            print("***** TASK Drop_Off_Flowers CANCELLED")
            await self.a_agent.send_message("action", "stop")
        
