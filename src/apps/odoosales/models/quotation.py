from pydantic import BaseModel, Field


class Quotation(BaseModel):
    customer_name: str = Field(
        description="""
            Get from provided list of companies and individuals.
        """
    )
    product_name: str = Field(
        description="""
            Get from provided list of products.
            For company customer, use a realistic product name that fits the company's business interest.
        """
    )


class QuotationResponse(BaseModel):
    quotations: list[Quotation] = Field(description="A list of generated quotations.")
