from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class TariffRequest(BaseModel):
    url: str
    provider: Optional[str] = "generic"
    zone: Optional[str] = None  # Optional zone filter (e.g., "1", "2", "all")

class Rate(BaseModel):
    weight: str
    price: float
    currency: str = "INR"
    item_type: Optional[str] = None  # "Documents" or "Non-Documents"

class ZoneRates(BaseModel):
    zone_id: str
    rates: List[Rate]

class ServiceZones(BaseModel):
    service_name: str
    export_zone: Optional[str] = None
    import_zone: Optional[str] = None

class Country(BaseModel):
    country_name: str
    country_code: str
    service_zones: List[ServiceZones]  # Export/Import zones for each service

class TariffResponse(BaseModel):
    provider: str
    countries: List[Country]
    zone_rates: Dict[str, List[ZoneRates]]  # service_name -> list of zone rates
    raw_data: Optional[Dict[str, Any]] = None
