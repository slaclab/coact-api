"""
Behavioral tests for FacilityComputeAllocation request handling in models and schema.
"""
from unittest.mock import Mock, MagicMock

from schema import Mutation
from models import CoactRequestType, FacilityInput, ClusterInput

FAKE_ID = 'a' * 24  # 24-char hex string accepted wherever an ObjectId str is needed


def _make_info(existing_servers=None):
    """Build a mock info context. existing_servers simulates a pre-existing purchase record."""
    info = Mock()
    info.context.username = 'admin'
    info.context.is_admin = True

    col = MagicMock()
    info.context.db.collection.return_value = col

    facility = Mock()
    facility.name = 'lcls'
    cluster = Mock()
    cluster.name = 'ada'
    info.context.db.find_cluster.return_value = cluster
    info.context.db.find_facility.side_effect = [facility, Mock()]
    info.context.db.find_facilities.return_value = []
    info.context.db.create.return_value = Mock()
    info.context.authn.return_value = 'admin'

    if existing_servers is not None:
        col.find.return_value.sort.return_value.limit.return_value = [
            {'_id': FAKE_ID, 'servers': existing_servers, 'burst_percent': 0}
        ]
    else:
        col.find.return_value.sort.return_value.limit.return_value = []
        col.insert_one.return_value.inserted_id = FAKE_ID

    return info


def test_facility_purchase_mutation_captures_old_and_new_purchased():
    """
    facilityAddUpdateComputePurchase must read the current servers value from the
    DB record as oldPurchased before overwriting it, set newPurchased to the
    incoming purchase amount, and tag updateStrategy='proportional' — giving the
    daemon everything it needs to cascade repo allocations proportionally.
    """
    info = _make_info(existing_servers=100)
    Mutation().facilityAddUpdateComputePurchase(
        facility=FacilityInput(name='lcls'),
        cluster=ClusterInput(name='ada'),
        purchase=200.0,
        info=info,
    )

    req = info.context.db.create.call_args[0][1]
    assert req.reqtype == CoactRequestType.FacilityComputeAllocation
    assert req.oldPurchased == 100
    assert req.newPurchased == 200
    assert req.updateStrategy == 'proportional'
