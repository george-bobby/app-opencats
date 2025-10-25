import json
from datetime import datetime
from pathlib import Path

from faker import Faker
from pydantic import BaseModel, Field

from apps.spree.config.settings import settings
from apps.spree.utils import constants
from apps.spree.utils.ai import instructor_client
from apps.spree.utils.constants import MENUS_FILE, PAGES_FILE, PRODUCTS_FILE, TAXONOMIES_FILE, TAXONS_FILE
from apps.spree.utils.database import db_client
from common.logger import Logger


fake = Faker()
logger = Logger()

# Default menus structure
DEFAULT_MENUS = [
    {
        "name": "Header Navigation",
        "location": "header",
        "locale": "en",
    },
    {
        "name": "Footer Navigation",
        "location": "footer",
        "locale": "en",
    },
]


class MenuItem(BaseModel):
    """Individual menu item model."""

    id: int = Field(description="Unique identifier for the menu item")  # noqa: A003, RUF100
    name: str = Field(description="Display name of the menu item")
    subtitle: str | None = Field(description="Optional subtitle for the menu item", default=None)
    destination: str | None = Field(description="URL or path destination. None when linked to a resource.", default=None)
    new_window: bool = Field(description="Whether to open in new window", default=False)
    item_type: str = Field(description="Type of menu item", default="Link")
    linked_resource_type: str = Field(description="Type of linked resource", default="Spree::Linkable::Uri")
    linked_resource_id: int | None = Field(description="ID of linked resource", default=None)
    code: str | None = Field(description="Optional code for the menu item", default=None)
    parent_id: int | None = Field(description="ID of parent menu item", default=None)
    parent_name: str | None = Field(description="Name of parent menu item", default=None)
    lft: int | None = Field(description="Left value for nested set model", default=None)
    rgt: int | None = Field(description="Right value for nested set model", default=None)
    depth: int = Field(description="Depth in menu hierarchy", default=0)
    menu_id: int = Field(description="ID of the menu this item belongs to")


class MenuItemForGeneration(BaseModel):
    """Menu item model for AI generation (without ID)."""

    name: str = Field(description="Display name of the menu item")
    subtitle: str | None = Field(description="Optional subtitle for the menu item", default=None)
    destination: str | None = Field(description="URL or path destination. None when linked to a resource.", default=None)
    new_window: bool = Field(description="Whether to open in new window", default=False)
    item_type: str = Field(description="Type of menu item", default="Link")
    linked_resource_type: str = Field(description="Type of linked resource", default="Spree::Linkable::Uri")
    linked_resource_id: int | None = Field(description="ID of linked resource", default=None)
    code: str | None = Field(description="Optional code for the menu item", default=None)
    parent_name: str | None = Field(description="Name of parent menu item", default=None)
    depth: int = Field(description="Depth in menu hierarchy", default=0)
    menu_location: str = Field(description="Location of the menu (header/footer)")


class Menu(BaseModel):
    """Individual menu model."""

    id: int = Field(description="Unique identifier for the menu")  # noqa: A003, RUF100
    name: str = Field(description="Name of the menu")
    location: str = Field(description="Location of the menu (header, footer)")
    locale: str = Field(description="Locale for the menu")
    store_id: int = Field(description="Store ID", default=1)
    menu_items: list[MenuItem] = Field(description="Menu items in this menu", default_factory=list)


class MenuForGeneration(BaseModel):
    """Menu model for AI generation (without ID)."""

    name: str = Field(description="Name of the menu")
    location: str = Field(description="Location of the menu (header, footer)")
    locale: str = Field(description="Locale for the menu")
    store_id: int = Field(description="Store ID", default=1)


class MenuItemsResponse(BaseModel):
    """Response format for generated menu items."""

    menu_items: list[MenuItemForGeneration]


class MenusResponse(BaseModel):
    """Response format for generated menus."""

    menus: list[MenuForGeneration]


