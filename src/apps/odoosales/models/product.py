from typing import Literal

from pydantic import BaseModel, Field


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
    description_picking: str = Field(
        description="""
                        Description of the product for internal transfer operations. 
                        Should be concise and informative. 
                        No more than 100 words.
                    """
    )
    description_pickingin: str = Field(
        description="""
                        Description of the product for receiving operations. 
                        Should be concise and informative. 
                        No more than 100 words.
                    """
    )
    description_pickingout: str = Field(
        description="""
                        Description of the product for picking operations. 
                        Should be concise and informative. 
                        No more than 100 words.
                    """
    )
    description_purchase: str = Field(
        description="""
                        Description of the product for purchase operations. 
                        Should be concise and informative. 
                        No more than 100 words.
                    """
    )
    description_sale: str = Field(
        description="""
                        Description of the product for sale operations. 
                        Should be concise and informative. 
                        No more than 100 words.
                    """
    )
    product_type: Literal["consu", "service"] = Field(
        description="""
                        Type of the product.
                        Choose from the following options:
                        - 'consu': For consumable products that can be sold.
                        - 'service': For services that can be sold.
                        Use 'consu' for physical products that can be sold.
                        Use 'service' for services that can be sold.
                    """,
        default="consu",
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
    category: Literal[
        "Home Essentials",
        "Electronics",
        "Apparel",
        "Health & Beauty",
        "Office Supplies",
        "Gift Sets & Bundles",
    ] = Field(
        description="""
                        Should be relevant to the product name and description.
                    """
    )
    variants: list[ProductAttribute] = Field(
        description="""
            List of product variants
            Variants should be relevant to the product name and description.
            Each product should have at least 2 variant.
            Use realistic and popular variant names.
        """,
        default_factory=list,
    )
    tags: list[str] = Field(
        description="""
            List of product tags.
            Tags should be relevant to the product name and description.
            Use popular and realistic tag names.
            Each product should have at least 2 tags.
        """,
        default_factory=list,
    )
    uom: Literal[
        "Units",
        "Dozens",
        "Days",
        "Hours",
        "m",
        "mm",
        "km",
        "cm",
        "m²",
        "L",
        "m³",
        "kg",
        "g",
        "t",
        "lb",
        "oz",
        "in",
        "ft",
        "yd",
        "mi",
        "ft²",
        "fl oz (US)",
        "qt (US)",
        "gal (US)",
        "in³",
        "ft³",
        "Pack",
        "Box",
        "Pallet",
    ] = Field(
        description="""
            ID of the unit of measure for the product.
            Choose the most appropriate unit of measure for the product.
            Get from provided list of unit of measures.
        """,
        default_factory=list,
    )
    weight: float = Field(
        description="""
            Weight of the product in kg.
            Use realistic weight for the product.
            If the product is not physical, use 0.
        """,
        default=0.0,
    )
    volume: float = Field(
        description="""
            Volume of the product in m³.
            Use realistic volume for the product.
            If the product is not physical, use 0.
        """,
        default=0.0,
    )


class ProductResponse(BaseModel):
    products: list[Product] = Field(description="A list of generated products.")
