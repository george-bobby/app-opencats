from apps.spree.config.settings import settings


STATES_FILE = settings.DATA_PATH.parent / "data" / "states.json"
GENERATED_DATA_PATH = settings.DATA_PATH / "generated"

## Product related paths
PRODUCTS_FILE = GENERATED_DATA_PATH / "products.json"
PROPERTIES_FILE = GENERATED_DATA_PATH / "properties.json"
PROTOTYPES_FILE = GENERATED_DATA_PATH / "prototypes.json"
OPTION_TYPES_FILE = GENERATED_DATA_PATH / "option_types.json"

## Taxonomy and navigation related paths
TAXONOMIES_FILE = GENERATED_DATA_PATH / "taxonomies.json"
TAXONS_FILE = GENERATED_DATA_PATH / "taxons.json"
MENUS_FILE = GENERATED_DATA_PATH / "menus.json"
PAGES_FILE = GENERATED_DATA_PATH / "pages.json"

## Promotion related paths
PROMOTIONS_FILE = GENERATED_DATA_PATH / "promotions.json"

## Inventory related paths
STOCK_LOCATIONS_FILE = GENERATED_DATA_PATH / "stock_locations.json"
STOCK_TRANSFERS_FILE = GENERATED_DATA_PATH / "stock_transfers.json"
STOCK_ITEMS_FILE = GENERATED_DATA_PATH / "stock_items.json"

## Media related paths
IMAGES_FILE = GENERATED_DATA_PATH / "images.json"

## Order related paths
ORDERS_FILE = GENERATED_DATA_PATH / "orders.json"
LINE_ITEMS_FILE = GENERATED_DATA_PATH / "line_items.json"
SHIPMENTS_FILE = GENERATED_DATA_PATH / "shipments.json"
SHIPPING_RATES_FILE = GENERATED_DATA_PATH / "shipping_rates.json"
SHIPPING_METHODS_FILE = GENERATED_DATA_PATH / "shipping_methods.json"
TAX_RATES_FILE = GENERATED_DATA_PATH / "tax_rates.json"
STATE_CHANGES_FILE = GENERATED_DATA_PATH / "state_changes.json"
USERS_FILE = GENERATED_DATA_PATH / "users.json"
ADDRESSES_FILE = GENERATED_DATA_PATH / "addresses.json"
PRODUCTS_FILE = GENERATED_DATA_PATH / "products.json"
INVENTORY_UNITS_FILE = GENERATED_DATA_PATH / "inventory_units.json"


RETURN_REASONS_FILE = GENERATED_DATA_PATH / "return_authorization_reasons.json"
RETURN_AUTHORIZATIONS_FILE = GENERATED_DATA_PATH / "return_authorizations.json"
CUSTOMER_RETURNS_FILE = GENERATED_DATA_PATH / "customer_returns.json"
REIMBURSEMENTS_FILE = GENERATED_DATA_PATH / "reimbursements.json"

# Constants
SHIPPING_CATEGORIES = [
    {"id": "1", "name": "Default"},
    {"id": "2", "name": "Digital"},
]

SHIPPING_ZONES = [
    {"id": 1, "name": "EU_VAT"},
    {"id": 2, "name": "UK_VAT"},
    {"id": 3, "name": "NORTH AMERICA"},
    {"id": 4, "name": "SOUTH AMERICA"},
    {"id": 5, "name": "MIDDLE EAST"},
    {"id": 6, "name": "ASIA"},
]

ROLES = ["customer_support", "fulfillment_staff"]

PAYMENT_PROVIDERS = [
    # "Spree::Gateway::AuthorizeNet",
    # "Spree::Gateway::AuthorizeNetCim",
    # "Spree::Gateway::BalancedGateway",
    # "Spree::Gateway::Banwire",
    # "Spree::Gateway::Beanstream",
    # "Spree::Gateway::Bogus",
    "Spree::Gateway::BogusSimple",  # Only this gateway is enabled for so that the checkout can be tested
    # "Spree::Gateway::BraintreeGateway",
    # "Spree::Gateway::CardSave",
    # "Spree::Gateway::CyberSource",
    # "Spree::Gateway::DataCash",
    # "Spree::Gateway::Epay",
    # "Spree::Gateway::Eway",
    # "Spree::Gateway::EwayRapid",
    # "Spree::Gateway::Maxipago",
    # "Spree::Gateway::Migs",
    # "Spree::Gateway::Moneris",
    # "Spree::Gateway::PayJunction",
    # "Spree::Gateway::PayPalGateway",
    # "Spree::Gateway::PayflowPro",
    # "Spree::Gateway::Paymill",
    # "Spree::Gateway::PinGateway",
    # "Spree::Gateway::Quickpay",
    # "Spree::Gateway::SagePay",
    # "Spree::Gateway::SecurePayAU",
    # "Spree::Gateway::SpreedlyCoreGateway",
    # "Spree::Gateway::StripeAchGateway",
    # "Spree::Gateway::StripeApplePayGateway",
    # "Spree::Gateway::StripeElementsGateway",
    # "Spree::Gateway::StripeGateway",
    # "Spree::Gateway::UsaEpayTransaction",
    # "Spree::Gateway::Worldpay",
    "Spree::PaymentMethod::Check",
    "Spree::PaymentMethod::StoreCredit",
]

