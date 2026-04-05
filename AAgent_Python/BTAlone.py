import asyncio
import random
from typing import Literal
import py_trees
import py_trees as pt
from py_trees import common
import Goals_BT_Basic
import Sensors


"""IMPASSABLE_OBJECT_TAGS   : list[str] -- A list containing all impassable object tags that the agent should avoid."""
IMPASSABLE_OBJECT_TAGS = ["Wall","Rock","Machine"]

"""NUM_RAYS_PER_SIDE        : int       -- The number of sensor rays defined per side in the json. This is used to get the front facing ray. Is equivalent to front ray index"""
NUM_RAYS_PER_SIDE = 2 #Ideally this should be read from somewhere


def common_goal_update(goal) -> pt.common.Status:
    """
    Common update for goal based BN.

    Author -- Us

    Returns:
    FAILURE if goal is None
    RUNNING if goal is not done
    SUCCESS if goal result is True
    Else FAILURE
    """
    if goal == None:
            return pt.common.Status.FAILURE
        
    if not goal.done():
        return pt.common.Status.RUNNING

    res = goal.result()
    if res:
        return pt.common.Status.SUCCESS

    return pt.common.Status.FAILURE

###### Do Nothing BN #####

class BN_DoNothing(pt.behaviour.Behaviour):
    """
    Goal based BN, does nothing, just waits a set amount of time.

    Author -- Professor
    """
    def __init__(self, aagent):
        self.my_agent = aagent
        self.my_goal = None
        # print("Initializing BN_DoNothing")
        super(BN_DoNothing, self).__init__("BN_DoNothing")

    def initialise(self):
        self.my_goal = asyncio.create_task(Goals_BT_Basic.DoNothing(self.my_agent).run())

    def update(self):
        return common_goal_update(self.my_goal)
    
    def terminate(self, new_status: common.Status):
        # Finishing the behaviour, therefore we have to stop the associated task
        print("Terminate DoNothing")
        if self.my_goal!=None:
            self.my_goal.cancel()
#### Return To Base BNs #####

class BN_IsInBaseNearContainer(pt.behaviour.Behaviour):
    """
    Checks if the agent is in a valid base and near a container 
    if so SUCCESS
    if not FAILURE.

    Author -- Us

    Attributes:
    VALID_BASES : list[str]         -- Exhaustive list of valid bases.
    my_agent    : AAgent_BT.AAgent  -- Agent to check.
    
    Methods:
    Standard behaviour methods.
    """

    VALID_BASES=["BaseAlpha","BaseBeta","BaseGamma","BaseDelta"]

    def __init__(self, aagent):
        self.my_goal=None
        super(BN_IsInBaseNearContainer, self).__init__("BN_IsInBaseNearContainer")
        self.my_agent=aagent

    def initialise(self) -> None:
        pass

    def update(self) -> common.Status:
        if (self.my_agent.i_state.currentNamedLoc in self.VALID_BASES
            and self.my_agent.i_state.nearbyContainerInventory):
            return pt.common.Status.SUCCESS
    
        return pt.common.Status.FAILURE
    
    def terminate(self, new_status: common.Status) -> None:
        pass

class BN_ReturnToBase(pt.behaviour.Behaviour):
    """
    Goal based BN, returns to base via navMesh.
    SUCCESS on reaching destination.
    RUNNING while on the way to destination.

    
    NOTE: Currently only walks to the Alpha base, later on we can make it walk to the nearest base.

    Author -- Us

    Methods:
    Standard behaviour methods.
    """
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_ReturnToBase, self).__init__("BN_ReturnToBase")
        self.my_agent = aagent
        self.debug_current_state=None

    def initialise(self) -> None:
        print("BN_ReturnToBase Intialising")
        self.my_goal= asyncio.create_task(Goals_BT_Basic.Walk_To(self.my_agent,"BaseAlpha").run())

    def update(self) -> pt.common.Status:
        #TODO remove temp
        temp= common_goal_update(self.my_goal)
        if temp!= self.debug_current_state:
            self.debug_current_state=temp
            print("Return To Base:",temp)
        return temp
    
    def terminate(self, new_status: common.Status) -> None:
        print("Terminate ReturnToBase:",new_status)
        if self.my_goal != None:
            self.my_goal.cancel()

##### Store Flowers BNs #####


