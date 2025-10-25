from pydantic import BaseModel, Field


class Combo(BaseModel):
    name: str = Field(
        description="""
            Name of the combo product.
            Should be descriptive and unique.
            Avoid using brand names or specific product lines.

            Example: "Office Essentials Combo", "Home Entertainment Bundle", "Gift Candle Set
        """,
    )
    products: list[str] = Field(
        description="""
            Get from provided list of products.
            Should be relevant to the combo name.
        """
    )


class ComboResponse(BaseModel):
    combos: list[Combo] = Field(description="List of generated combo products.")
