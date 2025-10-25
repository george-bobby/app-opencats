from common.logger import Logger


logger = Logger()


def _deduplicate_variants(variants: list) -> list:
    """Remove duplicate variants based on option_values."""

    seen_option_combinations = set()
    unique_variants = []

    for variant in variants:
        # Create a tuple of sorted option values for comparison
        option_combo = tuple(sorted(variant.option_values))

        if option_combo not in seen_option_combinations:
            seen_option_combinations.add(option_combo)
            unique_variants.append(variant)
        else:
            logger.warning(f"Skipping duplicate variant with option_values: {variant.option_values}")

    return unique_variants


def _build_constraints_context(existing_names: set[str] | None, existing_skus: set[str] | None, target_taxon: dict | None) -> str:
    """Build constraints context for deduplication and targeting."""
    constraints = []

    # Deduplication constraints
    if existing_names:
        names_list = list(existing_names)[:10]
        constraints.append(f"AVOID THESE NAMES: {names_list}")
    if existing_skus:
        skus_list = list(existing_skus)[:10]
        constraints.append(f"AVOID THESE SKUs: {skus_list}")

    # Target category constraint
    if target_taxon:
        constraints.append(f"TARGET: {target_taxon['name']} (ID: {target_taxon['id']})")
        constraints.append(f"DESCRIPTION: {target_taxon.get('description', 'Pet supplies category')}")

    return "\n".join(constraints) if constraints else ""


def _extract_product_specs(basic_product) -> dict[str, str | int | float]:
    """Extract key specs from technical product for marketing context."""
    specs = {
        "name": basic_product.name,
        "sku": basic_product.sku,
        "master_price": basic_product.master_price,
        "variant_count": len(basic_product.variants),
        "has_variants": len(basic_product.variants) > 0,
    }

    # Add variant pricing info if available
    if basic_product.variants:
        prices = [v.price for v in basic_product.variants]
        specs["price_range"] = f"${min(prices):.2f} - ${max(prices):.2f}"
        specs["sample_variants"] = [f"{v.sku_suffix} (${v.price})" for v in basic_product.variants[:3]]
    else:
        specs["price_range"] = f"${basic_product.master_price:.2f}"
        specs["sample_variants"] = []

    return specs
