import asyncio
import random
from typing import Literal
import py_trees
import py_trees as pt
from py_trees import common
import Goals_BT_Basic
import Sensors

"""
Common update for goal based BN.

Returns FAILURE if goal is None
Returns RUNNING if goal is not done
Returns SUCCESS if goal result is True

Else returns FAILURE
"""
def common_goal_update(goal) -> pt.common.Status:
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


##### Return To Base BNs #####

"""
Checks if the inventory has the required amount of flowers, if so returns SUCCESS, else returns FAILURE
"""
class BN_CheckInventory(pt.behaviour.Behaviour):
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
"""
To Test
Returns to base via Walk_to navMesh action.
Currently only walks to the Alpha base, later on we can make it walk to the nearest base.
"""
class BN_ReturnToBase(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        self.my_goal = None
        super(BN_ReturnToBase, self).__init__("BN_ReturnToBase")
        self.my_agent = aagent
        self.debug_current_state=None

    def initialise(self) -> None:
        self.my_goal= asyncio.create_task(Goals_BT_Basic.Walk_To(self.my_agent,"BaseAlpha").run())

    def update(self) -> pt.common.Status:
        #TODO remove temp
        temp= common_goal_update(self.my_goal)
        if temp!= self.debug_current_state:
            self.debug_current_state=temp
            print("Return To Base:",temp)
        return temp
    
    def terminate(self, new_status: common.Status) -> None:
        print("Terminate ReturnToBase")
        if self.my_goal != None:
            self.my_goal.cancel()

class BN_DropOffFlowers(pt.behaviour.Behaviour):
    def __init__(self, aagent):
        self.my_goal=None
        super(BN_DropOffFlowers,self).__init__("BN_DropOffFlowers")
        self.my_agent=aagent

    def initialise(self) -> None:
        self.my_goal=asyncio.create_task(Goals_BT_Basic.Drop_Off_Flowers(self.my_agent,2).run())

    def update(self) -> common.Status:
        return common_goal_update(self.my_goal)

    def terminate(self, new_status: common.Status) -> None:
        print("Terminate DropOffFlowers")
        if self.my_goal!=None:
            self.my_goal.cancel()
    
        


###### Flower Protocol BNs #####

class BN_DetectFlower(pt.behaviour.Behaviour):
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

'''Turns towards a flower and then moves forward until it hits something'''
class BN_MoveToFlower(pt.behaviour.Behaviour):

    def __init__(self, aagent):
        self.turn_degrees=9 # Ideally should be the degrees between each ray
        self.forward_movement=5 #Ideally should be ray length
        self.my_goal = None
        super(BN_MoveToFlower, self).__init__("BN_MoveToFlower")
        self.my_agent = aagent
        self.debug_current_state=None #DEBUGING var

    def initialise(self):
        print("BN_MoveToFlower Intializing")
        #We'll first store where the flowers are relative to the agent so that we can later prioritize ones over others to avoid constant target switching
        sensor_obj_info = self.my_agent.rc_sensor.sensor_rays[Sensors.RayCastSensor.OBJECT_INFO]
        for index, value in enumerate(sensor_obj_info):
            if value:  # there is a hit with an object
                if value["tag"] == "AlienFlower":  # If it is a flower
                    
                    #Flower's straight ahead
                    if index == 2:
                       #print("Flower forward")
                        self.my_goal = asyncio.create_task(Goals_BT_Basic.ForwardDist(self.my_agent,self.forward_movement,0,5).run())

                    #Flower's to your left
                    if index < 2:
                       #print(f"Flower left index: {index}")
                        self.my_goal = asyncio.create_task(Goals_BT_Basic.Turn_customizable(self.my_agent,-1,(index+1)*self.turn_degrees).run())
                    
                    #Flower's to your right
                    if index > 2:
                       #print(f"Flower right index: {index}")
                        self.my_goal = asyncio.create_task(Goals_BT_Basic.Turn_customizable(self.my_agent,1,(index+1)*self.turn_degrees).run())
                    break
                
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
            print("Canceling Goal")
        

###### Roaming BNs Don't Touch Much #######

class BN_ForwardRandom(pt.behaviour.Behaviour):
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
        print("Terminate BN_ForwardRandom")
        self.logger.debug("Terminate BN_ForwardRandom")
        if self.my_goal != None:
            self.my_goal.cancel()


class BN_TurnRandom(pt.behaviour.Behaviour):
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
        print("Terminate BN_TurnRandom")
        self.logger.debug("Terminate BN_TurnRandom")
        if self.my_goal!=None:
            self.my_goal.cancel()


###### Detect Frozen BN Don't Touch Much #######

class BN_DetectFrozen(pt.behaviour.Behaviour):  
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
        #Check inventory when 2 return to base
        return_to_base= pt.composites.Sequence(name="ReturnToBase",memory=False)
        return_to_base.add_children([
                                        BN_CheckInventory(aagent),
                                        BN_ReturnToBase(aagent),
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
                                    return_to_base,
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
