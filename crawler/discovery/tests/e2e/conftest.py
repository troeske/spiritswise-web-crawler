"""
Shared fixtures for E2E tests.

Provides mock API responses, database fixtures, and helper utilities
for testing the complete Product Discovery pipeline.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# =============================================================================
# Mock SerpAPI Responses
# =============================================================================

@pytest.fixture
def mock_google_search_response():
    """Mock response from Google Search API."""
    return {
        "search_metadata": {
            "id": "search_123",
            "status": "Success",
            "created_at": "2024-01-15 10:00:00 UTC",
        },
        "search_parameters": {
            "q": "whisky online shop",
            "engine": "google",
        },
        "organic_results": [
            {
                "position": 1,
                "title": "Master of Malt - Premium Whisky Shop",
                "link": "https://www.masterofmalt.com/",
                "displayed_link": "www.masterofmalt.com",
                "snippet": "Buy whisky online from the UK's largest whisky shop.",
            },
            {
                "position": 2,
                "title": "The Whisky Exchange - Buy Whisky Online",
                "link": "https://www.thewhiskyexchange.com/",
                "displayed_link": "www.thewhiskyexchange.com",
                "snippet": "The world's best whisky shop with over 10,000 whiskies.",
            },
            {
                "position": 3,
                "title": "Whisky Advocate Reviews",
                "link": "https://www.whiskyadvocate.com/ratings/",
                "displayed_link": "www.whiskyadvocate.com",
                "snippet": "Expert whisky reviews and ratings. See our top rated whiskies.",
            },
            {
                "position": 4,
                "title": "Total Wine & More - Spirits",
                "link": "https://www.totalwine.com/spirits",
                "displayed_link": "www.totalwine.com",
                "snippet": "Shop our wide selection of whisky and spirits.",
            },
            {
                "position": 5,
                "title": "Facebook - Whisky Community",
                "link": "https://www.facebook.com/whisky",
                "displayed_link": "www.facebook.com",
                "snippet": "Join our whisky lovers community.",
            },
        ],
    }


@pytest.fixture
def mock_google_shopping_response():
    """Mock response from Google Shopping API."""
    return {
        "search_metadata": {
            "id": "shopping_123",
            "status": "Success",
        },
        "shopping_results": [
            {
                "position": 1,
                "title": "Macallan 18 Year Old Sherry Oak",
                "price": "$299.99",
                "extracted_price": 299.99,
                "source": "Total Wine",
                "link": "https://www.totalwine.com/macallan-18",
                "thumbnail": "https://images.totalwine.com/macallan18.jpg",
            },
            {
                "position": 2,
                "title": "The Macallan 18 Year Old Single Malt Scotch",
                "price": "$319.99",
                "extracted_price": 319.99,
                "source": "BevMo",
                "link": "https://www.bevmo.com/macallan-18",
                "thumbnail": "https://images.bevmo.com/macallan18.jpg",
            },
            {
                "position": 3,
                "title": "Macallan 18 Sherry Cask - 750ml",
                "price": "$289.00",
                "extracted_price": 289.00,
                "source": "Master of Malt",
                "link": "https://www.masterofmalt.com/macallan-18",
                "thumbnail": "https://images.masterofmalt.com/macallan18.jpg",
            },
            {
                "position": 4,
                "title": "Random Wine Product",
                "price": "$25.00",
                "extracted_price": 25.00,
                "source": "Wine Shop",
                "link": "https://www.wineshop.com/wine",
                "thumbnail": "https://images.wineshop.com/wine.jpg",
            },
        ],
    }


@pytest.fixture
def mock_google_images_response():
    """Mock response from Google Images API."""
    return {
        "search_metadata": {
            "id": "images_123",
            "status": "Success",
        },
        "images_results": [
            {
                "position": 1,
                "title": "Macallan 18 Bottle Shot",
                "original": "https://images.example.com/macallan18_full.jpg",
                "thumbnail": "https://images.example.com/macallan18_thumb.jpg",
                "source": "masterofmalt.com",
                "original_width": 1200,
                "original_height": 1800,
            },
            {
                "position": 2,
                "title": "Macallan 18 Label Detail",
                "original": "https://images.example.com/macallan18_label.jpg",
                "thumbnail": "https://images.example.com/macallan18_label_thumb.jpg",
                "source": "whiskybase.com",
                "original_width": 800,
                "original_height": 600,
            },
            {
                "position": 3,
                "title": "Macallan Box and Packaging",
                "original": "https://images.example.com/macallan18_box.jpg",
                "thumbnail": "https://images.example.com/macallan18_box_thumb.jpg",
                "source": "thewhiskyexchange.com",
                "original_width": 1000,
                "original_height": 1000,
            },
            {
                "position": 4,
                "title": "Small Icon",
                "original": "https://images.example.com/small_icon.jpg",
                "thumbnail": "https://images.example.com/small_icon_thumb.jpg",
                "source": "example.com",
                "original_width": 50,
                "original_height": 50,
            },
        ],
    }


@pytest.fixture
def mock_google_news_response():
    """Mock response from Google News API."""
    return {
        "search_metadata": {
            "id": "news_123",
            "status": "Success",
        },
        "news_results": [
            {
                "position": 1,
                "title": "Macallan Releases New Limited Edition 18 Year Old",
                "link": "https://www.whiskyadvocate.com/macallan-new-release",
                "source": {"name": "Whisky Advocate"},
                "date": "2 days ago",
                "snippet": "The Macallan has announced a new limited edition of their popular 18 year old expression.",
                "thumbnail": "https://www.whiskyadvocate.com/thumb.jpg",
            },
            {
                "position": 2,
                "title": "Top Whisky Picks for 2024",
                "link": "https://www.forbes.com/whisky-picks-2024",
                "source": {"name": "Forbes"},
                "date": "1 week ago",
                "snippet": "Our experts pick the best whiskies to buy this year.",
            },
            {
                "position": 3,
                "title": "Old Article About Whisky",
                "link": "https://www.oldsite.com/article",
                "source": {"name": "Old Site"},
                "date": "3 years ago",
                "snippet": "This is an old article that should be filtered out.",
            },
        ],
    }


@pytest.fixture
def mock_review_search_response():
    """Mock response for review searches."""
    return {
        "organic_results": [
            {
                "position": 1,
                "title": "Macallan 18 Review - 94 Points",
                "link": "https://www.whiskyadvocate.com/macallan-18-review",
                "snippet": "This exceptional whisky earned 94 points in our review. Rich and complex.",
            },
            {
                "position": 2,
                "title": "Macallan 18 - 4.5/5 Stars Customer Rating",
                "link": "https://www.masterofmalt.com/macallan-18-reviews",
                "snippet": "Customer rating: 4.5 / 5 stars based on 250 reviews.",
            },
            {
                "position": 3,
                "title": "Is Macallan 18 Worth It?",
                "link": "https://www.reddit.com/r/whisky/macallan18",
                "snippet": "Discussion about whether the Macallan 18 is worth the price.",
            },
        ],
    }


# =============================================================================
# Mock Product Fixtures
# =============================================================================

@pytest.fixture
def mock_discovered_product():
    """Create a mock DiscoveredProduct for testing."""
    product = MagicMock()
    product.id = 1
    product.extracted_data = {
        "name": "Macallan 18 Year Old",
        "brand": "Macallan",
        "category": "Single Malt Scotch",
        "age": "18 years",
        "region": "Speyside",
    }
    product.product_type = "whisky"
    product.enrichment_status = "pending"
    product.price_history = []
    product.best_price = None
    product.images = []
    product.ratings = []
    product.press_mentions = []

    # Mock methods
    product.save = MagicMock()
    product.add_image = MagicMock()
    product.add_rating = MagicMock()
    product.add_press_mention = MagicMock()
    product.update_best_price = MagicMock()

    return product


@pytest.fixture
def mock_discovered_product_list():
    """Create a list of mock products for batch testing."""
    products = []
    whisky_data = [
        {"name": "Glenfiddich 12 Year Old", "brand": "Glenfiddich"},
        {"name": "Lagavulin 16 Year Old", "brand": "Lagavulin"},
        {"name": "Highland Park 18", "brand": "Highland Park"},
    ]

    for i, data in enumerate(whisky_data, start=1):
        product = MagicMock()
        product.id = i
        product.extracted_data = data
        product.product_type = "whisky"
        product.enrichment_status = "pending"
        product.price_history = []
        product.images = []
        product.ratings = []
        product.press_mentions = []
        product.save = MagicMock()
        product.add_image = MagicMock()
        product.add_rating = MagicMock()
        product.add_press_mention = MagicMock()
        product.update_best_price = MagicMock()
        products.append(product)

    return products


# =============================================================================
# Mock SerpAPI Client
# =============================================================================

@pytest.fixture
def mock_serpapi_client(
    mock_google_search_response,
    mock_google_shopping_response,
    mock_google_images_response,
    mock_google_news_response,
):
    """Create a mock SerpAPIClient that returns preset responses."""
    client = MagicMock()
    client.google_search.return_value = mock_google_search_response
    client.google_shopping.return_value = mock_google_shopping_response
    client.google_images.return_value = mock_google_images_response
    client.google_news.return_value = mock_google_news_response
    return client


@pytest.fixture
def mock_serpapi_client_with_errors():
    """Create a mock SerpAPIClient that simulates various errors."""
    client = MagicMock()

    call_count = {"search": 0, "shopping": 0, "images": 0, "news": 0}

    def search_side_effect(*args, **kwargs):
        call_count["search"] += 1
        if call_count["search"] == 2:
            raise Exception("Rate limit exceeded")
        return {"organic_results": []}

    def shopping_side_effect(*args, **kwargs):
        call_count["shopping"] += 1
        if call_count["shopping"] == 1:
            raise Exception("API Error")
        return {"shopping_results": []}

    client.google_search.side_effect = search_side_effect
    client.google_shopping.side_effect = shopping_side_effect
    client.google_images.return_value = {"images_results": []}
    client.google_news.return_value = {"news_results": []}

    return client


# =============================================================================
# Cache and Rate Limiter Fixtures
# =============================================================================

@pytest.fixture
def mock_cache():
    """Create a mock cache for testing."""
    cache_data = {}

    cache = MagicMock()

    def get_func(key, default=None):
        return cache_data.get(key, default)

    def set_func(key, value, timeout=None):
        cache_data[key] = value

    def delete_func(key):
        cache_data.pop(key, None)

    def incr_func(key, delta=1):
        if key in cache_data:
            cache_data[key] += delta
        else:
            cache_data[key] = delta
        return cache_data[key]

    cache.get = MagicMock(side_effect=get_func)
    cache.set = MagicMock(side_effect=set_func)
    cache.delete = MagicMock(side_effect=delete_func)
    cache.incr = MagicMock(side_effect=incr_func)
    cache._data = cache_data  # Expose for inspection

    return cache


@pytest.fixture
def mock_rate_limiter_allowed():
    """Create a mock rate limiter that always allows requests."""
    limiter = MagicMock()
    limiter.can_make_request.return_value = True
    limiter.record_request.return_value = None
    limiter.get_remaining_daily.return_value = 100
    limiter.get_remaining_monthly.return_value = 4000
    return limiter


@pytest.fixture
def mock_rate_limiter_blocked():
    """Create a mock rate limiter that blocks all requests."""
    limiter = MagicMock()
    limiter.can_make_request.return_value = False
    limiter.get_remaining_daily.return_value = 0
    limiter.get_remaining_monthly.return_value = 0
    return limiter


# =============================================================================
# URL and Domain Fixtures
# =============================================================================

@pytest.fixture
def sample_urls():
    """Sample URLs for testing URL extraction."""
    return [
        "https://www.masterofmalt.com/whisky/macallan-18",
        "https://www.thewhiskyexchange.com/p/lagavulin-16",
        "https://www.totalwine.com/spirits/scotch/glenfiddich",
        "https://www.whiskyadvocate.com/ratings/highland-park",
        "https://www.facebook.com/whiskypage",
        "https://www.amazon.com/whisky-bottles",
        "https://www.reddit.com/r/whisky",
    ]


@pytest.fixture
def expected_priority_urls():
    """URLs that should be prioritized."""
    return [
        "https://www.masterofmalt.com/whisky/macallan-18",
        "https://www.thewhiskyexchange.com/p/lagavulin-16",
        "https://www.totalwine.com/spirits/scotch/glenfiddich",
    ]


@pytest.fixture
def expected_excluded_urls():
    """URLs that should be excluded."""
    return [
        "https://www.facebook.com/whiskypage",
        "https://www.reddit.com/r/whisky",
    ]