def load_existing_data() -> dict:
    """Load existing taxonomies, taxons, products, and pages data from JSON files."""
    data = {"taxonomies": [], "taxons": [], "products": [], "pages": [], "valid_routes": [], "page_titles": []}

    # Load taxonomies
    if TAXONOMIES_FILE.exists():
        try:
            with Path.open(TAXONOMIES_FILE, encoding="utf-8") as f:
                taxonomies_data = json.load(f)
            data["taxonomies"] = taxonomies_data.get("taxonomies", [])
        except Exception as e:
            logger.warning(f"Could not load taxonomies: {e}")

    # Load taxons and build valid routes
    if TAXONS_FILE.exists():
        try:
            with Path.open(TAXONS_FILE, encoding="utf-8") as f:
                taxons_data = json.load(f)
            data["taxons"] = taxons_data.get("taxons", [])

            # Build valid taxon routes based on Spree permalink logic
            valid_routes = []
            for taxon in data["taxons"]:
                taxon_name = taxon["name"]
                parent_name = taxon.get("parent_name")

                # Create permalink like Spree does
                if parent_name is None:
                    # Top-level taxon (taxonomy root)
                    permalink = taxon_name.lower().replace(" ", "-").replace("&", "and")
                else:
                    # Child taxon
                    parent_permalink = parent_name.lower().replace(" ", "-").replace("&", "and")
                    child_permalink = taxon_name.lower().replace(" ", "-").replace("&", "and")
                    permalink = f"{parent_permalink}/{child_permalink}"

                valid_routes.append(
                    {"name": taxon_name, "route": f"/t/{permalink}", "description": taxon.get("description", ""), "parent": parent_name, "type": "taxon", "taxon_id": taxon.get("id")}
                )

            data["valid_routes"] = valid_routes
        except Exception as e:
            logger.warning(f"Could not load taxons: {e}")

    # Load products and build product routes
    if PRODUCTS_FILE.exists():
        try:
            with Path.open(PRODUCTS_FILE, encoding="utf-8") as f:
                products_data = json.load(f)
            products = products_data.get("products", [])
            data["products"] = products[:5]  # Just first 5 for context

            # Build valid product routes based on Spree product slug logic
            for product in products:
                product_name = product.get("name", "")
                product_sku = product.get("sku", "")
                product_id = product.get("id")

                if product_sku and product_id:
                    # In Spree, product slug is typically the SKU in lowercase
                    product_slug = product_sku.lower()
                    product_route = f"/products/{product_slug}"

                    data["valid_routes"].append(
                        {
                            "name": product_name,
                            "route": product_route,
                            "description": f"Product: {product_name}",
                            "parent": None,
                            "type": "product",
                            "product_id": product_id,
                            "sku": product_sku,
                        }
                    )

        except Exception as e:
            logger.warning(f"Could not load products: {e}")

    # Load CMS pages and build page routes
    if PAGES_FILE.exists():
        try:
            with Path.open(PAGES_FILE, encoding="utf-8") as f:
                pages_data = json.load(f)
            pages = pages_data.get("pages", [])
            data["pages"] = pages[:5]  # Just first 5 for context

            # Extract page titles and IDs for all pages to use as context
            for page in pages:
                page_title = page.get("title", "")
                page_id = page.get("id")
                page_slug = page.get("slug", "")
                page_type = page.get("type", "")

                # Add to page_titles list for context
                data["page_titles"].append({"id": page_id, "title": page_title, "slug": page_slug, "type": page_type})

            # Build valid page routes for Feature and Standard pages
            for page in pages:
                page_title = page.get("title", "")
                page_slug = page.get("slug", "")
                page_type = page.get("type", "")
                page_id = page.get("id")

                # Only include Feature and Standard pages (not Homepage)
                if page_slug and page_id and page_type in ["Spree::Cms::Pages::FeaturePage", "Spree::Cms::Pages::StandardPage"]:
                    page_route = f"/{page_slug}"

                    data["valid_routes"].append(
                        {
                            "name": page_title,
                            "route": page_route,
                            "description": f"CMS Page: {page_title}",
                            "parent": None,
                            "type": "cms_page",
                            "page_id": page_id,
                            "page_type": page_type,
                            "slug": page_slug,
                        }
                    )

        except Exception as e:
            logger.warning(f"Could not load CMS pages: {e}")

    return data


