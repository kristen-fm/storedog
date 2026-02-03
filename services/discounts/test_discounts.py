"""
Unit tests for the discounts.py Flask API endpoints.

This test suite uses true unit testing principles by mocking all external dependencies
(database, environment variables) to test the API endpoints in isolation.

Setup Strategy:
1. Set environment variables (POSTGRES_*) before imports to prevent KeyError during module load
2. Mock the database (bootstrap.db) to prevent actual database connections and initialization
3. Use Flask's test_client() to simulate HTTP requests without running a server
4. Mock Discount.query chains to return controlled test data instead of hitting the database

This approach ensures:
- Tests run without requiring a PostgreSQL database
- Tests are fast and isolated
- Each endpoint is tested independently with mock data
- No side effects between tests

Note: test_post_discount_success contains intentional flakiness for educational purposes.
Without mocking random.randint and words.get_random, the test will pass ~94% of the time
and fail ~6% of the time. See comments in that test for how to fix it.

To run the tests with test coverage, use the following command:

    docker compose -f docker-compose.dev.yml exec discounts sh -c \
        "coverage erase &&
        python -m coverage run -m unittest discover -p 'test*.py' -v &&
        python -m coverage report --show-missing"

"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, Mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock environment variables before importing discounts module
os.environ['POSTGRES_USER'] = 'test_user'
os.environ['POSTGRES_PASSWORD'] = 'test_password'
os.environ['POSTGRES_HOST'] = 'test_host'

# Mock the database initialization to prevent actual DB connection
with patch('bootstrap.db') as mock_db:
    mock_db.init_app = Mock()
    mock_db.drop_all = Mock()
    mock_db.create_all = Mock()
    mock_db.session = Mock()
    # Import after environment and mocks are set up
    from discounts import app


class TestDiscountsAPI(unittest.TestCase):

    def setUp(self):
        """Set up test client before each test"""
        self.app = app.test_client()
        self.app.testing = True

    @patch('discounts.Discount')
    def test_get_discounts_success(self, mock_discount_class):
        """Test GET /discount returns list of discounts successfully"""
        # Create mock discount objects
        mock_discount_1 = MagicMock()
        mock_discount_1.serialize.return_value = {
            'id': 1,
            'name': 'Summer Sale',
            'code': 'SUMMER20',
            'value': 20,
            'discount_type': {'id': 1, 'name': 'Percentage', 'discount_query': 'price * 0.8'}
        }

        mock_discount_2 = MagicMock()
        mock_discount_2.serialize.return_value = {
            'id': 2,
            'name': 'Winter Sale',
            'code': 'WINTER10',
            'value': 10,
            'discount_type': {'id': 2, 'name': 'Fixed', 'discount_query': 'price - 10'}
        }

        # Mock the query chain: Discount.query.all()
        mock_discount_class.query.all.return_value = [mock_discount_1, mock_discount_2]

        # Make request
        response = self.app.get('/discount')

        # Assertions
        self.assertEqual(200, response.status_code)
        self.assertEqual('application/json', response.content_type)

        # Verify response data
        json_data = response.get_json()
        self.assertEqual(2, len(json_data))
        self.assertEqual('Summer Sale', json_data[0]['name'])
        self.assertEqual('SUMMER20', json_data[0]['code'])
        self.assertEqual(20, json_data[0]['value'])
        self.assertEqual('Winter Sale', json_data[1]['name'])

        # Verify mock was called
        mock_discount_class.query.all.assert_called_once()
    
    # FLAKY TEST: Uncomment the patches below to fix the flakiness
    # @patch('discounts.random.randint')
    # @patch('discounts.words.get_random')
    @patch('discounts.db')
    @patch('discounts.DiscountType')
    @patch('discounts.Discount')
    def test_post_discount_success(
        self,
        mock_discount_class,
        mock_discount_type_class,
        mock_db,
        # mock_get_random,
        # mock_randint,
    ):
        """Test POST /discount creates a new discount and returns updated list"""

        # Existing discounts returned by the first Discount.query.all()
        existing_1 = MagicMock()
        existing_1.serialize.return_value = {'id': 1, 'name': 'Existing 1'}

        existing_2 = MagicMock()
        existing_2.serialize.return_value = {'id': 2, 'name': 'Existing 2'}

        # The new discount that will appear in the second Discount.query.all()
        # Note: These hardcoded values match what the mocks would produce when uncommented
        new_discount_obj = MagicMock()
        new_discount_obj.serialize.return_value = {
            'id': 3,
            'name': 'Discount 3',
            'code': 'SOMEWORD',  # Would be 'SOMEWORD' with mocks enabled
            'value': 123  # Would be 123 with mocks enabled
        }

        # Mock Discount.query.all() called twice:
        # 1) to compute discounts_count
        # 2) to return updated list after insert
        mock_discount_class.query.all.side_effect = [
            [existing_1, existing_2],
            [existing_1, existing_2, new_discount_obj],
        ]

        # FLAKY: Uncomment the lines below to fix randomness
        # Mock randomness + words generator
        # First randint is for words.get_random( randint(2,4) )
        # Second randint is for discount value randint(10,500)
        # mock_randint.side_effect = [3, 123]
        # mock_get_random.return_value = 'SOMEWORD'

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
        response = self.app.post('/discount')

        # Assertions: response basics
        self.assertEqual(200, response.status_code)
        self.assertEqual('application/json', response.content_type)

        json_data = response.get_json()
        self.assertEqual(3, len(json_data))
        self.assertEqual('Existing 1', json_data[0]['name'])
        self.assertEqual('Existing 2', json_data[1]['name'])
        self.assertEqual('Discount 3', json_data[2]['name'])

        # FLAKY ASSERTION: This is what makes the test flaky!
        # We're checking the actual random value passed to the Discount constructor
        call_args = mock_discount_class.call_args[0]
        discount_code = call_args[1]  # second argument is the code from words.get_random()
        discount_value = call_args[2]  # third argument is the value from random.randint(10, 500)

        # This assertion checks that the random value is less than 471
        # Since the actual code generates random.randint(10, 500), this will:
        # - PASS when the random value is 10-470 (~94% of the time)
        # - FAIL when the random value is 471-500 (~6% of the time)
        #
        # To fix: Uncomment the @patch decorators and mock setup above (lines 101-102, 145-146)
        self.assertLess(discount_value, 471)

        # Verify constructors called with expected args
        mock_discount_type_class.assert_called_once_with(
            'Random Savings',
            'price * .9',
            None
        )

        # FLAKY: When you uncomment the mocks above, also uncomment these assertions
        # to verify the Discount constructor was called with the expected mocked values
        # mock_get_random.assert_called_once_with(3)
        # mock_discount_class.assert_called_once_with(
        #     'Discount 3',
        #     'SOMEWORD',
        #     123,
        #     mock_discount_type_instance
        # )

        # Verify DB session operations
        mock_db.session.add.assert_called_once_with(mock_discount_instance)
        mock_db.session.commit.assert_called_once()

        # Verify query usage (called twice total)
        self.assertEqual(2, mock_discount_class.query.all.call_count)

if __name__ == '__main__':
    unittest.main()
