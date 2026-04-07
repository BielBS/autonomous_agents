import asyncio
import py_trees as pt
from py_trees import common
import Goals_BT_Basic
import Sensors
import BNs_SmartRoam 
from Utils import common_goal_update
from Utils import get_inventory_amount

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


class BN_DetectFrozen(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        self.my_goal = None
        # print("Initializing BN_DetectInventoryFull")
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
    Goal based BN, returns to the nearest base as the crow flies via navMesh.
    SUCCESS on reaching destination.
    RUNNING while on the way to destination.
    
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
        #Fallback go to BaseAlpha
        chosen_base= "BaseAlpha"
        if self.my_agent.i_state.position["z"] > 0.0:
            if self.my_agent.i_state.position["x"] > 0.0:
                chosen_base="BaseDelta"
            if self.my_agent.i_state.position["x"] < 0.0:
                chosen_base="BaseGamma"
        
        
        if self.my_agent.i_state.position["z"] < 0.0:
            if self.my_agent.i_state.position["x"] > 0.0:
                chosen_base="BaseAlpha"
            if self.my_agent.i_state.position["x"] < 0.0:
                chosen_base="BaseBeta"
                #Yes, we could remove this check and everything would work but I'll leave it here for ease of understanding

        self.my_goal= asyncio.create_task(Goals_BT_Basic.Walk_To(self.my_agent,chosen_base).run())

    def update(self) -> pt.common.Status:
        goal_status= common_goal_update(self.my_goal)
        #if goal_status!= self.debug_current_state:
        #    self.debug_current_state=goal_status
        #    print("Return To Base:",goal_status)
        return goal_status
    
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
        if get_inventory_amount(self.my_agent.i_state.myInventoryList) >= self.return_threshold:
            return pt.common.Status.SUCCESS
        
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
        goal_status= common_goal_update(self.my_goal)
        #if goal_status!= self.debug_current_state:
        #    self.debug_current_state=goal_status
        #    print("Drop Off Flowers:",goal_status)
        return goal_status

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

    def __init__(self, aagent):

        self.my_goal = None
        super(BN_MoveToFlower, self).__init__("BN_MoveToFlower")
        self.my_agent = aagent
        self.debug_current_state=None #DEBUGING var

    def initialise(self):
        print("BN_MoveToFlower Intializing")
        #We'll first store where the flowers are relative to the agent so that we can later prioritize ones over others to avoid constant target switching
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        sensor_angles = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.ANGLE]
        rays_with_flowers=[]
        distance_to_forward_flower=0.0
        central_ray_index = self.my_agent.rc_sensor.central_ray_index

        for index, value in enumerate(sensor_obj_info):
            if value:  # there is a hit with an object
                if value["tag"] != "AlienFlower":  # If it is a flower
                    continue

                if index == central_ray_index:
                    # We only need to know the distance if we'll move forward
                    distance_to_forward_flower=value["distance"]

                rays_with_flowers.append(index)


        #Flower's straight ahead
        if central_ray_index in rays_with_flowers: #We prioritize moving forward if there is a flower straight ahead, else turn to the first flower from left to right.
            #print("Flower forward")
            self.my_goal = asyncio.create_task(Goals_BT_Basic.ForwardDist(self.my_agent,distance_to_forward_flower,0,5).run())
        elif rays_with_flowers:
            #print("Flower to the sides")
            self.my_goal = asyncio.create_task(
                Goals_BT_Basic.Turn_customizable(self.my_agent, 0, sensor_angles[rays_with_flowers[0]]).run()
            )

    def update(self):
        goal_status= common_goal_update(self.my_goal)
        #if goal_status!= self.debug_current_state:
        #    self.debug_current_state=goal_status
        #    print("Move To Flower:",goal_status)
        return goal_status


    def terminate(self, new_status: common.Status):
        print("Terminate BN_MoveToFlower STATUS:",new_status)
        self.logger.debug("Terminate BN_MoveToFlower")
        if self.my_goal!= None:
            self.my_goal.cancel()
        

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

        frozen = pt.composites.Sequence(name="Sequence_frozen", memory=True)
        frozen.add_children([
            BN_DetectFrozen(aagent),
            BN_DoNothing(aagent),
        ])

        
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
        store_flowers= pt.composites.Sequence(name="StoreFlowers",memory=True) 
        store_flowers.add_children([
                                        BN_CheckInventory(aagent),
                                        return_to_base,
                                        BN_DropOffFlowers(aagent),
                                     ])
        

        smart_roaming = BNs_SmartRoam.create_roaming_subtree(
            aagent,
            name="SmartRoaming",
            avoid_side_walls=True,
            side_wall_distance=2.0,
            center_bias_weight=1.1,
        )

        false_root = pt.composites.Selector(name="Selector", memory=False)
        false_root.add_children([
                                    store_flowers,
                                    flower_protocol,
                                    smart_roaming
                                    ])

        self.root = pt.composites.Selector(name="Selector_root", memory=False)
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