def validate_and_fix_route(destination: str, valid_routes: list[dict]) -> str:
    """Validate a route and fix it if invalid."""

    # Always valid routes in Spree
    valid_base_routes = ["/", "/products", "/about", "/contact"]

    if destination in valid_base_routes:
        return destination

    # Check if it's a valid route (taxon or product)
    if any(route["route"] == destination for route in valid_routes):
        return destination

    # Block social media URLs since they're available elsewhere
    social_domains = ["facebook.com", "instagram.com", "twitter.com", "pinterest.com", "linkedin.com", "youtube.com"]
    if destination.startswith(("http://", "https://")):
        if any(domain in destination for domain in social_domains):
            logger.warning(f"Blocked social media route '{destination}' - redirected to /about")
            return "/about"
        return destination

    # Fix common invalid patterns
    if destination.startswith("/collections/"):
        return "/products"  # Redirect collections to products

    if destination in ["/sale", "/deals", "/new-arrivals"]:
        return "/products"  # Redirect sale-type pages to products

    if destination.startswith("/page/"):
        return "/about"  # Redirect generic pages to about

    # If route looks like a taxon but doesn't match, try to find closest match
    if destination.startswith("/t/"):
        route_name = destination.replace("/t/", "").replace("-", " ").title()
        # Try to find a similar taxon
        for route in valid_routes:
            if route.get("type") == "taxon" and (route_name.lower() in route["name"].lower() or route["name"].lower() in route_name.lower()):
                return route["route"]

    # If route looks like a product but doesn't match, try to find closest match
    if destination.startswith("/products/"):
        product_slug = destination.replace("/products/", "")
        # Try to find a product with similar SKU or name
        for route in valid_routes:
            if route.get("type") == "product" and (
                product_slug.lower() == route.get("sku", "").lower()
                or product_slug.lower() in route["name"].lower().replace(" ", "-")
                or route["name"].lower().replace(" ", "-") in product_slug.lower()
            ):
                return route["route"]

        # If no specific product found, redirect to products listing
        logger.warning(f"Invalid product route '{destination}' redirected to /products")
        return "/products"

    # Check for CMS page routes
    for route in valid_routes:
        if route.get("type") == "cms_page" and route["route"] == destination:
            return route["route"]

    # Try to find similar CMS page by slug
    if destination.startswith("/") and not destination.startswith(("/t/", "/products/")):
        page_slug = destination.lstrip("/")

        # Try fuzzy match through valid_routes
        for route in valid_routes:
            if route.get("type") == "cms_page" and (
                page_slug.lower() == route.get("slug", "").lower()
                or page_slug.lower() in route["name"].lower().replace(" ", "-")
                or route["name"].lower().replace(" ", "-") in page_slug.lower()
            ):
                return route["route"]

    # Last resort - redirect to products
    logger.warning(f"Invalid route '{destination}' redirected to /products")
    return "/products"


