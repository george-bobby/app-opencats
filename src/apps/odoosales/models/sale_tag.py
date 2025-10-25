from pydantic import BaseModel, Field


class SaleTag(BaseModel):
    name: str = Field(
        description="""
            Name of the sale tag.
            This should be a unique identifier for the tag
            
            EXAMPLE:
            - Holiday Order
            - Late Payment
            - Bulk Discount
        """,
    )


class SaleTagResponse(BaseModel):
    sale_tags: list[SaleTag] = Field(description="A list of generated sale tags.")
