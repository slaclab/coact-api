"""
Unit test for the Facility model computepurchases field that CLI depends on.
"""
import pytest
from unittest.mock import Mock
from datetime import datetime, timezone
from models import Facility, FacilityComputePurchases


def test_facility_computepurchases_aggregates_purchased_nodes():
    """Test that Facility.computepurchases correctly aggregates purchased nodes data for CLI."""
    facility = Facility(name="testfac", description="Test Facility")

    # Mock the GraphQL info context and database
    mock_info = Mock()
    mock_collection = Mock()
    mock_info.context.db.collection.return_value = mock_collection

    # Mock aggregation results for compute purchases (what CLI needs)
    mock_purchases_result = [
        {"_id": {"clustername": "ada"}, "servers": 256, "burst_percent": 20}
    ]

    # Mock aggregation results for allocations
    mock_allocations_result = [
        {"clustername": "ada", "percent_of_facility": 75.0}
    ]

    mock_collection.aggregate.side_effect = [
        iter(mock_purchases_result),   # First call: purchases
        iter(mock_allocations_result)  # Second call: allocations
    ]

    # Mock datetime
    test_date = datetime(2026, 4, 24, tzinfo=timezone.utc)
    with pytest.MonkeyPatch().context() as m:
        m.setattr('models.datetime', Mock(utcnow=Mock(return_value=test_date)))
        result = facility.computepurchases(mock_info)

    # Verify CLI gets the purchased nodes data it needs
    assert len(result) == 1
    assert isinstance(result[0], FacilityComputePurchases)

    ada_purchase = result[0]
    assert ada_purchase.clustername == "ada"
    assert ada_purchase.purchased == 256  # This is what CLI queries for purchased nodes
    assert ada_purchase.burst_percent == 20
    assert ada_purchase.allocated == 75.0