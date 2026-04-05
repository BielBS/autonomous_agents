import asyncio
import random
from typing import Literal
import py_trees
import py_trees as pt
from py_trees import common
import Goals_BT_Basic
import Sensors


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
       #print("BN_ForwardRandom Initialize")
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
       #print("BN_TurnRandom Intialize")
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
        store_flowers= pt.composites.Sequence(name="storeFlowers",memory=False) 
        store_flowers.add_children([
                                        BN_CheckInventory(aagent),
                                        return_to_base,
                                        BN_DropOffFlowers(aagent),
                                     ])
        

        #TODO, idk if neccesary, improve roaming
        roaming = pt.composites.Parallel(name="Parallel", policy=py_trees.common.ParallelPolicy.SuccessOnAll())
        roaming.add_children([
                                BN_ForwardRandom(aagent), 
                                BN_TurnRandom(aagent)
                              ])

        false_root = pt.composites.Selector(name="Selector", memory=False)
        false_root.add_children([
                                    store_flowers,
                                    flower_protocol,
                                    roaming
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