class BN_CheckInventory(pt.behaviour.Behaviour):
    """
    Checks if the inventory has the required amount of flowers, if so SUCCESS, else FAILURE
    
    Author -- Us

    Methods:
    Standard behaviour methods
    """
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_CheckInventory, self).__init__("BN_MoveForward")
        self.my_agent = aagent
        # At what amount of flowers should the agent return to base
        self.return_threshold=2

    def initialize(self):
        pass

    def update(self) -> pt.common.Status:
        inventory=self.my_agent.i_state.myInventoryList

        for _, value in enumerate(inventory):
            if value["name"] != "AlienFlower":
                continue

            if value["amount"] >= self.return_threshold:
                return pt.common.Status.SUCCESS
            
            #There should only be 1 AlienFlower "slot", no need to iterate over the whole inventory
            break
        
        #The agent doesn't have more than self.return_threshold Flowers
        return pt.common.Status.FAILURE
    
    def terminate(self, new_status: common.Status) -> None:
        pass

class BN_DropOffFlowers(pt.behaviour.Behaviour):
    """
    Uses a goal to drop off the flowers onto a nearby container
    SUCCESS if it drops off the flowers
    FAILURE if MAX_ATTEMPTS is exeded without SUCCESS
    Else RUNNING

    Author -- Us

    Methods:
    Standard behaviour methods.
    """
    def __init__(self, aagent):
        self.my_goal=None
        super(BN_DropOffFlowers,self).__init__("BN_DropOffFlowers")
        self.my_agent=aagent
        self.debug_current_state=None 

    def initialise(self) -> None:
        print("BN_DropOffFlowers initialise")
        self.my_goal=asyncio.create_task(Goals_BT_Basic.Drop_Off_Flowers(self.my_agent,2).run())

    def update(self) -> common.Status:
        #TODO remove temp
        temp= common_goal_update(self.my_goal)
        if temp!= self.debug_current_state:
            self.debug_current_state=temp
            print("Drop Off Flowers:",temp)
        return temp

    def terminate(self, new_status: common.Status) -> None:
        print("Terminate DropOffFlowers")
        if self.my_goal!=None:
            self.my_goal.cancel()
    
        


###### Flower Protocol BNs #####

class BN_DetectFlower(pt.behaviour.Behaviour):
    """
    Checks if any ray detects an 'AlienFlower' object
    SUCCESS if so
    FAILURE if not

    Author -- Professor 

    Methods:
    Standard behaviour methods
    """
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_DetectFlower, self).__init__("BN_DetectFlower")
        self.my_agent = aagent

    def initialise(self):
        #print("Intialising BN_DetectFlower")
        pass

    def update(self):
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for index, value in enumerate(sensor_obj_info):
            if value:  # there is a hit with an object
                if value["tag"] == "AlienFlower":  # If it is a flower
                    # print("Flower detected!")

                    return pt.common.Status.SUCCESS
        # print("No flower...")
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status):
        pass

class BN_MoveToFlower(pt.behaviour.Behaviour):
    """
    Goal based BN.
    Turns towards a flower and then moves forward until it hits something.
    Selects a flower from left to right on intialise.


    Author -- Us

    Attributes:
    TURN_DEGREES    : float -- The degrees between each ray, this way if you detect it on the first ray form the left the agent will turn TURN 2 TURN_DEGREES
    
    Methods:
    Standard behaviour methods.
    
    """

    TURN_DEGREES = 11.25 # Ideally should be the degrees between each ray

    def __init__(self, aagent):

        self.my_goal = None
        super(BN_MoveToFlower, self).__init__("BN_MoveToFlower")
        self.my_agent = aagent
        self.debug_current_state=None #DEBUGING var

    def initialise(self):
        print("BN_MoveToFlower Intializing")
        #We'll first store where the flowers are relative to the agent so that we can later prioritize ones over others to avoid constant target switching
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        rays_with_flowers=[]
        distance_to_forward_flower=0.0

        for index, value in enumerate(sensor_obj_info):
            if value:  # there is a hit with an object
                if value["tag"] != "AlienFlower":  # If it is a flower
                    continue

                if index == 2: 
                    # We only need to know the distance if we'll move forward
                    distance_to_forward_flower=value["distance"]

                rays_with_flowers.append(index)


        #Flower's straight ahead
        if 2 in rays_with_flowers: #We prioritize moving forward if there is a flower straight ahead, else turn to the first flower from left to right.
            #print("Flower forward")
            self.my_goal = asyncio.create_task(Goals_BT_Basic.ForwardDist(self.my_agent,distance_to_forward_flower,0,5).run())
        else:
            #print("Flower to the sides")
            self.my_goal = asyncio.create_task(Goals_BT_Basic.Turn_customizable(self.my_agent,0,(rays_with_flowers[0]-2)*self.TURN_DEGREES).run())

    def update(self):
        #TODO remove temp
        temp= common_goal_update(self.my_goal)
        if temp!= self.debug_current_state:
            self.debug_current_state=temp
            print("Move To Flower:",temp)
        return temp


    def terminate(self, new_status: common.Status):
        print("Terminate BN_MoveToFlower STATUS:",new_status)
        self.logger.debug("Terminate BN_MoveToFlower")
        if self.my_goal!= None:
            self.my_goal.cancel()
        
