from pydantic import BaseModel, Field

from apps.odoosales.config.settings import settings


class Lead(BaseModel):
    name: str = Field(
        description=f"""
            Name of the lead.
            It should be a descriptive title that summarizes the lead's potential.
            Focus on business theme ${settings.DATA_THEME_SUBJECT} and the specific business problem it addresses.
            Example: "Increase sales through targeted marketing campaigns"
        """
    )
    description: str = Field(
        description=f"""
            Detailed description of the lead.
            It should be relevant to lead name and provide context for the business problem.
            It should provide a comprehensive overview of the business problem and how it relates to the theme ${settings.DATA_THEME_SUBJECT}.
            No more than 8 words.
        """
    )


class LeadResponse(BaseModel):
    leads: list[Lead] = Field(description="A list of generated leads.")
