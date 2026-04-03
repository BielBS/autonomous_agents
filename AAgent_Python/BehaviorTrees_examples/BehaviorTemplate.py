import py_trees
import time


class CheckBattery(py_trees.behaviour.Behaviour):
    def __init__(self, name="Check Battery", threshold=20):
        """
        CONSTRUCTION: Called once when the tree is built.
        """
        super(CheckBattery, self).__init__(name)
        self.threshold = threshold
        self.logger.debug(f"[{self.name}] Initialized with threshold {self.threshold}%")

    def setup(self):
        """
        INFRASTRUCTURE: Called once to 'wire' the node to the system.
        """
        self.logger.debug(f"[{self.name}] setup() - Connecting to Battery Sensor...")
        # Simulate connecting to a hardware interface or ROS topic
        self.sensor_connected = True
        return True

    def initialise(self):
        """
        EXECUTION START: Called every time this node is ticked for the first time
        after being idle or completing its previous run.
        """
        self.logger.debug(f"[{self.name}] initialise() - Starting new check.")
        # Best place to reset a timer or a 'start_time' variable
        self.start_check_time = time.time()

    def update(self):
        """
        THE TICK: This runs every time the tree is ticked while this node is active.
        """
        # Logic: In a real robot, you'd read a real sensor here
        current_battery = 25

        self.logger.debug(f"[{self.name}] update() - Battery at {current_battery}%")

        if current_battery > self.threshold:
            return py_trees.common.Status.SUCCESS
        else:
            return py_trees.common.Status.FAILURE

    def terminate(self, new_status):
        """
        CLEANUP: Called when the node finishes (Success/Failure) or is interrupted.
        """
        self.logger.debug(f"[{self.name}] terminate({new_status}) - Cleaning up.")