"""
tags to take into acount when improving roaming(CASE SENSITIVE!):
    Wall (map edge)
    Rock

    (These are objects on each base)
    Location    (floor of each base)
    Container   (hitbox of where we store flowers)
    Machine     (the visible "thing" that represents the container)

"""
###### Improved Roaming Attempt ########

class BN_IsForwardBlocked(pt.behaviour.Behaviour):
    """
    This simple BN checks if continuing forward is feasible or if there is an impassable object in front
    FAILURE if it is NOT an impassable object within MIN_SAFE_DISTANCE(or not detecting anything)
    SUCCESS if the front ray is detecting an impassable object within MIN_SAFE_DISTANCE

    I know the name is a bit confusing since resurning SUCCESS means it is SUCCESSFULLY blocked, but it is done like this to make the BT work properlly and not stutter

    Author -- Us
    
    Attributes:
    MIN_SAFE_DISTANCE : float -- Distance at which an impassable object is considered to be blocking the agent.

    Methods:
    Standard behaviour methods
    """
    MIN_SAFE_DISTANCE = 2.0
    def __init__(self,aagent):
        self.my_goal=None
        super(BN_IsForwardBlocked,self).__init__("BN_IsForwardBlocked")
        self.my_agent = aagent

    def initialise(self) -> None:
        pass

    def update(self) -> pt.common.Status:
        #This might not seem intuitive but it gets the middle ray always. This is because if there are X number of rays per side the forward facing one is X+1, but since we start counting at 0 it's X
        front_ray_sensor = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO][NUM_RAYS_PER_SIDE] 
        
        if front_ray_sensor:  # there is a hit with an object
            if front_ray_sensor["tag"] in IMPASSABLE_OBJECT_TAGS:
                if front_ray_sensor["distance"] < self.MIN_SAFE_DISTANCE:  
                    return pt.common.Status.SUCCESS
            
        return pt.common.Status.FAILURE

    def terminate(self, new_status: common.Status) -> None:
        pass




class BN_SmartTurning(pt.behaviour.Behaviour):
    """
    Goal based BN,
    Moves turns a random amount from 0 degrees to MAX_DEGREES_TO_TURN (56.25), randomly choosing between left and right.
    If it detects an impassable object is too close it won't turn towards it.
    If all rays detect an object too close it will do a random turn from -EMERGENCY_TURN_DEGREES (-180) to EMERGENCY_TURN_DEGREES (180) degrees
    
    SUCCESS if new heading is achieved (with a margin of error)
    RUNNING while turning

    Author -- Us, inspired by the professors TurnRandom

    Attributes:
    MIN_DISTANCE_THRESHOLD  : float -- At what distance should the agent avoid turing towards that, this mainly helps if the rays become long or when there are thight corridors.
    MAX_DEGREES_TO_TURN     : float  
        When moving normally how much should it be able to turn. If all are blocked it will still turn form 0 to 180.
        Numbers that are very much larger than the degrees that the rays span might cause issues, unsure.
        Numbers below the degrees that the rays span probably won't work, unsure.
    EMERGENCY_TURN_DEGREES  : float -- What many degrees can it potentially turn in case of all rays being blocked.
        
    Methods:
    Standard behaviour methods
    """
    MIN_DISTANCE_THRESHOLD = 2.0
    MAX_DEGREES_TO_TURN = 56.25
    EMERGENCY_TURN_DEGREES = 180

    def __init__(self, aagent):
        self.my_goal = None
        super(BN_SmartTurning, self).__init__("BN_SmartTurning")
        self.my_agent = aagent

    def initialise(self) -> None:
        sensor_information = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        possible_rotation_values=[]

        #How many degrees of the turn each rays "controls", imagine the ray in the middle of a cone that is 2*"degrees_per_ray" degrees (2* because its that many degrees either side of the ray)
        degrees_per_ray = self.MAX_DEGREES_TO_TURN/((NUM_RAYS_PER_SIDE*2)+1) # 2* because there are 2 sides, + 1 because there is one in the middle

        for index, value in enumerate(sensor_information):
            # it is an impassable object
            if (not value # is null, which means there is no hit 
                or  (value["distance"] >= self.MIN_DISTANCE_THRESHOLD 
                or value["tag"] not in IMPASSABLE_OBJECT_TAGS)):  # if object is not impassable or it is not close
                
                #Store that ray's "controlled area" as a possible value for turning
                possible_rotation_values.append(random.uniform(degrees_per_ray*(index-NUM_RAYS_PER_SIDE)-degrees_per_ray, degrees_per_ray*(index-NUM_RAYS_PER_SIDE)+degrees_per_ray))
            
        if not possible_rotation_values: # all rays are blocked
            self.my_goal = asyncio.create_task(Goals_BT_Basic.Turn_customizable(self.my_agent,0,random.uniform(-self.EMERGENCY_TURN_DEGREES,self.EMERGENCY_TURN_DEGREES)).run())
            return      
        
        #Some rays are not blocked and we'll randomly choose one of them, and follow it's random value for movement.
        self.my_goal = asyncio.create_task(Goals_BT_Basic.Turn_customizable(self.my_agent,0,random.choice(possible_rotation_values)).run())

    def update(self):
       return common_goal_update(self.my_goal)

    def terminate(self, new_status: common.Status):
        # Finishing the behaviour, therefore we have to stop the associated task
        #print("Terminate BN_TurnRandom")
        self.logger.debug("Terminate BN_TurnRandom")
        if self.my_goal!=None:
            self.my_goal.cancel()



