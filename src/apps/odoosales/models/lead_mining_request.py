import pandas as pd
from pydantic import BaseModel, Field

from apps.odoosales.config.constants import SALE_TEAMS_DATA
from apps.odoosales.config.settings import settings


df_tags = pd.read_json(settings.DATA_PATH.joinpath("sale_tags.json"))
df_sale_teams = pd.DataFrame(SALE_TEAMS_DATA)
df_users = pd.read_json(settings.DATA_PATH.joinpath("users.json"))


class LeadMiningRequest(BaseModel):
    name_prefix: str = Field(
        description="""
            Prefix for the lead mining request name. Odoo will append a unique identifier to this prefix.
            This prefix helps in identifying the request in Odoo's UI.
            Example: "Tech Leads Q3", "Edu Leads APAC", etc.
        """
    )
    leads_count: int = Field(
        description="""
            The number of leads to be mined in this request. 
            It should be realistic based on the industry and country.    
            No more than 10 leads per request.                
        """
    )
    country_names: list[str] = Field(
        description="""
            List of country names to filter leads by. Odoo will use these countries to generate leads.
            If a country name does not match any in Odoo's database, it will be skipped.
            Get from provided list of countries.
        """
    )
    industry_names: list[str] = Field(
        description="""
            List of industry names to filter leads by. Odoo will use these industries to generate leads.
            If an industry name does not match any in Odoo's crm.iap.lead.industry records, it will be skipped.
            Get from provided list of IAP industries
        """
    )
    sales_team_name: str = Field(
        description=f"""
            Name of the sales team to assign the leads to. Odoo will use this team for the generated leads.
            If the team name does not match any in Odoo's crm.team records, it will be skipped.
            Get available teams from {df_sale_teams["name"].to_list()}.
        """
    )
    salesperson_name: str = Field(
        description=f"""
            Name of the salesperson to assign the leads to. Odoo will use this user for the generated leads.
            If the salesperson name does not match any in Odoo's res.users records, it will be skipped.
            Get available salespersons from {df_users["name"].to_list()}.
        """
    )
    tag_names: list[str] = Field(
        description=f"""
            List of tag names to assign to the leads. Odoo will use these tags for the generated leads.
            Example: ["Hot Lead", "Enterprise", "New Opportunity"].
            If a tag name does not match any in Odoo's crm.tag records, it will be skipped.
            
            Get available tags from {df_tags["name"].to_list()}.
        """
    )


class LeadMiningRequestResponse(BaseModel):
    lead_mining_requests: list[LeadMiningRequest] = Field(description="List of generated lead mining requests.")
