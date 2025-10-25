import json
import logging
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch

from apps.gumroad.config.settings import settings
from apps.gumroad.utils.faker import faker
from apps.gumroad.utils.gumroad import GumroadAPI
from apps.gumroad.utils.mysql import AsyncMySQLClient
from common.logger import logger


# Suppress Elasticsearch INFO logs
logging.getLogger("elasticsearch").setLevel(logging.WARNING)


class ElasticsearchBackfill:
    """Backfill sales data from MySQL to Elasticsearch."""

    def __init__(self):
        self.es = Elasticsearch(settings.ELASTICSEARCH_URL)
        self.mysql = AsyncMySQLClient()

    async def __aenter__(self):
        await self.mysql.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.mysql.disconnect()

    async def backfill_purchases(self, batch_size: int = 1000, seller_id: int = 1):
        """Backfill all purchases from MySQL to Elasticsearch."""
        logger.info("Starting Elasticsearch purchases backfill...")

        # Get total count of purchases to backfill
        total_count_result = await self.mysql.fetch_one("SELECT COUNT(*) as count FROM purchases WHERE seller_id = %s", (seller_id,))
        total_count = total_count_result[0] if total_count_result else 0

        logger.info(f"Found {total_count} purchases to backfill for seller_id {seller_id}")

        if total_count == 0:
            logger.warning("No purchases found to backfill")
            return

        # Process in batches
        offset = 0
        successful_indexes = 0
        failed_indexes = 0

        while offset < total_count:
            logger.info(f"Processing batch {offset // batch_size + 1}: records {offset + 1} to {min(offset + batch_size, total_count)}")

            # Fetch batch of purchases with related data
            purchases = await self.fetch_purchase_batch(seller_id, batch_size, offset)

            # Index the batch
            batch_successful, batch_failed = await self.index_purchase_batch(purchases)
            successful_indexes += batch_successful
            failed_indexes += batch_failed

            offset += batch_size

        logger.info(f"Successfully indexed: {successful_indexes} purchases")
        logger.info(f"Failed to index: {failed_indexes} purchases")

        # Verify the total count in Elasticsearch
        total_es_count = self.es.count(index="purchases")
        if total_es_count and isinstance(total_es_count, dict) and "count" in total_es_count:
            logger.info(f"Total documents in purchases index: {total_es_count['count']}")
        else:
            logger.warning("Could not retrieve total document count from Elasticsearch for purchases index.")

    async def fetch_purchase_batch(self, seller_id: int, batch_size: int, offset: int) -> list[dict[str, Any]]:
        """Fetch a batch of purchases with all necessary related data."""
        query = """
        SELECT 
            p.id,
            p.seller_id,
            p.created_at,
            p.updated_at,
            p.fee_cents,
            p.link_id as product_id,
            p.email,
            p.price_cents,
            p.displayed_price_cents,
            p.displayed_price_currency_type,
            p.rate_converted_to_usd,
            p.street_address,
            p.city,
            p.state,
            p.zip_code,
            p.country,
            p.full_name,
            p.credit_card_id,
            p.purchaser_id,
            p.purchaser_type,
            p.session_id,
            p.ip_address,
            p.is_mobile,
            p.stripe_refunded,
            p.stripe_transaction_id,
            p.stripe_fingerprint,
            p.stripe_card_id,
            p.can_contact,
            p.referrer,
            p.stripe_status,
            p.variants,
            p.chargeback_date,
            p.webhook_failed,
            p.failed,
            p.card_type,
            p.card_visual,
            p.purchase_state,
            p.processor_fee_cents,
            p.succeeded_at,
            p.card_country,
            p.stripe_error_code,
            p.browser_guid,
            p.error_code,
            p.card_bin,
            p.custom_fields,
            p.ip_country,
            p.ip_state,
            p.purchase_success_balance_id,
            p.purchase_chargeback_balance_id,
            p.purchase_refund_balance_id,
            p.flags,
            p.offer_code_id,
            p.subscription_id,
            p.preorder_id,
            p.card_expiry_month,
            p.card_expiry_year,
            p.tax_cents,
            p.affiliate_credit_cents,
            p.credit_card_zipcode,
            p.json_data,
            p.card_data_handling_mode,
            p.charge_processor_id,
            p.total_transaction_cents,
            p.gumroad_tax_cents,
            p.zip_tax_rate_id,
            p.quantity,
            p.merchant_account_id,
            p.shipping_cents,
            p.affiliate_id,
            p.processor_fee_cents_currency,
            p.stripe_partially_refunded,
            p.paypal_order_id,
            p.rental_expired,
            p.processor_payment_intent_id,
            p.processor_setup_intent_id,
            p.price_id,
            p.recommended_by,
            p.deleted_at,
            -- Related data
            l.name as product_name,
            l.unique_permalink as product_unique_permalink,
            l.description as product_description,
            l.taxonomy_id,
            u.name as seller_name
        FROM purchases p
        LEFT JOIN links l ON p.link_id = l.id
        LEFT JOIN users u ON p.seller_id = u.id
        WHERE p.seller_id = %s
        ORDER BY p.id
        LIMIT %s OFFSET %s
        """

        results = await self.mysql.fetch_dict_all(query, (seller_id, batch_size, offset))
        return results

    async def index_purchase_batch(self, purchases: list[dict[str, Any]]) -> tuple[int, int]:
        """Index a batch of purchases into Elasticsearch."""
        successful = 0
        failed = 0
        failed_ids = []

        for purchase in purchases:
            try:
                # Transform the purchase data to match Elasticsearch mapping
                es_doc = self.transform_purchase_for_elasticsearch(purchase)

                # Index the document
                result = self.es.index(
                    index="purchases",
                    id=purchase["id"],  # Use MySQL ID as Elasticsearch document ID
                    body=es_doc,
                )

                if result and result.get("result") in ["created", "updated"]:
                    successful += 1
                else:
                    failed += 1
                    failed_ids.append(purchase["id"])
                    logger.error(f"Unexpected result for purchase {purchase['id']}: {result}")

            except Exception as e:
                failed += 1
                failed_ids.append(purchase["id"])
                logger.error(f"Failed to index purchase {purchase['id']}: {e!s}")
                # Log the problematic document for debugging
                logger.debug(f"Problematic purchase data: {purchase}")

        if failed_ids:
            logger.warning(f"Failed to index {len(failed_ids)} purchases in this batch: {failed_ids}")

        return successful, failed

    def transform_purchase_for_elasticsearch(self, purchase: dict[str, Any]) -> dict[str, Any]:
        """Transform MySQL purchase data to Elasticsearch document format."""

        # Helper function to safely convert datetime strings
        def safe_datetime(dt_str):
            if dt_str is None:
                return None
            if isinstance(dt_str, str):
                try:
                    # Parse MySQL datetime format: "2025-02-09 10:42:37"
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    # Convert to ISO format with UTC timezone
                    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                except ValueError:
                    try:
                        # Try parsing if it's already in ISO format
                        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).isoformat()
                    except ValueError:
                        return dt_str
            elif hasattr(dt_str, "isoformat"):
                # If it's already a datetime object
                return dt_str.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            return str(dt_str)

        # Helper function to safely extract domain from email
        def extract_email_domain(email):
            if email and "@" in email:
                return email.lower().split("@")[1]
            return None

        # Helper function to extract domain from referrer
        def extract_referrer_domain(referrer):
            if not referrer or referrer == "direct":
                return "direct"

            # Simple domain extraction - you might want to use a proper URL parser
            if "://" in referrer:
                try:
                    from urllib.parse import urlparse

                    return urlparse(referrer).netloc.lower()
                except Exception:
                    return referrer.lower()
            return referrer.lower()

        # Calculate derived fields that match the Rails application logic
        chargeback_date = purchase.get("chargeback_date")
        stripe_refunded = purchase.get("stripe_refunded", False)
        subscription_id = purchase.get("subscription_id")
        flags = purchase.get("flags", 0) or 0

        ip_country = purchase.get("ip_country") or faker.first_world_country()
        ip_state = purchase.get("ip_state") or faker.state_abbr()

        # Transform flags integer to selected_flags list (this is a simplified version)
        # You might need to implement the actual flag decoding based on Rails FlagShihTzu
        selected_flags = []
        if isinstance(flags, int) and flags > 0 and flags & 1:  # Example flag check
            selected_flags.append("some_flag")

        es_doc = {
            "id": purchase["id"],
            "can_contact": bool(purchase.get("can_contact", False)),
            "chargeback_date": safe_datetime(chargeback_date),
            "country_or_ip_country": ip_country,
            "created_at": safe_datetime(purchase["created_at"]),
            "latest_charge_date": safe_datetime(purchase.get("succeeded_at") or purchase["created_at"]),
            "email": purchase.get("email", "").lower() if purchase.get("email") else None,
            "email_domain": extract_email_domain(purchase.get("email")),
            "paypal_email": purchase.get("email", "").lower() if purchase.get("card_type") == "paypal" else None,
            "fee_cents": purchase.get("fee_cents", 0) or 0,
            "full_name": purchase.get("full_name"),
            "not_chargedback_or_chargedback_reversed": chargeback_date is None,  # Simplified
            "not_refunded_except_subscriptions": not stripe_refunded or subscription_id is not None,
            "not_subscription_or_original_subscription_purchase": subscription_id is None,
            "successful_authorization_or_without_preorder": purchase.get("purchase_state")
            in [
                "successful",
                "preorder_authorization_successful",
                "preorder_concluded_successfully",
            ]
            or purchase.get("preorder_id") is None,
            "price_cents": purchase.get("price_cents", 0) or 0,
            "purchase_state": purchase.get("purchase_state", "failed"),
            "amount_refunded_cents": 0,  # You'll need to calculate this from refunds table if available
            "fee_refunded_cents": 0,  # You'll need to calculate this from refunds table if available
            "tax_refunded_cents": 0,  # You'll need to calculate this from refunds table if available
            "selected_flags": selected_flags,
            "stripe_refunded": bool(stripe_refunded),
            "tax_cents": purchase.get("tax_cents", 0) or 0,
            "monthly_recurring_revenue": 0.0,  # Calculate if needed
            "ip_country": ip_country,  # Fixed: now properly populated
            "ip_state": ip_state,  # Fixed: now properly populated
            "referrer_domain": extract_referrer_domain(purchase.get("referrer")),
            "license_serial": None,  # You'll need to join with licenses table if available
            "variant_ids": [],  # You'll need to join with variant_attributes if available
            "product_ids_from_same_seller_purchased_by_purchaser": [],  # Complex calculation
            "variant_ids_from_same_seller_purchased_by_purchaser": [],  # Complex calculation
            "affiliate_credit_id": None,  # Join with affiliate_credits if available
            "affiliate_credit_affiliate_user_id": None,
            "affiliate_credit_amount_cents": purchase.get("affiliate_credit_cents", 0) or 0,
            "affiliate_credit_fee_cents": 0,
            "affiliate_credit_amount_partially_refunded_cents": 0,
            "affiliate_credit_fee_partially_refunded_cents": 0,
            "product_id": purchase.get("product_id"),
            "product_unique_permalink": purchase.get("product_unique_permalink"),
            "product_name": purchase.get("product_name"),
            "product_description": purchase.get("product_description"),
            "seller_id": purchase.get("seller_id"),
            "seller_name": purchase.get("seller_name"),
            "purchaser_id": purchase.get("purchaser_id"),
            "subscription_id": subscription_id,
            "subscription_cancelled_at": None,  # Join with subscriptions if available
            "subscription_deactivated_at": None,  # Join with subscriptions if available
            "taxonomy_id": purchase.get("taxonomy_id"),
        }

        # Remove None values to keep the document clean
        return {k: v for k, v in es_doc.items() if v is not None}


