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

