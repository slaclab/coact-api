"""
Behavioral tests for FacilityComputeAllocation request handling in models and schema.
"""
from unittest.mock import Mock, MagicMock

import pytest

from schema import Mutation
from models import CoactRequestStatus, CoactRequestType, FacilityInput, ClusterInput

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


def test_facility_purchase_mutation_is_auto_approved_and_audited():
    """
    The mutation self-approves, so the audit trail is the only record of who changed
    the purchase and by how much.
    """
    info = _make_info(existing_servers=100)
    Mutation().facilityAddUpdateComputePurchase(
        facility=FacilityInput(name='lcls'),
        cluster=ClusterInput(name='ada'),
        purchase=200.0,
        info=info,
    )

    req = info.context.db.create.call_args[0][1]
    assert req.approvalstatus == CoactRequestStatus.Approved
    # the daemon dispatches off this value coming back out of the change stream
    assert int(req.approvalstatus) == 1
    action = info.context.audit.call_args.args[2]
    details = info.context.audit.call_args.kwargs['details']
    assert action == 'facilityAddUpdateComputePurchase'
    assert '100' in details and '200' in details


def test_facility_purchase_mutation_reports_zero_old_purchased_on_first_purchase():
    """With no prior record the mutation inserts one and reports oldPurchased as 0."""
    info = _make_info(existing_servers=None)
    Mutation().facilityAddUpdateComputePurchase(
        facility=FacilityInput(name='lcls'),
        cluster=ClusterInput(name='ada'),
        purchase=50.0,
        info=info,
    )

    req = info.context.db.create.call_args[0][1]
    assert req.oldPurchased == 0
    assert req.newPurchased == 50
    info.context.db.collection.return_value.insert_one.assert_called_once()


def _make_approve_info(is_admin=True, is_czar=False, **request_fields):
    info = Mock()
    info.context.authn.return_value = 'someone'
    info.context.is_admin = is_admin

    thereq = Mock()
    thereq.reqtype = "FacilityComputeAllocation"
    thereq.reponame = None
    thereq.facilityname = 'lcls'
    thereq.clustername = 'ada'
    thereq.newPurchased = 200
    for k, v in request_fields.items():
        setattr(thereq, k, v)

    info.context.db.find_request.return_value = thereq
    czar_facility = Mock()
    czar_facility.name = 'lcls'
    info.context.db.find_facilities.return_value = [czar_facility] if is_czar else []
    return info, thereq


def test_approve_facility_compute_allocation_happy_path():
    info, thereq = _make_approve_info()

    assert Mutation().requestApprove(id=FAKE_ID, info=info) is True
    thereq.approve.assert_called_once_with(info)


def test_approve_facility_compute_allocation_rejects_czar():
    """Compute purchases are a budget action, so a facility czar must not approve one."""
    info, thereq = _make_approve_info(is_admin=False, is_czar=True)

    with pytest.raises(Exception, match='Only an admin'):
        Mutation().requestApprove(id=FAKE_ID, info=info)
    thereq.approve.assert_not_called()


@pytest.mark.parametrize("field", ["facilityname", "clustername", "newPurchased"])
def test_approve_facility_compute_allocation_requires_core_fields(field):
    info, thereq = _make_approve_info(**{field: None})

    with pytest.raises(Exception, match='cannot approve'):
        Mutation().requestApprove(id=FAKE_ID, info=info)
    thereq.approve.assert_not_called()
