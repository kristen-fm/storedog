"""
Pytest unit tests for the discounts.py Flask API endpoints.

Setup Strategy:
1. Set environment variables (POSTGRES_*) before imports to prevent KeyError during module load
2. Mock the database (bootstrap.db) to prevent actual database connections and initialization
3. Use Flask's test_client() to simulate HTTP requests without running a server
4. Mock Discount.query chains to return controlled test data instead of hitting the database

Note: test_post_discount_success contains intentional flakiness for educational purposes.
Without mocking random.randint and words.get_random, the test will pass/fail depending on randomness.
"""

from unittest.mock import patch, MagicMock, Mock


def test_get_discounts_success(client):
    """Test GET /discount returns list of discounts successfully"""
    with patch("discounts.Discount") as mock_discount_class:
        # Create mock discount objects
        mock_discount_1 = MagicMock()
        mock_discount_1.serialize.return_value = {
            "id": 1,
            "name": "Summer Sale",
            "code": "SUMMER20",
            "value": 20,
            "discount_type": {
                "id": 1,
                "name": "Percentage",
                "discount_query": "price * 0.8",
            },
        }

        mock_discount_2 = MagicMock()
        mock_discount_2.serialize.return_value = {
            "id": 2,
            "name": "Winter Sale",
            "code": "WINTER10",
            "value": 10,
            "discount_type": {"id": 2, "name": "Fixed", "discount_query": "price - 10"},
        }

        # Mock the query chain: Discount.query.all()
        mock_discount_class.query.all.return_value = [mock_discount_1, mock_discount_2]

        # Make request
        response = client.get("/discount")

        # Assertions
        assert response.status_code == 200
        assert response.content_type == "application/json"

        json_data = response.get_json()
        assert len(json_data) == 2
        assert json_data[0]["name"] == "Summer Sale"
        assert json_data[0]["code"] == "SUMMER20"
        assert json_data[0]["value"] == 20
        assert json_data[1]["name"] == "Winter Sale"

        mock_discount_class.query.all.assert_called_once()


def test_post_discount_success(client):
    """
    Test POST /discount creates a new discount and returns updated list.

    FLAKY TEST (intentional): randomness is not mocked.
    Uncomment patches for discounts.random.randint and discounts.words.get_random to fix flakiness.
    """
    # FLAKY FIX (optional):
    # with patch("discounts.random.randint") as mock_randint, patch("discounts.words.get_random") as mock_get_random:
    #     mock_randint.side_effect = [3, 123]
    #     mock_get_random.return_value = "SOMEWORD"
    #     ...

    with patch("discounts.db") as mock_db, \
         patch("discounts.DiscountType") as mock_discount_type_class, \
         patch("discounts.Discount") as mock_discount_class:

        # Existing discounts returned by the first Discount.query.all()
        existing_1 = MagicMock()
        existing_1.serialize.return_value = {"id": 1, "name": "Existing 1"}

        existing_2 = MagicMock()
        existing_2.serialize.return_value = {"id": 2, "name": "Existing 2"}

        # The new discount that will appear in the second Discount.query.all()
        # (Hardcoded values are fine because they come from our mocked objects' serialize())
        new_discount_obj = MagicMock()
        new_discount_obj.serialize.return_value = {
            "id": 3,
            "name": "Discount 3",
            "code": "SOMEWORD",
            "value": 123,
        }

        # Mock Discount.query.all() called twice:
        # 1) to compute discounts_count
        # 2) to return updated list after insert
        mock_discount_class.query.all.side_effect = [
            [existing_1, existing_2],
            [existing_1, existing_2, new_discount_obj],
        ]

        # Mock DiscountType() construction
        mock_discount_type_instance = MagicMock()
        mock_discount_type_class.return_value = mock_discount_type_instance

        # Mock Discount() construction (the object that gets added/committed)
        mock_discount_instance = MagicMock()
        mock_discount_class.return_value = mock_discount_instance

        # Ensure db.session exists as a mock with add/commit
        mock_db.session.add = Mock()
        mock_db.session.commit = Mock()

        # Make request
        response = client.post("/discount")

        # Assertions: response basics
        assert response.status_code == 200
        assert response.content_type == "application/json"

        json_data = response.get_json()
        assert len(json_data) == 3
        assert json_data[0]["name"] == "Existing 1"
        assert json_data[1]["name"] == "Existing 2"
        assert json_data[2]["name"] == "Discount 3"

        # FLAKY ASSERTION (intentional): depends on random.randint(10, 500)
        call_args = mock_discount_class.call_args[0]
        discount_value = call_args[2]  # third argument is the value from random.randint(10, 500)
        assert discount_value < 157

        # Verify constructors called with expected args
        mock_discount_type_class.assert_called_once_with("Random Savings", "price * .9", None)

        # Verify DB session operations
        mock_db.session.add.assert_called_once_with(mock_discount_instance)
        mock_db.session.commit.assert_called_once()

        # Verify query usage (called twice total)
        assert mock_discount_class.query.all.call_count == 2
