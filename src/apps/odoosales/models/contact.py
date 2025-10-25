from typing import Literal

from pydantic import BaseModel, Field


class Address(BaseModel):
    """Address information for a contact in the USA"""

    contact_name: str = Field(description="Full name of the contact person at this address.")
    email: str = Field(
        description="""
            Email address for this contact location.
            The domain must be gmail.com or outlook.com
            The email should be unique and not already used by any other individual.
        """
    )
    street: str = Field(description="Street number and name.")
    city: str = Field(description="City name.")
    state: str = Field(
        description="""
                        States in the USA.         
                        Return complete state name, NOT the 2-letter abbreviation.
                        For example, use 'California' instead of 'CA', use 'New York' instead of 'NY'.   
                    """
    )
    zip_code: str = Field(description="5-digit ZIP code (e.g., 90210).")
    note: str | None = Field(description="Optional notes about this address (e.g., 'Side door entrance').")


class LinkedContact(BaseModel):
    """Information about a linked contact person"""

    name: str = Field(description="Full name of the linked contact")
    title: Literal["Miss", "Madam", "Mister"] = Field(
        description="""
            Title of contact. 
            Should base on the gender or name of the contact person.
            
            Must be one of the following: 'Miss', 'Madam', 'Mister'.
        """
    )
    job_position: str = Field(description="Job position or role within the organization")
    email: str = Field(description="Email address of the linked contact")
    note: str | None = Field(description="Additional notes about this contact person")


class BankAccount(BaseModel):
    """Bank account information for invoicing"""

    bank_name: str = Field(
        description="""
            Name of the bank where the account is held.
            This should be the full name of the bank, not an abbreviation or acronym.
            It should be a recognized financial institution in the USA.
        """
    )
    account_number: str = Field(
        description="""
            Bank account number.
            This should be a valid account number for the bank where the company holds its primary account.
            It should be a numeric string, typically 10-12 digits long.
        """
    )


class Company(BaseModel):
    """Main contact/company model"""

    name: str = Field(description="Full legal name of the company or organization.")
    email: str = Field(description="Primary email address for the company.")
    primary_address: Address = Field(description="The company's main business address.")
    industry: str = Field(
        description="""
                        Get from provided list of industries.
                        This field represents the type of business the company is engaged in.      
                    """
    )
    category: str = Field(
        description="""
                            Get from provided list of contact tags.
                            This field represents the classification of the business relationship.
                        """
    )
    vat: str | None = Field(description="VAT number or Tax ID (e.g., Employer Identification Number - EIN in the US).")
    website: str | None = Field(description="Official company website URL.")
    note: str | None = Field(description="General notes about the company.")
    delivery_address: Address | None = Field(description="Default shipping address for goods.")
    invoice_address: Address | None = Field(description="Default billing address for invoices.")
    linked_contact: LinkedContact | None = Field(description="A key contact person within the company")
    primary_bank_account: BankAccount = Field(description="Primary bank account for customer invoicing.")


class Individual(BaseModel):
    """Main contact/individual model"""

    name: str = Field(description="Full name of the individual.")
    title: Literal["Miss", "Madam", "Mister"] = Field(
        description="""
            Title of contact. 
            Should base on the gender or name of the contact person.
            
            Must be one of the following: 'Miss', 'Madam', 'Mister'.
        """
    )
    phone: str = Field(description="Primary 10-digit phone number for the contact (e.g., 555-123-4567).")
    mobile: str = Field(description="Mobile phone number for the contact (e.g., 555-987-6543).")
    job_position: str = Field(description="The individual's job title or role.")
    email: str = Field(
        description="""
            Primary email address for the individual.
            The domain must be gmail.com or outlook.com
            The email should be unique and not already used by any other individual.
        """
    )
    vat: str | None = Field(description="VAT number or Tax ID (e.g., Employer Identification Number - EIN in the US).")
    primary_address: Address = Field(description="The individual's primary residential or business address.")
    category: str = Field(
        description="""
                            Get from provided list of contact tags.
                            This field represents the classification of the business relationship.
                        """
    )
    vat: str = Field(description="Tax identification number (e.g., Social Security Number - SSN in the US).")
    website: str | None = Field(description="Personal or professional website URL.")
    note: str | None = Field(description="General notes about the individual.")
    primary_bank_account: BankAccount = Field(description="Primary bank account for customer invoicing.")


class IndividualResponse(BaseModel):
    individuals: list[Individual] = Field(description="A list of generated individuals.")


class CompanyResponse(BaseModel):
    companies: list[Company] = Field(description="A list of generated companies.")
