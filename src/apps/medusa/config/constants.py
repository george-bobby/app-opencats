"""Medusa application constants and enums."""

from enum import Enum

from apps.medusa.config.settings import settings


class MedusaModelName(Enum):
    CUSTOMER = "customers"
    PRODUCT = "products"
    PRODUCT_VARIANT = "variants"
    PRODUCT_OPTION = "product-options"
    ORDER = "orders"
    REGION = "regions"
    SALES_CHANNEL = "sales-channels"
    SHIPPING_PROFILE = "shipping-profiles"
    PAYMENT_PROVIDER = "payment-providers"
    FULFILLMENT_PROVIDER = "fulfillment-providers"


class MedusaAdminEndpoint(Enum):
    CUSTOMERS = "/admin/customers"
    PRODUCTS = "/admin/products"
    ORDERS = "/admin/orders"
    REGIONS = "/admin/regions"
    SALES_CHANNELS = "/admin/sales-channels"
    SHIPPING_PROFILES = "/admin/shipping-profiles"


RANDOM_SEED = 42

CATEGORIES_FILENAME = "categories.json"
COLLECTIONS_FILENAME = "collections.json"
PRODUCTS_FILENAME = "products.json"
CUSTOMERS_FILENAME = "customers.json"
CUSTOMER_GROUPS_FILENAME = "customer_groups.json"
ORDERS_FILENAME = "orders.json"
TAGS_FILENAME = "tags.json"
TYPES_FILENAME = "types.json"
PROMOTIONS_FILENAME = "promotions.json"
CAMPAIGNS_FILENAME = "campaigns.json"
PRICE_LISTS_FILENAME = "price_lists.json"
SALES_CHANNELS_FILENAME = "sales_channels.json"

CATEGORIES_FILEPATH = settings.DATA_PATH / CATEGORIES_FILENAME
COLLECTIONS_FILEPATH = settings.DATA_PATH / COLLECTIONS_FILENAME
PRODUCTS_FILEPATH = settings.DATA_PATH / PRODUCTS_FILENAME
CUSTOMERS_FILEPATH = settings.DATA_PATH / CUSTOMERS_FILENAME
CUSTOMER_GROUPS_FILEPATH = settings.DATA_PATH / CUSTOMER_GROUPS_FILENAME
ORDERS_FILEPATH = settings.DATA_PATH / ORDERS_FILENAME
TAGS_FILEPATH = settings.DATA_PATH / TAGS_FILENAME
TYPES_FILEPATH = settings.DATA_PATH / TYPES_FILENAME
PROMOTIONS_FILEPATH = settings.DATA_PATH / PROMOTIONS_FILENAME
CAMPAIGNS_FILEPATH = settings.DATA_PATH / CAMPAIGNS_FILENAME
PRICE_LISTS_FILEPATH = settings.DATA_PATH / PRICE_LISTS_FILENAME
SALES_CHANNELS_FILEPATH = settings.DATA_PATH / SALES_CHANNELS_FILENAME
CUSTOMER_GROUPS_FILEPATH = settings.DATA_PATH / CUSTOMER_GROUPS_FILENAME

DEFAULT_CUSTOMERS_COUNT = 1000
DEFAULT_CUSTOMER_GROUPS_COUNT = 4
DEFAULT_PRODUCTS_COUNT = 400
DEFAULT_CATEGORIES_COUNT = 30
DEFAULT_COLLECTIONS_COUNT = 25
DEFAULT_TYPES_COUNT = 40
DEFAULT_TAGS_COUNT = 80
DEFAULT_PROMOTIONS_COUNT = 30
DEFAULT_CAMPAIGNS_COUNT = 20
DEFAULT_PRICE_LISTS_COUNT = 10

CUSTOMERS_BATCH_SIZE = 25
CUSTOMER_GROUPS_BATCH_SIZE = 2
PRODUCTS_BATCH_SIZE = 10
CATEGORIES_BATCH_SIZE = 10
COLLECTIONS_BATCH_SIZE = 5
TYPES_BATCH_SIZE = 10
TAGS_BATCH_SIZE = 10
PROMOTIONS_BATCH_SIZE = 5
CAMPAIGNS_BATCH_SIZE = 10
PRICE_LISTS_BATCH_SIZE = 3
MAPPING_BATCH_SIZE = 20

