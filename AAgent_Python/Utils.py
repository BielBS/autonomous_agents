import py_trees as pt


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
    if goal is None:
        return pt.common.Status.FAILURE

    if not goal.done():
        return pt.common.Status.RUNNING

    return pt.common.Status.SUCCESS if goal.result() else pt.common.Status.FAILURE


def get_inventory_amount(inventory, item_name="AlienFlower"):
    """
    Returns the amount stored for a given inventory item.
    """
    return next(
        (item["amount"] for item in inventory if item["name"] == item_name),
        0
    )
