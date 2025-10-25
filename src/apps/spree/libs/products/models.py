from pydantic import BaseModel, Field


class Variant(BaseModel):
    """Individual variant model."""

    option_values: list[int] = Field(description="List of option value IDs for this variant")
    price: float = Field(description="Price for this variant")
    stock_quantity: int = Field(description="Stock quantity between 100-500")
    sku_suffix: str = Field(description="SKU suffix for this variant")
    position: int = Field(description="Position/order of this variant (1, 2, 3, etc.)")


class Product(BaseModel):
    """Individual product model."""

    id: int = Field(description="Unique identifier for the product")  # noqa: A003, RUF100
    name: str = Field(description="Product name")
    description: str = Field(description="Product description, use HTML for formatting")
    prototype_id: int = Field(description="Prototype ID that this product uses")
    master_price: float = Field(description="Master price of the product")
    sku: str = Field(description="Product SKU")
    variants: list[Variant] = Field(description="List of product variants")
    image_keywords: list[str] = Field(description="Keywords for searching stock images/demo photos", default_factory=list)
    meta_title: str = Field(description="SEO meta title for the product")
    meta_description: str = Field(description="SEO meta description for the product")
    meta_keywords: str = Field(description="SEO meta keywords for the product")
    status: str = Field(description="Product status", default="active")
    promotionable: bool = Field(description="Whether product can be promoted", default=True)
    taxon_ids: list[int] = Field(description="List of taxon IDs to categorize this product", default_factory=list)
    available_on: str = Field(description="Date when product becomes available (ISO format)", default="")


class ProductForGeneration(BaseModel):
    """Product model for AI generation (without ID and description)."""

    name: str = Field(description="Product name")
    prototype_id: int = Field(description="Prototype ID that this product uses")
    master_price: float = Field(description="Master price of the product")
    sku: str = Field(description="Product SKU")
    variants: list[Variant] = Field(description="List of product variants")
    image_keywords: list[str] = Field(description="Keywords for searching stock images/demo photos", default_factory=list)
    status: str = Field(description="Product status", default="active")
    promotionable: bool = Field(description="Whether product can be promoted", default=True)
    taxon_ids: list[int] = Field(description="List of taxon IDs to categorize this product", default_factory=list)
    available_on: str = Field(description="Date when product becomes available (ISO format)", default="")


class ProductsResponse(BaseModel):
    """Response format for generated products."""

    products: list[ProductForGeneration]


class SingleProductResponse(BaseModel):
    """Response format for a single generated product."""

    product: ProductForGeneration


class ProductDescriptionForGeneration(BaseModel):
    """Product description model for AI generation (without ID)."""

    description: str = Field(description="Rich HTML product description")
    meta_title: str = Field(description="SEO meta title for the product")
    meta_description: str = Field(description="SEO meta description for the product")
    meta_keywords: str = Field(description="SEO meta keywords for the product")


class SingleDescriptionResponse(BaseModel):
    """Response format for a single generated product description."""

    description: ProductDescriptionForGeneration