INCLUDE_PERSONAL_INFO_RATIO = 0.75
INCLUDE_COMPANY_RATIO = 0.45

PRICE_LIST_CONFIGS = [
    {
        "channel_name": "Official Website",
        "price_list_name": "Standard Retail Pricing",
        "description": "Regular pricing for direct-to-consumer online sales with full retail margins",
        "discount_percentage": 0,
        "type": "sale",
        "status": "active",
    },
    {
        "channel_name": "Instagram Shop",
        "price_list_name": "Social Media Flash Sale",
        "description": "Limited-time promotional pricing for Instagram followers and social engagement campaigns",
        "discount_percentage": 10,
        "type": "sale",
        "status": "active",
    },
    {
        "channel_name": "Department Store Counter",
        "price_list_name": "Wholesale Partner Pricing",
        "description": "Bulk order pricing for authorized retail partners and department store partnerships",
        "discount_percentage": 15,
        "type": "sale",
        "status": "active",
    },
    {
        "channel_name": "Seasonal Pop-up Store",
        "price_list_name": "End of Season Clearance",
        "description": "Aggressive markdown pricing for seasonal inventory liquidation and pop-up events",
        "discount_percentage": 25,
        "type": "sale",
        "status": "active",
    },
    {
        "channel_name": "Amazon Marketplace",
        "price_list_name": "Marketplace Competitive Pricing",
        "description": "Platform-optimized pricing to remain competitive on Amazon with fee adjustments",
        "discount_percentage": 12,
        "type": "sale",
        "status": "active",
    },
    {
        "channel_name": "Walmart Marketplace",
        "price_list_name": "Value Retailer Discount",
        "description": "Everyday low pricing strategy aligned with value-focused retailer expectations",
        "discount_percentage": 8,
        "type": "sale",
        "status": "active",
    },
    {
        "channel_name": "TikTok Shop",
        "price_list_name": "Viral Trend Promotion",
        "description": "Influencer collaboration pricing for trending products and live shopping events",
        "discount_percentage": 20,
        "type": "sale",
        "status": "active",
    },
]

REGIONS_DATA = [
    {
        "name": "United States",
        "countries": [],
        "currency_code": "USD",
        "payment_providers": ["pp_system_default"],
        "automatic_taxes": True,
        "is_tax_inclusive": False,
    }
]

MIN_RESERVATIONS = 15
MAX_RESERVATIONS = 40
QUANTITY_PERCENTAGE = 0.10

RETURN_REASONS_DATA = [
    {"value": "too_small", "label": "Too Small", "description": "The item runs smaller than expected and does not fit properly."},
    {"value": "too_large", "label": "Too Large", "description": "The item runs larger than expected and does not fit properly."},
    {"value": "poor_fit", "label": "Poor Fit", "description": "The item doesn't fit body shape or style properly despite being the correct size."},
    {"value": "defective_or_damaged", "label": "Defective or Damaged", "description": "The product has manufacturing defects or arrived damaged during shipping."},
    {"value": "not_as_described", "label": "Not as Described", "description": "The color, material, or style does not match the product description or photos."},
    {
        "value": "quality_below_expectations",
        "label": "Quality Below Expectations",
        "description": "The fabric quality, stitching, or overall construction is below expected standards.",
    },
    {"value": "changed_mind", "label": "Changed Mind", "description": "Customer decided they no longer want the product after receiving it."},
    {"value": "wrong_item_received", "label": "Wrong Item Received", "description": "Received a different product than what was ordered due to fulfillment error."},
    {"value": "wrong_size_color", "label": "Wrong Size or Color", "description": "Customer accidentally ordered the incorrect size or color."},
    {"value": "better_price_found", "label": "Better Price Found", "description": "Customer found the same item at a lower price elsewhere or a sale occurred."},
]