###### Roaming BNs Don't Touch Much #######

class BN_ForwardRandom(pt.behaviour.Behaviour):
    """
    Goal based BN,
    Moves Forward a random amount from 1 to 5.
    
    SUCCESS if length is reached or passed
    FAILURE if stuck in place
    RUNNING while moving

    Author -- Professor
    NOTE: We've changed update from hardcoded to referencing the common_goal_update function but the behaviour is the same.

    Methods:
    Standard behaviour methods
    """
    def __init__(self, aagent):
        self.my_goal = None
        #print("Initializing BN_ForwardRandom")
        super(BN_ForwardRandom, self).__init__("BN_ForwardRandom")
        self.logger.debug("Initializing BN_ForwardRandom")
        self.my_agent = aagent

    def initialise(self):
        print("BN_ForwardRandom Initialize")
        self.logger.debug("Create Goals_BT.ForwardDist task")
        self.my_goal = asyncio.create_task(Goals_BT_Basic.ForwardDist(self.my_agent, -1, 1, 5).run())

    def update(self):
        return common_goal_update(self.my_goal)
    
    def terminate(self, new_status: common.Status):
        # Finishing the behaviour, therefore we have to stop the associated task
        #print("Terminate BN_ForwardRandom")
        self.logger.debug("Terminate BN_ForwardRandom")
        if self.my_goal != None:
            self.my_goal.cancel()


class BN_TurnRandom(pt.behaviour.Behaviour):
    """
    Goal based BN,
    Moves turns a random amount from 0 degrees to 180, randomly choosing between left and right.
    
    SUCCESS if new heading is achieved (with a margin of error)
    RUNNING while turning

    Author -- Professor
    NOTE: We've changed update from hardcoded to referencing the common_goal_update function but the behaviour is the same.

    Methods:
    Standard behaviour methods
    """
    def __init__(self, aagent):
        self.my_goal = None
        #print("Initializing BN_TurnRandom")
        super(BN_TurnRandom, self).__init__("BN_TurnRandom")
        self.my_agent = aagent

    def initialise(self):
        print("BN_TurnRandom Intialize")
        self.my_goal = asyncio.create_task(Goals_BT_Basic.Turn_customizable(self.my_agent,random.choice([-1,1]),random.uniform(0,180)).run())

    def update(self):
       return common_goal_update(self.my_goal)

    def terminate(self, new_status: common.Status):
        # Finishing the behaviour, therefore we have to stop the associated task
        #print("Terminate BN_TurnRandom")
        self.logger.debug("Terminate BN_TurnRandom")
        if self.my_goal!=None:
            self.my_goal.cancel()



###### Detect Frozen BN Don't Touch Much #######

