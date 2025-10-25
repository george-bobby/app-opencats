import pandas as pd
from pydantic import BaseModel, Field

from apps.odooinventory.config.constants import COMPONENT_CATEGORIES


df_component_categories = pd.DataFrame(COMPONENT_CATEGORIES)


class Component(BaseModel):
    name: str = Field(
        description="""
            The name of the component that used to make up the product in BOM.
            The name should be clear, descriptive, and relevant to the product.
            For example, if the product is a shirt, the component name could be 'Cotton Fabric – White', etc.
        """
    )
    category: str = Field(
        description=f"""
            The category of the product category to which the component belongs.,
            Get available categories from the list of product categories: {df_component_categories["name"].to_list()}.,
            The category should be relevant to the component and product.,
        """
    )


class Operation(BaseModel):
    name: str = Field(description="The name of the operation to be performed on the component")
    work_center: str = Field(
        description="""
            Get from provided list of work centers.
            It should be relevant to the operation and the component.,
            It should be a complete name, not just a code or abbreviation.,
            For example, use 'Cutting Machine' instead of 'CM', use 'Sewing Station' instead of 'SS'.,
            The work center should be capable of performing the operation
            and should be available in the Odoo system.
        """
    )
    description: str = Field(
        description="""
            A brief description of the operation to be performed.,
            This should provide enough detail for the operator to understand the task.,
        """
    )
    duration: int = Field(
        description="""
            The duration of the operation in minutes.,
            This should be a reasonable estimate of the time required to complete the operation.
            The duration should be realistic and based on the complexity of the operation and the efficiency of the work center.
            For very complex operations, the duration can be longer, but it should not exceed 60 minutes.
            
            EXAMPLE
            - Fabric Cutting: 20 minutes
            - Sleeve Attachment: 35 minutes
            - Zipper Installation: 15 minutes
            - Final Stitching: 30 minutes
            - Quality Check: 10 minutes
            - Packing: 10 minutes
            - ...
        """,
    )


class BOM(BaseModel):
    product: str = Field(
        description="""
            Get from provided list of products.
            The product for which the Bill of Materials is created.,
            The product should be relevant to the components and operations in the BOM.,
            It should be unique for each BOM and should not be repeated across different BOMs.,
        """
    )
    components: list[Component] = Field(description="A list of components that make up the product in the Bill of Materials")
    operations: list[Operation] = Field(
        description="""
            A list of operations to be performed on the components in the Bill of Materials.
            Each operation should have a name, work center ID, and description.
            The operations should be relevant to the components and products and work centers's functionality.
        """
    )


class BOMResponse(BaseModel):
    bill_of_materials: list[BOM] = Field(description="A list of Bill of Materials (BOM) objects, each representing a product's BOM.")