SALES_CHANNELS_DATA = [
    {
        "name": "Official Website",
        "description": "Primary e-commerce platform offering the complete collection of apparel, footwear, and accessories with exclusive online-only items.",
        "is_disabled": False,
    },
    {
        "name": "Instagram Shop",
        "description": "Shoppable social media storefront allowing customers to purchase trending fashion pieces directly from styled Instagram posts and stories.",
        "is_disabled": False,
    },
    {
        "name": "Department Store Counter",
        "description": "Dedicated retail space within major department stores showcasing curated seasonal collections and providing in-person styling assistance.",
        "is_disabled": False,
    },
    {
        "name": "Seasonal Pop-up Store",
        "description": "Temporary retail locations in premium shopping districts featuring limited edition collections and exclusive fashion drops.",
        "is_disabled": True,
    },
    {
        "name": "Amazon Marketplace",
        "description": "E-commerce platform enabling brands to sell products directly to Amazon's vast customer base, leveraging Prime shipping, global reach, and robust fulfillment options.",  # noqa: E501
        "is_disabled": False,
    },
    {
        "name": "Walmart Marketplace",
        "description": "Online storefront on Walmart's platform, offering wide product visibility to millions of shoppers with streamlined order fulfillment and competitive pricing.",
        "is_disabled": False,
    },
    {
        "name": "TikTok Shop",
        "description": "Shoppable fashion content platform where customers can purchase trending apparel directly through TikTok videos and livestreams.",
        "is_disabled": False,
    },
]

SHIPPING_PROFILES_DATA = [
    {"name": "Standard Shipping", "type": "default"},
    {"name": "Express Delivery", "type": "express"},
    {"name": "International Standard", "type": "international"},
    {"name": "International Express", "type": "international"},
    {"name": "Store Pickup", "type": "local"},
    {"name": "Same Day Delivery", "type": "express"},
    {"name": "Gift Wrapping Service", "type": "gift"},
    {"name": "Returns & Exchanges", "type": "return"},
]

STOCK_LOCATIONS_DATA = [
    {
        "name": "Trendspire",
        "address": {
            "address_1": "123 Fashion Avenue",
            "address_2": "Suite 402",
            "country_code": "us",
            "city": "New York",
            "company": "Trendspire Inc.",
            "phone": "+1 (212) 555-0199",
            "postal_code": "10018",
            "province": "New York",
        },
    }
]

SALES_CHANNELS = [
    "Official Website",
    "Instagram Shop",
    "Department Store Counter",
    "Amazon Marketplace",
    "Walmart Marketplace",
    "Tiktok Shop",
]

US_ADDRESS_TEMPLATES = {
    "east_coast": {
        "cities": ["New York", "Boston", "Philadelphia", "Washington", "Baltimore", "Miami", "Atlanta", "Charlotte"],
        "states": ["NY", "MA", "PA", "DC", "MD", "FL", "GA", "NC"],
    },
    "west_coast": {
        "cities": ["Los Angeles", "San Francisco", "San Diego", "Seattle", "Portland", "Las Vegas", "Phoenix", "Denver"],
        "states": ["CA", "CA", "CA", "WA", "OR", "NV", "AZ", "CO"],
    },
    "central": {
        "cities": ["Chicago", "Houston", "Dallas", "Austin", "San Antonio", "Detroit", "Minneapolis", "Milwaukee"],
        "states": ["IL", "TX", "TX", "TX", "TX", "MI", "MN", "WI"],
    },
}

PROMOTION_TYPES = [
    {
        "name": "standard_fixed_items",
        "type": "standard",
        "description": "Fixed dollar discount on items with campaign",
        "target_type": "items",
        "allocation": "each",
        "value_type": "fixed",
        "needs_campaign": True,
        "needs_currency": True,
    },
    {
        "name": "standard_fixed_order",
        "type": "standard",
        "description": "Fixed dollar discount on entire order",
        "target_type": "order",
        "allocation": "across",
        "value_type": "fixed",
        "needs_campaign": False,
        "needs_currency": True,
    },
    {
        "name": "standard_percentage_items",
        "type": "standard",
        "description": "Percentage discount on items",
        "target_type": "items",
        "allocation": "each",
        "value_type": "percentage",
        "needs_campaign": True,
        "needs_currency": False,
    },
    {
        "name": "standard_automatic_order",
        "type": "standard",
        "description": "Automatic percentage discount on order",
        "target_type": "order",
        "allocation": "across",
        "value_type": "percentage",
        "needs_campaign": True,
        "needs_currency": True,
        "is_automatic": True,
    },
    {
        "name": "buyget",
        "type": "buyget",
        "description": "Buy X Get Y promotion",
        "target_type": "items",
        "allocation": "each",
        "value_type": "percentage",
        "needs_campaign": True,
        "needs_currency": False,
        "is_buyget": True,
    },
    {
        "name": "standard_shipping",
        "type": "standard",
        "description": "Percentage discount on shipping",
        "target_type": "shipping_methods",
        "allocation": "across",
        "value_type": "percentage",
        "needs_campaign": True,
        "needs_currency": False,
    },
]