async def generate_menu_items_for_location(location: str, menu_id: int, items_count: int) -> list[dict]:
    """Generate menu items for a specific location (header/footer) using existing data context."""

    if items_count <= 0:
        return []

    logger.info(f"Generating {items_count} menu items for {location} menu using existing taxonomies and products")

    # Load existing data for context
    existing_data = load_existing_data()

    # Build simple context with main taxonomy routes and subcategories
    main_taxonomies = [t for t in existing_data["taxons"] if t.get("parent_name") is None]
    subcategories = [t for t in existing_data["taxons"] if t.get("parent_name") is not None][:8]

    # Create route info for main taxonomies
    main_taxonomy_routes = []
    for taxonomy in main_taxonomies:
        permalink = taxonomy["name"].lower().replace(" ", "-").replace("&", "and")
        main_taxonomy_routes.append(f"{taxonomy['name']}: /t/{permalink}")

    subcategory_names = [t["name"] for t in subcategories]

    # Get page information for context
    page_titles = existing_data["page_titles"]

    # Format page information for context
    page_routes = []
    for page in page_titles:
        if page["type"] in [constants.SPREE_CMS_FEATUREPAGE, constants.SPREE_CMS_STANDARDPAGE]:
            page_routes.append(f"{page['title']}: /{page['slug']}")

    main_taxonomies_text = ", ".join(main_taxonomy_routes) if main_taxonomy_routes else "Categories: /t/categories, Brands: /t/brands"
    subcategories_text = ", ".join(subcategory_names) if subcategory_names else "Dogs, Cats, Treats"
    pages_text = ", ".join(page_routes) if page_routes else "About Us: /about-us, FAQ: /faq, Shipping & Returns: /shipping-returns"

    if location == "header":
        system_prompt = f"""Create {items_count} header navigation menu items for {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.

        MAIN TAXONOMIES (include these): {main_taxonomies_text}
        SUBCATEGORIES: {subcategories_text}
        CMS PAGES (include these): {pages_text}

        Create practical header navigation including:
        - Essential pages (Home, Shop, About, Contact)  
        - Main product categories
        - Brand pages
        - CMS pages like About Us, FAQ, etc.
        - Any relevant taxonomy sections

        Use logical destinations like "/", "/products", "/about-us", "/faq", "/shipping-returns", "/t/category-name", etc."""

        user_prompt = f"""Generate exactly {items_count} header navigation items for a pet store.
        
        MUST INCLUDE main taxonomy pages: {main_taxonomies_text}
        
        Also include essential pages, CMS pages, and some subcategories:
        - CMS Pages: {pages_text}
        - Subcategories: {subcategories_text}
        
        Each item needs:
        - name: Navigation label  
        - subtitle: Optional description
        - destination: URL path (/, /products, or CMS page routes like /about-us, /faq, or taxonomy routes like /t/categories)
        - new_window: false
        - item_type: "Link"
        - linked_resource_type: "Spree::Linkable::Uri"
        - linked_resource_id: null
        - code: optional short identifier
        - parent_name: parent menu name for sub-items, null for top-level
        - depth: 0 for top-level, 1 for sub-items
        - menu_location: "header"
        
        Prioritize main taxonomy pages and CMS pages so users can browse the main Categories, Brands, Pet Types sections and important information pages."""

    else:  # footer
        system_prompt = f"""Create {items_count} footer navigation menu items for {settings.SPREE_STORE_NAME}, a {settings.DATA_THEME_SUBJECT}.

        Create useful footer navigation with:
        - Company info links from CMS pages
        - Quick product access and main categories
        - Popular taxonomy sections
        - Important information pages

        MAIN TAXONOMIES: {main_taxonomies_text}
        SUBCATEGORIES: {subcategories_text}
        CMS PAGES (include these): {pages_text}

        DO NOT include social media links (they're available elsewhere).
        Focus on helpful navigation and popular product categories."""

        user_prompt = f"""Generate exactly {items_count} footer navigation items.
        
        Include:
        - CMS pages: {pages_text}
        - Product browsing (/products, main taxonomy pages)
        - Popular categories from: {subcategories_text}
        
        DO NOT include social media links.
        
        Each item needs:
        - name: Footer link label
        - subtitle: Optional description
        - destination: URL (use exact CMS page routes like /about-us, /faq, /shipping-returns, /products, /t/category-name)
        - new_window: false (all internal links)
        - item_type: "Link"
        - linked_resource_type: "Spree::Linkable::Uri"
        - linked_resource_id: null
        - code: optional identifier
        - parent_name: section name for grouped items, null for top-level
        - depth: 0 for sections, 1 for items
        - menu_location: "footer"
        
        Create useful footer navigation without social media. Group items logically under section headings."""

    try:
        menu_items_response = await instructor_client.chat.completions.create(
            model="claude-3-5-sonnet-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_model=MenuItemsResponse,
            temperature=0.3,
            max_tokens=8192,
        )

        if menu_items_response and menu_items_response.menu_items:
            # Process and validate each menu item
            menu_items = []
            fixed_routes = 0

            for item in menu_items_response.menu_items:
                item_dict = item.model_dump()
                item_dict["menu_id"] = menu_id

                # Validate and fix the destination route
                original_destination = item_dict["destination"]
                validated_destination = validate_and_fix_route(original_destination, existing_data["valid_routes"])

                if original_destination != validated_destination:
                    fixed_routes += 1

                item_dict["destination"] = validated_destination

                matching_route = next((route for route in existing_data["valid_routes"] if route["route"] == validated_destination), None)
                if matching_route and matching_route.get("type") == "cms_page":
                    # Set proper CMS page linking
                    item_dict["linked_resource_type"] = "Spree::CmsPage"
                    item_dict["linked_resource_id"] = matching_route["page_id"]
                    item_dict["destination"] = None  # CMS pages use linked_resource instead of destination

                elif matching_route and matching_route.get("type") == "taxon":
                    # Set proper taxon linking (if needed in the future)
                    item_dict["linked_resource_type"] = "Spree::Taxon"
                    item_dict["linked_resource_id"] = matching_route.get("taxon_id")

                else:
                    # Default to URI linking for other routes
                    item_dict["linked_resource_type"] = "Spree::Linkable::Uri"
                    item_dict["linked_resource_id"] = None

                menu_items.append(item_dict)

            return menu_items
        else:
            logger.error(f"Failed to parse menu items response for {location}")
            return []
    except Exception as e:
        logger.error(f"Error generating menu items for {location}: {e}")
        return []


