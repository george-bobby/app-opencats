import pandas as pd
from pydantic import BaseModel, Field

from apps.odoosales.config.settings import settings


df_products = pd.read_json(settings.DATA_PATH.joinpath("products.json"))


class Combo(BaseModel):
    name: str = Field(
        description="""
                    Name of the combo
                    It should be descriptive and relevant to the products included.
                    For example, "Healthy Snack Combo" or "Office Essentials Bundle".
                    The name should be catchy and appealing to customers.
        """
    )
    products: list[str] = Field(
        description=f"""
                    Choose from the following allowed products: {list(df_products["name"].to_list())}.
                    Each combo should include at least 3 products.
                    The products should be relevant to each other, and combo name, and form a cohesive theme.
        """
    )


class ComboResponse(BaseModel):
    combos: list[Combo] = Field(description="A list of generated combos.")
