"""
Tests for Price Finder.

Phase 4: Product Enrichment - TDD Tests for price_finder.py
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from crawler.discovery.enrichment.price_finder import PriceFinder, PriceAggregator


@pytest.fixture
def mock_client():
    """Create a mock SerpAPIClient."""
    return MagicMock()


@pytest.fixture
def price_finder(mock_client):
    """Create a PriceFinder with mock client."""
    return PriceFinder(client=mock_client)


@pytest.fixture
def mock_product():
    """Create a mock DiscoveredProduct."""
    product = MagicMock()
    product.extracted_data = {
        "name": "Glenfiddich 12 Year Old",
        "brand": "Glenfiddich",
    }
    product.price_history = []
    product.best_price = None
    return product


class TestPriceFinderInit:
    """Tests for PriceFinder initialization."""

    def test_init_with_client(self, mock_client):
        """Should initialize with provided client."""
        finder = PriceFinder(client=mock_client)
        assert finder.client == mock_client

    def test_init_creates_parser(self, mock_client):
        """Should create ShoppingResultParser."""
        finder = PriceFinder(client=mock_client)
        assert finder.parser is not None

    def test_init_creates_query_builder(self, mock_client):
        """Should create QueryBuilder."""
        finder = PriceFinder(client=mock_client)
        assert finder.query_builder is not None


class TestFindPrices:
    """Tests for find_prices method."""

    def test_find_prices_returns_list(self, price_finder, mock_client, mock_product):
        """Should return list of price entries."""
        mock_client.google_shopping.return_value = {
            "shopping_results": [
                {
                    "title": "Glenfiddich 12 Year Old Single Malt",
                    "price": "$45.99",
                    "source": "Total Wine",
                    "link": "https://totalwine.com/glenfiddich",
                }
            ]
        }

        prices = price_finder.find_prices(mock_product)

        assert isinstance(prices, list)

    def test_find_prices_includes_price_currency_retailer(self, price_finder, mock_client, mock_product):
        """Should include price, currency, retailer, url."""
        mock_client.google_shopping.return_value = {
            "shopping_results": [
                {
                    "title": "Glenfiddich 12 Year Old Whisky",
                    "price": "$45.99",
                    "source": "Master of Malt",
                    "link": "https://masterofmalt.com/glenfiddich",
                }
            ]
        }

        prices = price_finder.find_prices(mock_product)

        assert len(prices) > 0
        first = prices[0]
        assert "price" in first
        assert "currency" in first
        assert "retailer" in first
        assert "url" in first

    def test_find_prices_filters_irrelevant_results(self, price_finder, mock_client, mock_product):
        """Should filter out results that don't match product."""
        mock_client.google_shopping.return_value = {
            "shopping_results": [
                {
                    "title": "Glenfiddich 12 Year Old",
                    "price": "$45.99",
                    "source": "Shop1",
                    "link": "https://shop1.com",
                },
                {
                    "title": "Completely Different Product",
                    "price": "$99.99",
                    "source": "Shop2",
                    "link": "https://shop2.com",
                },
            ]
        }

        prices = price_finder.find_prices(mock_product)

        # Should only include relevant result
        assert len(prices) == 1
        assert prices[0]["price"] == 45.99

    def test_find_prices_handles_api_error(self, price_finder, mock_client, mock_product):
        """Should return empty list on API error."""
        mock_client.google_shopping.side_effect = Exception("API Error")

        prices = price_finder.find_prices(mock_product)

        assert prices == []

    def test_find_prices_respects_max_results(self, price_finder, mock_client, mock_product):
        """Should respect max_results limit."""
        mock_client.google_shopping.return_value = {
            "shopping_results": [
                {"title": f"Glenfiddich 12 Year {i}", "price": f"${40+i}", "source": f"Shop{i}", "link": f"https://shop{i}.com"}
                for i in range(20)
            ]
        }

        prices = price_finder.find_prices(mock_product, max_results=5)

        assert len(prices) <= 5