def calculate_nested_set_values_for_menu_items(items_by_parent: dict, parent_id: int | None = None, left_value: int = 1) -> tuple[dict, int]:
    """Calculate left and right values for nested set model for menu items."""
    current_left = left_value
    lft_rgt_values = {}

    children = items_by_parent.get(parent_id, [])

    # Sort children by name for consistent ordering
    children = sorted(children, key=lambda x: x["name"])

    for child in children:
        child_id = child["id"]

        # Set left value for this node
        lft_rgt_values[child_id] = {"lft": current_left}
        current_left += 1

        # Recursively process children (if any)
        child_values, current_left = calculate_nested_set_values_for_menu_items(items_by_parent, child_id, current_left)
        lft_rgt_values.update(child_values)

        # Set right value for this node (after all children are processed)
        lft_rgt_values[child_id]["rgt"] = current_left
        current_left += 1

    return lft_rgt_values, current_left


async def generate_menus(header_items: int = 8, footer_items: int = 12) -> dict | None:
    """Generate realistic header and footer menus using AI and existing taxonomies/products as context.

    Creates both spree_menus entries and spree_menu_items with proper hierarchy:
    - Each menu gets a root container item (item_type: "Container")
    - Navigation items are children of the root container
    - Uses existing taxonomies, taxons, and products to create relevant navigation
    """

    logger.info(f"Generating menus with {header_items} header items and {footer_items} footer items...")

    try:
        # Generate the basic menu structure
        all_menu_items = []
        menus_with_ids = []
        menu_id = 1

        # Create header and footer menus
        for menu_data in DEFAULT_MENUS:
            menu = Menu(id=menu_id, name=menu_data["name"], location=menu_data["location"], locale=menu_data["locale"], store_id=1, menu_items=[])
            menus_with_ids.append(menu)

            # Generate menu items for this menu
            items_count = header_items if menu_data["location"] == "header" else footer_items
            menu_items = await generate_menu_items_for_location(menu_data["location"], menu_id, items_count)
            all_menu_items.extend(menu_items)

            menu_id += 1

        # Add incrementing IDs to all menu items
        menu_items_with_ids = []
        item_id = 1

        for item_dict in all_menu_items:
            # Convert dict to MenuItem model with ID
            menu_item = MenuItem(
                id=item_id,
                name=item_dict["name"],
                subtitle=item_dict.get("subtitle"),
                destination=item_dict["destination"],
                new_window=item_dict.get("new_window", False),
                item_type=item_dict.get("item_type", "Link"),
                linked_resource_type=item_dict.get("linked_resource_type", "Spree::Linkable::Uri"),
                linked_resource_id=item_dict.get("linked_resource_id"),
                code=item_dict.get("code"),
                parent_name=item_dict.get("parent_name"),
                depth=item_dict.get("depth", 0),
                menu_id=item_dict["menu_id"],
                lft=None,  # Will be calculated below
                rgt=None,  # Will be calculated below
            )
            menu_items_with_ids.append(menu_item)
            item_id += 1

        # Calculate nested set values for each menu separately
        logger.info("Calculating nested set values for menu items...")

        for menu in menus_with_ids:
            # Get menu items for this menu
            menu_items = [item for item in menu_items_with_ids if item.menu_id == menu.id]

            if not menu_items:
                continue

            # Build parent mapping for nested set calculation
            items_by_parent = {}

            for item in menu_items:
                if item.parent_name is None:
                    # Top-level item
                    items_by_parent[None] = [*items_by_parent.get(None, []), {"id": item.id, "name": item.name}]
                else:
                    # Find parent by name within this menu
                    parent_item = next((i for i in menu_items if i.name == item.parent_name), None)
                    if parent_item:
                        parent_id = parent_item.id
                        items_by_parent[parent_id] = [*items_by_parent.get(parent_id, []), {"id": item.id, "name": item.name}]

            # Calculate nested set values for this menu
            lft_rgt_values, _ = calculate_nested_set_values_for_menu_items(items_by_parent, parent_id=None, left_value=1)

            # Update menu items with calculated lft/rgt values
            for item in menu_items:
                if item.id in lft_rgt_values:
                    item.lft = lft_rgt_values[item.id]["lft"]
                    item.rgt = lft_rgt_values[item.id]["rgt"]

                else:
                    logger.warning(f"No nested set values calculated for menu item: {item.name} (ID:{item.id})")

            # Add items to menu
            menu.menu_items = menu_items

        # Save all menus and menu items to file
        menus_dict = {"menus": [menu.model_dump() for menu in menus_with_ids]}

        settings.DATA_PATH.mkdir(parents=True, exist_ok=True)
        MENUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with Path.open(MENUS_FILE, "w", encoding="utf-8") as f:
            json.dump(menus_dict, f, indent=2, ensure_ascii=False)

        total_items = sum(len(menu.menu_items) for menu in menus_with_ids)
        logger.succeed(f"Successfully generated and saved {len(menus_with_ids)} menus with {total_items} total menu items to {MENUS_FILE}")

        logger.succeed("Menu generation completed with route validation - all destinations are now valid Spree routes")
        return menus_dict

    except Exception as e:
        logger.error(f"Error generating menus: {e}")
        raise


