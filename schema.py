from typing import List, Optional
from pydantic import BaseModel, Field


class Items(BaseModel):
    item_description: Optional[str] = Field(default=None, description="Item description.")
    hs_code: Optional[str] = Field(default=None, description="6 to 10-digit HS Tariff Code.")
    unit_of_measure: Optional[str] = Field(default="PCS", description="Unit of measure (e.g., PCS, KGM, SET).")
    quantity: Optional[float] = Field(default=0.0, description="Quantity.")
    unit_price: Optional[float] = Field(default=0.0, description="Unit price.")
    total_price: Optional[float] = Field(default=0.0, description="Line item total (Quantity * Unit Price).")
    country_of_origin: Optional[str] = Field(default=None, description="2-letter ISO country code of manufacture (e.g., CN).")


class InvoiceDataResponse(BaseModel):
    # Core Nafeza & Compliance Identifiers
    acid_number: Optional[str] = Field(default=None, description="19-digit Egyptian ACID number.")
    importer_tax_id: Optional[str] = Field(default=None, description="9-digit Egyptian Importer Tax ID.")
    exporter_address: Optional[str] = Field(default=None, description="Address of the exporter company.")
    
    # Invoice Details
    invoice_number: Optional[str] = Field(default=None, description="Commercial invoice number or code.")
    invoice_date: Optional[str] = Field(default=None, description="Date of the invoice.")
    currency: Optional[str] = Field(default="USD", description="3-letter ISO currency code.")
    
    # Port & Logistics Info
    origin_port: Optional[str] = Field(default=None, description="Port of loading / export origin (e.g., CNSHA).")
    destination_port: Optional[str] = Field(default=None, description="Port of discharge / import destination (e.g., EGALY).")

    # Reconciliation Totals
    bill_total: Optional[float] = Field(default=0.0, description="Declared grand total printed on invoice.")
    calculated_total: Optional[float] = Field(
        default=0.0, 
        description="Sum of all extracted line item totals for reconciliation."
    )
    totals_match: Optional[bool] = Field(
        default=True, 
        description="True if calculated line items total matches the printed bill total."
    )
    
    items: List[Items] = Field(default_factory=list, description="List of line items extracted from table.")