from enum import Enum


class StockModelName(Enum):
    STOCK_PICKING = "stock.picking"
    STOCK_PICKING_TYPE = "stock.picking.type"
    STOCK_MOVE = "stock.move"
    STOCK_WAREHOUSE = "stock.warehouse"
    STOCK_LOCATION = "stock.location"
    STOCK_QUANT = "stock.quant"
    STOCK_ROUTE = "stock.route"


class MrpModelName(Enum):
    MRP_WORK_CENTER = "mrp.workcenter"
    MRP_ORDER = "mrp.production"
    MRP_BOM = "mrp.bom"
    MRP_UNBUILD_ORDER = "mrp.unbuild"
    MRP_CAPACITY = "mrp.workcenter.capacity"
    MRP_OPERATION = "mrp.routing.workcenter"
    MRP_BOM_LINE = "mrp.bom.line"


class ResModelName(Enum):
    RES_CONFIG_SETTINGS = "res.config.settings"
    RES_GROUP = "res.groups"
    RES_USERS = "res.users"
    RES_PARTNER = "res.partner"
    RES_COMPANY = "res.company"
    RES_INDUSTRY = "res.partner.industry"
    RES_CATEGORY = "res.partner.category"
    RES_COUNTRY = "res.country"
    RES_COUNTRY_STATE = "res.country.state"


class AccountModelName(Enum):
    ACCOUNT_JOURNAL = "account.journal"
    ACCOUNT_PAYMENT_TERM = "account.payment.term"
    ACCOUNT_TAX = "account.tax"
    ACCOUNT_INVOICE = "account.move"


class ProductModelName(Enum):
    PRODUCT_TEMPLATE = "product.template"
    PRODUCT_PRODUCT = "product.product"
    PRODUCT_CATEGORY = "product.category"
    PRODUCT_ATTRIBUTE = "product.attribute"
    PRODUCT_ATTRIBUTE_VALUE = "product.attribute.value"
    PRODUCT_TAG = "product.tag"
    PRODUCT_PRICELIST = "product.pricelist"
    PRODUCT_PRICELIST_ITEM = "product.pricelist.item"


DEFAULT_ADDRESS_ID = 1
DEFAULT_COUNTRY_ID = 233  # United States
DEFAULT_ADMIN_USER_ID = 2
DEFAULT_EMPLOYEE_ID = 1

COMPANY_INDUSTRIES = [
    "Agriculture",
    "Manufacturing",
    "Technology",
    "Healthcare",
    "Finance",
    "Retail",
    "Education",
    "Real Estate",
    "Construction",
    "Hospitality",
    "Transportation",
    "Energy",
    "Telecommunications",
    "Media",
    "Consulting",
    "Automotive",
    "Aerospace",
    "Pharmaceutical",
    "Biotechnology",
    "Chemical",
]

CONTACT_TAGS = [
    "VIP",
    "Prospect",
    "Partner",
    "Investor",
    "Alumni",
    "Newsletter",
    "Event Attendee",
    "Referral",
    "Community Member",
    "Social Media",
    "Industry Expert",
    "Influencer",
    "Brand Ambassador",
    "Advocate",
    "Volunteer",
    "Donor",
    "Sponsor",
    "Consultant",
    "Customer",
]

SCRAP_REASONS = [
    "Damaged during shipping",
    "Defective",
    "Expired",
    "Obsolete",
    "Overstocked",
    "Returned and defective",
    "Damaged packaging",
    "Scratched lenses",
    "Defective stitching",
    "Broken",
    "Unsellable",
    "Out of season",
]

PRODUCT_CATEGORIES = [
    "Home Essentials",
    "Electronics",
    "Apparel",
    "Health & Beauty",
    "Office Supplies",
    "Gift Sets & Bundles",
]

COMPONENT_CATEGORIES = [
    {"name": "Raw Materials - Textiles", "parent_name": "Manufacturing"},
    {"name": "Raw Materials - Chemicals", "parent_name": "Manufacturing"},
    {"name": "Raw Materials - Metals", "parent_name": "Manufacturing"},
    {"name": "Subassemblies - Electronics", "parent_name": "Manufacturing"},
    {"name": "Subassemblies - Packaging", "parent_name": "Manufacturing"},
    {"name": "Raw Materials - Plastics", "parent_name": "Manufacturing"},
    {"name": "Raw Materials - Paper & Cardboard", "parent_name": "Manufacturing"},
    {"name": "Components - Hardware", "parent_name": "Manufacturing"},
    {"name": "Components - Adhesives & Sealants", "parent_name": "Manufacturing"},
    {"name": "Subassemblies - Mechanical", "parent_name": "Manufacturing"},
    {"name": "Raw Materials - Fabric Dyes", "parent_name": "Manufacturing"},
    {"name": "Raw Materials - Fragrances & Oils", "parent_name": "Manufacturing"},
    {"name": "Components - Electrical", "parent_name": "Manufacturing"},
    {"name": "Packaging & Shipping Materials", "parent_name": "Expenses"},
    {"name": "Waste & Scrap Materials", "parent_name": "Expenses"},
]