async def backfill_all_purchases(seller_id: int = 1, batch_size: int = 500):
    """Main function to backfill all purchases for a seller."""
    logger.start("Backfilling all purchases...")
    async with ElasticsearchBackfill() as backfill:
        await backfill.backfill_purchases(batch_size=batch_size, seller_id=seller_id)
        logger.succeed("Backfilling all purchases completed")


async def generate_product_views(number_of_views: int):
    """Generate product views and save to JSON file."""
    logger.info(f"Generating {number_of_views} product views")

    # Create generated data directory if it doesn't exist
    generated_path = settings.DATA_PATH / "generated"
    generated_path.mkdir(parents=True, exist_ok=True)

    # Save data to JSON file
    data_to_save = {"number_of_views": number_of_views, "generated_at": datetime.now(UTC).isoformat()}

    json_file_path = generated_path / "product_views_data.json"
    with json_file_path.open("w") as f:
        json.dump(data_to_save, f, indent=2, default=str)

    logger.info(f"Generated product views data saved to: {json_file_path}")

    return json_file_path


async def seed_product_views(file_path: Path = settings.DATA_PATH / "generated" / "product_views_data.json"):
    """Seed product views using data from JSON file."""

    if not file_path.exists():
        logger.error(f"JSON file not found: {file_path}")
        logger.info("Please run generate_product_views() first to create the data file")
        return False

    # Load data from JSON file
    with file_path.open() as f:
        data = json.load(f)

    number_of_views = data["number_of_views"]
    logger.info(f"Loading product views data from: {file_path}")
    logger.info(f"Data generated at: {data['generated_at']}")

    # 1. Connect to Elasticsearch
    es = Elasticsearch(settings.ELASTICSEARCH_URL)
    async with GumroadAPI() as gumroad:
        products = await gumroad.get_all_products()

    seller_id = 1  # Replace with your seller/user ID

    logger.start(f"Adding {number_of_views} product views...")

    successful_indexes = 0
    failed_indexes = 0
    country = faker.first_world_country()

    for i in range(number_of_views):
        product_id = faker.random_element(elements=products)["id"]
        try:
            doc = {
                "product_id": product_id,
                "timestamp": faker.date_time_between(start_date="-1y", end_date="now").replace(tzinfo=UTC).isoformat(),
                "country": country,
                "state": faker.state(),
                "referrer_domain": faker.random_element(
                    elements=[
                        "direct",
                        # "google.com",
                        # "facebook.com",
                        # "twitter.com",
                        # "reddit.com",
                    ]
                ),
                "seller_id": seller_id,
                "user_id": faker.random_int(min=1, max=1000),
                "ip_address": faker.ipv4(),
                "url": f"https://seller.gumroad.dev/l/{product_id}",
                "browser_guid": str(uuid.uuid4()),
                "browser_fingerprint": faker.uuid4(),
                "referrer": faker.url(),
            }

            # Index the document (auto-generate an ID)
            index_result = es.index(index="product_page_views", body=doc)

            if index_result and index_result.get("result") in ["created", "updated"]:
                successful_indexes += 1
            else:
                failed_indexes += 1
                logger.error(f"Unexpected result for document {i + 1}: {index_result}")

        except Exception as e:
            failed_indexes += 1
            logger.error(f"Failed to index document {i + 1}: {e!s}")

        if (i + 1) % 1000 == 0:  # Progress indicator every 1000 views
            logger.info(f"Processed {i + 1} documents... (Success: {successful_indexes}, Failed: {failed_indexes})")

    logger.succeed("Indexing complete!")
    logger.info(f"Successfully indexed: {successful_indexes} views")
    logger.info(f"Failed to index: {failed_indexes} views")
    logger.info(f"Total processed: {successful_indexes + failed_indexes} out of {number_of_views} views")

    # Check total documents in the index
    total_count = es.count(index="product_page_views")
    if total_count and isinstance(total_count, dict) and "count" in total_count:
        logger.info(f"\nTotal documents in product_page_views index: {total_count['count']}")
    else:
        logger.warning("Could not retrieve total document count from Elasticsearch for product_page_views index.")

    # 3. Get total count of views for this product
    count_result = es.count(index="product_page_views", body={"query": {"term": {"product_id": product_id}}})
    if count_result and isinstance(count_result, dict) and "count" in count_result:
        logger.info(f"\nTotal views for product_id {product_id}: {count_result['count']}")
    else:
        logger.warning("Could not retrieve total view count from Elasticsearch for product_id.")

    # Show first 10 views as examples
    logger.info(f"\nFirst 10 views for product_id = {product_id}")
    search_result = es.search(
        index="product_page_views",
        body={"query": {"term": {"product_id": product_id}}},
    )
    if search_result and isinstance(search_result, dict) and "hits" in search_result and "hits" in search_result["hits"]:
        for hit in search_result["hits"]["hits"]:
            logger.info(f"  {hit['_source']}")
    else:
        logger.warning("Could not retrieve search results from Elasticsearch for product_id.")


async def delete_all_indices_and_reindex_all():
    """Delete all Elasticsearch indices and reindex everything by running the reset-es.sh script."""

    script_path = Path(__file__).resolve().parent.parent / "docker" / "reset-es.sh"
    script_path = str(script_path)

    logger.start("Running reset-es.sh script to delete and reindex all Elasticsearch data...")

    try:
        subprocess.run(["bash", script_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.succeed("Successfully completed deletion and reindexing of Elasticsearch data")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run reset-es.sh script: {e!s}")
        raise