async def seed_menus():
    """Seed menus and menu items into the database with proper hierarchy.

    Creates:
    1. Menu entries in spree_menus
    2. Root container items in spree_menu_items (item_type: "Container")
    3. Navigation items as children of root containers
    4. Proper nested set values for the complete hierarchy
    """

    logger.start("Inserting menus and menu items into database...")

    try:
        # Load menus from JSON file
        if not MENUS_FILE.exists():
            logger.error(f"Menus file not found at {MENUS_FILE}. Run generate command first.")
            raise FileNotFoundError("Menus file not found")

        with Path.open(MENUS_FILE, encoding="utf-8") as f:
            data = json.load(f)

        menus = data.get("menus", [])
        logger.info(f"Loaded {len(menus)} menus from {MENUS_FILE}")

        current_time = datetime.now()

        # First pass: Insert menus and their root container items
        menu_id_map = {}  # generated_id -> database_id
        root_container_map = {}  # database_menu_id -> root_container_id

        for menu in menus:
            try:
                # Check if menu already exists
                existing_menu = await db_client.fetchrow(
                    "SELECT id FROM spree_menus WHERE location = $1 AND locale = $2 AND store_id = $3", menu["location"], menu["locale"], menu["store_id"]
                )

                if existing_menu:
                    menu_id_map[menu["id"]] = existing_menu["id"]
                    # Check if root container item exists for this menu
                    existing_root = await db_client.fetchrow(
                        "SELECT id FROM spree_menu_items WHERE menu_id = $1 AND parent_id IS NULL AND item_type = $2", existing_menu["id"], "Container"
                    )
                    if existing_root:
                        root_container_map[existing_menu["id"]] = existing_root["id"]
                    continue

                # Insert menu
                menu_record = await db_client.fetchrow(
                    """
                    INSERT INTO spree_menus (name, location, locale, store_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    menu["name"],
                    menu["location"],
                    menu["locale"],
                    menu["store_id"],
                    current_time,
                    current_time,
                )

                if menu_record:
                    database_menu_id = menu_record["id"]
                    menu_id_map[menu["id"]] = database_menu_id
                    # Create root container menu item for this menu
                    root_container_record = await db_client.fetchrow(
                        """
                        INSERT INTO spree_menu_items (name, subtitle, destination, new_window, item_type,
                                                    linked_resource_type, linked_resource_id, code, parent_id,
                                                    lft, rgt, depth, menu_id, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                        RETURNING id
                        """,
                        menu["name"],  # Use menu name for the container
                        None,  # subtitle
                        None,  # destination (containers don't have destinations)
                        False,  # new_window
                        "Container",  # item_type
                        "Spree::Linkable::Uri",  # linked_resource_type
                        None,  # linked_resource_id
                        None,  # code
                        None,  # parent_id (root level)
                        1,  # lft (will be recalculated later)
                        2,  # rgt (will be recalculated later)
                        0,  # depth
                        database_menu_id,  # menu_id
                        current_time,  # created_at
                        current_time,  # updated_at
                    )

                    if root_container_record:
                        root_container_map[database_menu_id] = root_container_record["id"]

            except Exception as e:
                logger.error(f"Failed to insert menu {menu['name']}: {e}")
                continue

        # Second pass: Insert menu items
        all_menu_items = []
        for menu in menus:
            menu_items = menu.get("menu_items", [])
            # Update menu_id to database ID
            database_menu_id = menu_id_map.get(menu["id"])
            if database_menu_id:
                for item in menu_items:
                    item["database_menu_id"] = database_menu_id
                    all_menu_items.append(item)

        logger.info(f"Processing {len(all_menu_items)} menu items")

        # Build item mapping and parent relationships
        item_id_map = {}  # name -> database_id (within each menu)
        items_by_menu = {}  # database_menu_id -> list of items

        for item in all_menu_items:
            database_menu_id = item["database_menu_id"]
            if database_menu_id not in items_by_menu:
                items_by_menu[database_menu_id] = []
            items_by_menu[database_menu_id].append(item)

        # Insert items for each menu
        for database_menu_id, menu_items in items_by_menu.items():
            # Get the root container ID for this menu
            root_container_id = root_container_map.get(database_menu_id)
            if not root_container_id:
                logger.warning(f"No root container found for menu {database_menu_id}, skipping menu items")
                continue

            # First pass: insert top-level items (children of root container)
            top_level_items = [item for item in menu_items if item.get("parent_name") is None]
            child_items = [item for item in menu_items if item.get("parent_name") is not None]

            logger.info(f"Processing {len(top_level_items)} top-level items for menu {database_menu_id}")

            for item in top_level_items:
                try:
                    # Check if item already exists (child of root container)
                    existing_item = await db_client.fetchrow(
                        "SELECT id FROM spree_menu_items WHERE name = $1 AND menu_id = $2 AND parent_id = $3", item["name"], database_menu_id, root_container_id
                    )

                    if existing_item:
                        item_id_map[f"{database_menu_id}_{item['name']}"] = existing_item["id"]
                        continue

                    # Insert top-level menu item (child of root container)
                    item_record = await db_client.fetchrow(
                        """
                        INSERT INTO spree_menu_items (name, subtitle, destination, new_window, item_type,
                                                    linked_resource_type, linked_resource_id, code, parent_id,
                                                    lft, rgt, depth, menu_id, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                        RETURNING id
                        """,
                        item["name"],
                        item.get("subtitle"),
                        item["destination"],
                        item.get("new_window", False),
                        item.get("item_type", "Link"),
                        item.get("linked_resource_type", "Spree::Linkable::Uri"),
                        item.get("linked_resource_id"),
                        item.get("code"),
                        root_container_id,  # parent_id = root container
                        item.get("lft", 1),
                        item.get("rgt", 2),
                        1,  # depth = 1 (child of root container at depth 0)
                        database_menu_id,
                        current_time,
                        current_time,
                    )

                    if item_record:
                        item_id_map[f"{database_menu_id}_{item['name']}"] = item_record["id"]

                except Exception as e:
                    logger.error(f"Failed to insert top-level menu item {item['name']}: {e}")
                    continue

            # Second pass: insert child items
            logger.info(f"Processing {len(child_items)} child items for menu {database_menu_id}")

            for item in child_items:
                try:
                    parent_name = item.get("parent_name")
                    parent_key = f"{database_menu_id}_{parent_name}"

                    if not parent_name or parent_key not in item_id_map:
                        logger.warning(f"Parent '{parent_name}' not found for menu item '{item['name']}', skipping")
                        continue

                    parent_id = item_id_map[parent_key]

                    # Check if item already exists
                    existing_item = await db_client.fetchrow("SELECT id FROM spree_menu_items WHERE name = $1 AND parent_id = $2", item["name"], parent_id)

                    if existing_item:
                        item_id_map[f"{database_menu_id}_{item['name']}"] = existing_item["id"]
                        continue

                    # Insert child menu item
                    item_record = await db_client.fetchrow(
                        """
                        INSERT INTO spree_menu_items (name, subtitle, destination, new_window, item_type,
                                                    linked_resource_type, linked_resource_id, code, parent_id,
                                                    lft, rgt, depth, menu_id, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                        RETURNING id
                        """,
                        item["name"],
                        item.get("subtitle"),
                        item["destination"],
                        item.get("new_window", False),
                        item.get("item_type", "Link"),
                        item.get("linked_resource_type", "Spree::Linkable::Uri"),
                        item.get("linked_resource_id"),
                        item.get("code"),
                        parent_id,
                        item.get("lft", 1),
                        item.get("rgt", 2),
                        2,  # depth = 2 (grandchild of root container)
                        database_menu_id,
                        current_time,
                        current_time,
                    )

                    if item_record:
                        item_id_map[f"{database_menu_id}_{item['name']}"] = item_record["id"]

                except Exception as e:
                    logger.error(f"Failed to insert child menu item {item['name']}: {e}")
                    continue

        # Update nested set values for the complete hierarchy (including root containers)
        logger.info("Updating nested set values for complete menu hierarchy...")
        for database_menu_id in menu_id_map.values():
            try:
                # Get all menu items for this menu (including root container)
                all_menu_items = await db_client.fetch("SELECT id, name, parent_id, depth FROM spree_menu_items WHERE menu_id = $1 ORDER BY depth, name", database_menu_id)

                if all_menu_items:
                    # Build hierarchy mapping for nested set calculation
                    items_by_parent = {}
                    for item in all_menu_items:
                        parent_id = item["parent_id"]
                        if parent_id not in items_by_parent:
                            items_by_parent[parent_id] = []
                        items_by_parent[parent_id].append({"id": item["id"], "name": item["name"]})

                    # Calculate nested set values starting from root containers (parent_id = None)
                    lft_rgt_values, _ = calculate_nested_set_values_for_menu_items(items_by_parent, parent_id=None, left_value=1)

                    # Update all items with new nested set values
                    for item_id, values in lft_rgt_values.items():
                        await db_client.execute("UPDATE spree_menu_items SET lft = $1, rgt = $2 WHERE id = $3", values["lft"], values["rgt"], item_id)

            except Exception as e:
                logger.error(f"Failed to update nested set values for menu {database_menu_id}: {e}")

        logger.succeed(f"Successfully processed {len(menu_id_map)} menus and {len(item_id_map)} menu items in the database")

    except Exception as e:
        logger.error(f"Error seeding menus in database: {e}")
        raise
