from typing import Literal

from pydantic import BaseModel, Field


class ProductTag(BaseModel):
    name: str = Field(
        description="""
            The name of the product tag.
            Should be descriptive and relevant to the product.
            Use popular and realistic tag names.
        """,
    )


class ProductAttribute(BaseModel):
    name: str = Field(
        description="""
            The attribute name of the product variant.
            The attribute name should be realistic and popular.
        """,
    )

    display_type: Literal["color", "select", "radio"] = Field(
        description="""
            The display type of the product variant attribute.
            Choose from the following options:
            - 'color': For color attributes, use this display type.
            - 'select': For attributes that can be selected from a dropdown.
            - 'radio': For attributes that can be selected using radio buttons.
        """,
    )

    values: list[str] = Field(
        description="""
            The values of the product variant attribute.
            The values should be relevant to the attribute name.
            For each attribute, provide 2-3 values.
        """,
    )


class Product(BaseModel):
    name: str = Field(
        description="""
                        Name of the product. 
                        Should be generic, descriptive and unique. 
                        Using popular product names is recommended.
                        Avoid using brand names or specific product lines.

                        EXAMPLE: 
                            Wireless Bluetooth Headphones, 
                            Ergonomic Office Chair, 
                            Smartphone with 5G Connectivity, 
                            Portable Power Bank, 
                            Gaming Mouse with RGB Lighting
                    """
    )
    description: str = Field(
        description="""
                        Summary description of the product. 
                        Should be concise and informative. 
                        No more than 100 words
                    """
    )
    list_price: float = Field(
        description="""
                        Price of the product in USD. 
                        Give a realistic price for the product.          
                    """
    )
    cost: float = Field(
        description="""
                        Cost of the product in USD. 
                        This is the cost to the store, not the selling price.
                    """
    )
    category: str = Field(
        description="""
                        Get from provided list of product categories.     
                        Should be relevant to the product name and description.
                    """
    )
    variants: list[ProductAttribute] = Field(
        description="""
            List of product variants base on provided attributes
        """,
        default_factory=list,
    )
    uom: str = Field(
        description="""
            ID of the unit of measure for the product.
            Choose the most appropriate unit of measure for the product.
            Get from provided list of unit of measures.
        """,
    )


class ProductResponse(BaseModel):
    products: list[Product] = Field(
        description="List of generated products",
        default_factory=list,
    )
