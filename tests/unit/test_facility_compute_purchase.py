"""
Unit tests for Mutation.facilityAddUpdateComputePurchase and its handling of burst_nodes.
"""
import pytest
from unittest.mock import Mock
from schema import Mutation


def mock_info(current_purchase=None):
    info = Mock()
    info.context.username = "admin"
    info.context.db.find_facility.return_value = Mock(name="facility")
    info.context.db.find_facility.return_value.name = "testfac"
    info.context.db.find_cluster.return_value = Mock()
    info.context.db.find_cluster.return_value.name = "milano"
    purchases = Mock()
    purchases.find.return_value.sort.return_value.limit.return_value = [current_purchase] if current_purchase else []
    purchases.insert_one.return_value.inserted_id = "new-id"
    info.context.db.collection.return_value = purchases
    return info, purchases


def call(info, **kwargs):
    return Mutation.facilityAddUpdateComputePurchase(None, facility=Mock(), cluster=Mock(), info=info, **kwargs)


def test_omitted_burst_keeps_the_current_burst():
    info, purchases = mock_info({"_id": "cp-1", "servers": 10, "burst_nodes": 16})
    call(info, purchase=20)
    purchases.update_one.assert_called_once_with({"_id": "cp-1"}, {"$set": {"servers": 20}})


def test_given_burst_is_updated():
    info, purchases = mock_info({"_id": "cp-1", "servers": 10, "burst_nodes": 16})
    call(info, purchase=20, burst_nodes=0)
    purchases.update_one.assert_called_once_with({"_id": "cp-1"}, {"$set": {"servers": 20, "burst_nodes": 0}})


@pytest.mark.parametrize("burst,stored", [(None, 0.0), (8, 8)])
def test_new_purchase_stores_burst(burst, stored):
    info, purchases = mock_info()
    call(info, purchase=20, burst_nodes=burst)
    doc = purchases.insert_one.call_args.args[0]
    assert doc["servers"] == 20
    assert doc["burst_nodes"] == stored


def test_negative_burst_is_rejected():
    info, purchases = mock_info({"_id": "cp-1", "servers": 10, "burst_nodes": 16})
    with pytest.raises(Exception, match="Invalid burst node count"):
        call(info, purchase=20, burst_nodes=-1)
    purchases.update_one.assert_not_called()