class BN_DetectFrozen(pt.behaviour.Behaviour):  
    """
    Detects if the internal state of the agent 'isFrozen' is set to True.
    SUCCESS if it is frozen
    else FAILURE

    Author -- Professor

    Methods: 
    Standard behaviour methods.
    """
    def __init__(self, aagent):      
        self.my_goal = None      
          #print("Initializing BN_DetectInventoryFull")      
        super(BN_DetectFrozen, self).__init__("BN_DetectFrozen")
        self.my_agent = aagent
        self.i_state = aagent.i_state
    def initialise(self):
        pass 

    def update(self):   
        if self.i_state.isFrozen: 
            return pt.common.Status.SUCCESS
        return pt.common.Status.FAILURE
    def terminate(self, new_status: common.Status):
        pass


class BTAlone:
    """
    
    FIXME: Tree outdated
    Tree Structure:
    
                           Root (Selector)
                          /            \
                      Frozen          false_root(Selector)-----------------------------|
                   (Sequence)           /        |                                      \
                    /      \\          /         |------------------|                    \
                   /        \\        /                             |                     \
            DetectFrozen  DoNothing  /                              |                      \
                               ReturnToBase                   FlowerProtocol          Roaming(Parallel)
                               (Sequence)---|                  (Sequence)               /          \
                              /    |         \\                  /      \\             /            \
                             /     |          \\                /        \\           /              \
                    CheckInv  ReturnToBase DropFlowers DetectFlower MoveToFlower   ForwardRandom TurnRandom
                                                       
    
    Selector: Returns SUCCESS when first child succeeds
    Sequence: Returns SUCCESS only when all children succeed in order
    Parallel: Returns SUCCESS when all children succeed (SuccessOnAll policy)

    NOTE: ASCII tree 'drawn' with AI + some (IMPORTANT) human modificaitons
    """

    def __init__(self, aagent):
        # py_trees.logging.level = py_trees.logging.Level.DEBUG

        self.aagent = aagent      

        frozen=  pt.composites.Sequence(name="DetectFrozen", memory=True)
        frozen.add_children([BN_DetectFrozen(aagent), BN_DoNothing(aagent)])

        
        # Detect the flower, once detected turn towards it, once facing it move forward
        flower_protocol = pt.composites.Sequence(name="MoveToFlower", memory=True)
        flower_protocol.add_children([
                                        BN_DetectFlower(aagent),
                                        BN_MoveToFlower(aagent),
                                        ]) 
        
        #checks if it's in a base, if not returns to base
        return_to_base=pt.composites.Selector(name="ReturnToBase",memory=False)
        return_to_base.add_children([
                                        BN_IsInBaseNearContainer(aagent),
                                        BN_ReturnToBase(aagent)
        ])

        #Check inventory when 2 return to base, then drop off flowers
        store_flowers= pt.composites.Sequence(name="StoreFlowers",memory=False) 
        store_flowers.add_children([
                                        BN_CheckInventory(aagent),
                                        return_to_base,
                                        BN_DropOffFlowers(aagent),
                                     ])
        

        smart_forward = pt.composites.Selector("SmartForward",memory=False)
        smart_forward.add_children([
                                    BN_IsForwardBlocked(aagent),
                                    BN_ForwardRandom(aagent)
                                 ])

        smart_roaming =pt.composites.Parallel(name="SmartRoaming", policy=py_trees.common.ParallelPolicy.SuccessOnAll())
        smart_roaming.add_children([
                                    smart_forward,
                                    BN_SmartTurning(aagent)
        ])

        random_roaming = pt.composites.Parallel(name="Parallel", policy=py_trees.common.ParallelPolicy.SuccessOnAll())
        random_roaming.add_children([
                                BN_ForwardRandom(aagent), 
                                BN_TurnRandom(aagent)
                              ])

        false_root = pt.composites.Selector(name="Selector", memory=False)
        false_root.add_children([
                                    store_flowers,
                                    flower_protocol,
                                    smart_roaming
                                    ])
        
        
        

        self.root = pt.composites.Selector(name="Selector", memory=False)
        self.root.add_children([frozen, false_root])


        self.behaviour_tree = pt.trees.BehaviourTree(self.root)

    def stop_behaviour_tree(self):
        print("Stopping the BehaviorTree")
        self.root.tick_once()

        for node in self.root.iterate():
            if node.status != pt.common.Status.INVALID:
                node.status = pt.common.Status.INVALID
                # For nodes that weren't RUNNING, manually call terminate
                if hasattr(node, "terminate"):
                    node.terminate(pt.common.Status.INVALID)

    async def tick(self):
        self.behaviour_tree.tick()
        await asyncio.sleep(0)