class TestGetBestPrice:
    """Tests for get_best_price method."""

    def test_get_best_price_returns_lowest(self, price_finder):
        """Should return the lowest price."""
        prices = [
            {"price": 59.99, "currency": "USD", "retailer": "Shop1", "url": "https://shop1.com"},
            {"price": 45.99, "currency": "USD", "retailer": "Shop2", "url": "https://shop2.com"},
            {"price": 52.00, "currency": "USD", "retailer": "Shop3", "url": "https://shop3.com"},
        ]

        best = price_finder.get_best_price(prices)

        assert best["price"] == 45.99
        assert best["retailer"] == "Shop2"

    def test_get_best_price_handles_empty_list(self, price_finder):
        """Should return None for empty list."""
        best = price_finder.get_best_price([])
        assert best is None

    def test_get_best_price_filters_zero_prices(self, price_finder):
        """Should filter out zero/invalid prices."""
        prices = [
            {"price": 0, "currency": "USD", "retailer": "Shop1", "url": ""},
            {"price": 45.99, "currency": "USD", "retailer": "Shop2", "url": ""},
        ]

        best = price_finder.get_best_price(prices)

        assert best["price"] == 45.99

    def test_get_best_price_returns_none_if_all_zero(self, price_finder):
        """Should return None if all prices are zero."""
        prices = [
            {"price": 0, "currency": "USD", "retailer": "Shop1", "url": ""},
            {"price": 0, "currency": "USD", "retailer": "Shop2", "url": ""},
        ]

        best = price_finder.get_best_price(prices)

        assert best is None


class TestIsRelevantResult:
    """Tests for _is_relevant_result method."""

    def test_matches_exact_product_name(self, price_finder):
        """Should match when product name is in result title."""
        result = price_finder._is_relevant_result(
            "glenfiddich 12 year old",
            "glenfiddich 12 year old single malt scotch whisky"
        )
        assert result is True

    def test_matches_partial_product_name(self, price_finder):
        """Should match when significant words match."""
        result = price_finder._is_relevant_result(
            "macallan 18 year old",
            "the macallan 18 year old sherry oak"
        )
        assert result is True

    def test_rejects_different_product(self, price_finder):
        """Should reject when product doesn't match."""
        result = price_finder._is_relevant_result(
            "glenfiddich 12 year old",
            "johnnie walker black label"
        )
        assert result is False

    def test_handles_empty_names(self, price_finder):
        """Should handle empty product names."""
        result = price_finder._is_relevant_result("", "any title")
        # Empty name has no significant words, so 0 matches >= 0 * 0.5
        assert result is True


class TestPriceAggregator:
    """Tests for PriceAggregator."""

    def test_aggregates_prices_to_history(self, mock_product):
        """Should add prices to product's price_history."""
        aggregator = PriceAggregator()
        prices = [
            {"price": 45.99, "currency": "USD", "retailer": "Shop1", "url": "https://shop1.com"},
            {"price": 52.00, "currency": "USD", "retailer": "Shop2", "url": "https://shop2.com"},
        ]

        aggregator.aggregate_prices(mock_product, prices)

        assert len(mock_product.price_history) == 2
        assert mock_product.price_history[0]["price"] == 45.99
        assert mock_product.price_history[0]["retailer"] == "Shop1"
        assert "date" in mock_product.price_history[0]

    def test_updates_best_price(self, mock_product):
        """Should update product's best_price."""
        aggregator = PriceAggregator()
        prices = [
            {"price": 59.99, "currency": "USD", "retailer": "Shop1", "url": "https://shop1.com"},
            {"price": 45.99, "currency": "USD", "retailer": "Shop2", "url": "https://shop2.com"},
        ]

        aggregator.aggregate_prices(mock_product, prices)

        # Should call update_best_price with lowest price
        mock_product.update_best_price.assert_called_once()
        call_kwargs = mock_product.update_best_price.call_args[1]
        assert call_kwargs["price"] == 45.99

    def test_saves_product(self, mock_product):
        """Should save the product after aggregation."""
        aggregator = PriceAggregator()
        prices = [{"price": 45.99, "currency": "USD", "retailer": "Shop1", "url": ""}]

        aggregator.aggregate_prices(mock_product, prices)

        mock_product.save.assert_called_once()

    def test_handles_empty_prices(self, mock_product):
        """Should handle empty prices list."""
        aggregator = PriceAggregator()

        aggregator.aggregate_prices(mock_product, [])

        # Should still save, but not call update_best_price
        mock_product.save.assert_called_once()
        mock_product.update_best_price.assert_not_called()