US_COUNTRY_ID = 224

IMAGE_TAG_PLACEHOLDER = "!IMG!"


SPREE_CMS_HOMEPAGE = "Spree::Cms::Pages::Homepage"
SPREE_CMS_FEATUREPAGE = "Spree::Cms::Pages::FeaturePage"
SPREE_CMS_STANDARDPAGE = "Spree::Cms::Pages::StandardPage"

PAGE_TYPES = [
    SPREE_CMS_HOMEPAGE,
    SPREE_CMS_FEATUREPAGE,
    SPREE_CMS_STANDARDPAGE,
]

# Section types
SPREE_SECTION_HERO_IMAGE = "Spree::Cms::Sections::HeroImage"
SPREE_SECTION_FEATURED_ARTICLE = "Spree::Cms::Sections::FeaturedArticle"
SPREE_SECTION_PRODUCT_CAROUSEL = "Spree::Cms::Sections::ProductCarousel"
SPREE_SECTION_IMAGE_GALLERY = "Spree::Cms::Sections::ImageGallery"
SPREE_SECTION_SIDE_BY_SIDE_IMAGES = "Spree::Cms::Sections::SideBySideImages"
SPREE_SECTION_RICH_TEXT = "Spree::Cms::Sections::RichTextContent"

SECTION_TYPES = [
    SPREE_SECTION_HERO_IMAGE,
    SPREE_SECTION_PRODUCT_CAROUSEL,
    SPREE_SECTION_IMAGE_GALLERY,
    SPREE_SECTION_RICH_TEXT,
    SPREE_SECTION_FEATURED_ARTICLE,
    SPREE_SECTION_SIDE_BY_SIDE_IMAGES,
]

# Resource types
SPREE_RESOURCE_TAXON = "Spree::Taxon"
SPREE_RESOURCE_PRODUCT = "Spree::Product"

# Section fit types
SECTION_FIT_SCREEN = "Screen"
SECTION_FIT_CONTAINER = "Container"

REIMBURSEMENT_TYPES = [
    {
        "id": 1,
        "name": "Original Payment Method Refund",
        "active": True,
        "mutable": True,
        "created_at": "2025-08-22 10:54:53.293134",
        "updated_at": "2025-08-22 10:54:53.293134",
        "type": "Spree::ReimbursementType::OriginalPayment",
    },
    {
        "id": 2,
        "name": "Store Credit Compensation",
        "active": True,
        "mutable": True,
        "created_at": "2025-08-22 10:54:53.294480",
        "updated_at": "2025-08-22 10:54:53.294480",
        "type": "Spree::ReimbursementType::StoreCredit",
    },
    {
        "id": 3,
        "name": "Product Exchange Resolution",
        "active": True,
        "mutable": True,
        "created_at": "2025-08-22 10:54:53.295601",
        "updated_at": "2025-08-22 10:54:53.295601",
        "type": "Spree::ReimbursementType::Exchange",
    },
    {
        "id": 4,
        "name": "Account Credit Reimbursement",
        "active": True,
        "mutable": True,
        "created_at": "2025-08-22 10:54:53.296667",
        "updated_at": "2025-08-22 10:54:53.296667",
        "type": "Spree::ReimbursementType::Credit",
    },
    {
        "id": 5,
        "name": "Instant Store Credit Refund",
        "active": True,
        "mutable": True,
        "created_at": "2025-08-22 10:54:53.297935",
        "updated_at": "2025-08-22 10:54:53.297935",
        "type": "Spree::ReimbursementType::StoreCredit",
    },
]