MAX_PRODUCTS_PER_BATCH = 7
SALES_CHANNEL_PROBABILITY = 0.75
MAX_RETRIES = 3
RECENT_PRODUCTS_CONTEXT_LIMIT = 30
ESTIMATED_TOKENS_PER_PRODUCT = 1000
MAX_API_TOKENS = 7000

MATERIAL_KEYWORDS = {
    "cotton": ["cotton", "tee", "t-shirt", "tank", "basic"],
    "denim": ["jean", "denim", "trucker"],
    "wool": ["wool", "knit", "cardigan"],
    "merino": ["merino"],
    "cashmere": ["cashmere", "luxury"],
    "linen": ["linen", "summer", "resort"],
    "silk": ["silk", "satin", "elegant"],
    "polyester": ["athletic", "performance", "windbreaker", "track"],
    "leather": ["leather", "moto", "biker"],
    "nylon": ["nylon", "rain", "packable"],
    "fleece": ["fleece", "cozy"],
    "corduroy": ["corduroy"],
    "canvas": ["canvas", "utility"],
}

TYPE_MATERIAL_MAP = {
    "t-shirt": "cotton",
    "tank": "cotton",
    "shirt": "cotton",
    "blouse": "polyester",
    "sweater": "wool",
    "cardigan": "wool",
    "hoodie": "cotton-fleece",
    "dress": "polyester",
    "jeans": "denim",
    "pants": "cotton-twill",
    "jacket": "polyester",
    "coat": "wool",
}

SIZE_MULTIPLIERS = {
    "xxs": 0.85,
    "xs": 0.90,
    "s": 0.95,
    "m": 1.00,
    "l": 1.05,
    "xl": 1.10,
    "xxl": 1.15,
    "2xl": 1.15,
    "3xl": 1.20,
}

PRODUCT_TYPE_DIMENSIONS = {
    "t-shirt": {"length": 30, "width": 25, "height": 3, "weight": 230},
    "shirt": {"length": 32, "width": 28, "height": 4, "weight": 280},
    "sweater": {"length": 35, "width": 30, "height": 6, "weight": 450},
    "pants": {"length": 40, "width": 32, "height": 6, "weight": 550},
    "jacket": {"length": 45, "width": 38, "height": 8, "weight": 800},
    "dress": {"length": 48, "width": 32, "height": 5, "weight": 400},
    "default": {"length": 32, "width": 28, "height": 4, "weight": 300},
}

HS_CODE_MAP = {
    "t-shirt": "610910",
    "shirt": "620520",
    "sweater": "611020",
    "pants": "620342",
    "jacket": "620193",
    "dress": "620443",
    "default": "610910",
}

KEYWORD_EXTRACT_FIELDS = ["name", "title", "description", "handle"]
MIN_KEYWORD_LENGTH = 2
RELEVANT_TYPES_SAMPLE_SIZE = 8
RELEVANT_COLLECTIONS_SAMPLE_SIZE = 3
RELEVANT_TAGS_SAMPLE_SIZE = 12
RELEVANT_TYPES_LIMIT = 10
RELEVANT_TAGS_LIMIT = 15

REQUIRED_VARIANT_ATTRIBUTES = ["material", "hs_code", "origin_country", "length", "width", "height", "weight", "mid_code"]
DEFAULT_ORIGIN_COUNTRY = "us"
DEFAULT_SHIPPING_PROFILE = "Standard Shipping"
DEFAULT_PRODUCT_TYPE = "Apparel"
DEFAULT_CATEGORY_NAME = "General Clothing"


TAX_REGIONS_DATA = [
    {
        "country_code": "us",
        "default_tax_rate": {"name": "Federal sales tax", "rate": 7, "code": "PC040100"},
        "provider_id": "tp_system",
    }
]
