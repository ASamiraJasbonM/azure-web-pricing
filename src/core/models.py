"""
Data models for Azure pricing and cost estimation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class ServiceType(Enum):
    """Azure service types"""
    VIRTUAL_MACHINES = "Virtual Machines"
    AKS = "Kubernetes Service"
    SQL_DATABASE = "Azure SQL Database"
    REDIS_CACHE = "Azure Cache for Redis"
    CONTAINER_REGISTRY = "Container Registry"
    DNS = "DNS"
    AZURE_DEVOPS = "Azure DevOps"
    APP_SERVICE = "App Service"
    FUNCTIONS = "Functions"
    STORAGE = "Storage Accounts"


class PricingTier(Enum):
    """Pricing tiers for Azure services"""
    # VM tiers
    STANDARD = "Standard"
    PREMIUM = "Premium"
    IO_OPTIMIZED = "IO Optimized"
    
    # SQL tiers
    BASIC = "Basic"
    GENERAL_PURPOSE = "General Purpose"
    BUSINESS_CRITICAL = "Business Critical"
    HYPERSCALE = "Hyperscale"
    
    # Redis tiers
    BASIC_TIER = "Basic"
    STANDARD_TIER = "Standard"
    PREMIUM_TIER = "Premium"


@dataclass
class PriceItem:
    """Model for a single price item from Azure API"""
    service_name: str
    sku_name: str
    retail_price: float
    unit_of_measure: str
    region: str
    currency: str = "USD"
    price_type: str = "Consumption"
    meter_name: str = ""
    product_name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "sku_name": self.sku_name,
            "retail_price": self.retail_price,
            "unit_of_measure": self.unit_of_measure,
            "region": self.region,
            "currency": self.currency,
            "price_type": self.price_type,
        }


@dataclass
class ServiceConfig:
    """Configuration for a single service in a deployment"""
    service_type: ServiceType
    sku: str
    quantity: int = 1
    hours_per_month: int = 730
    tier: Optional[PricingTier] = None
    region: str = "westus"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceConfig":
        return cls(
            service_type=ServiceType(data.get("type", "")),
            sku=data.get("sku", ""),
            quantity=data.get("quantity", 1),
            hours_per_month=data.get("hours_per_month", 730),
            tier=data.get("tier"),
            region=data.get("region", "westus"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.service_type.value,
            "sku": self.sku,
            "quantity": self.quantity,
            "hours_per_month": self.hours_per_month,
            "tier": self.tier.value if self.tier else None,
            "region": self.region,
        }


@dataclass
class CostBreakdown:
    """Cost breakdown for a service"""
    service_name: str
    hourly_cost: float
    monthly_cost: float
    yearly_cost: float
    currency: str = "USD"
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "hourly_cost": self.hourly_cost,
            "monthly_cost": self.monthly_cost,
            "yearly_cost": self.yearly_cost,
            "currency": self.currency,
            "details": self.details,
        }


@dataclass
class DeploymentEstimate:
    """Complete deployment estimate"""
    services: List[ServiceConfig]
    region: str
    currency: str = "USD"
    created_at: datetime = field(default_factory=datetime.now)
    
    total_monthly: float = 0.0
    total_hourly: float = 0.0
    total_yearly: float = 0.0
    
    breakdown: List[CostBreakdown] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "services": [s.to_dict() for s in self.services],
            "region": self.region,
            "currency": self.currency,
            "created_at": self.created_at.isoformat(),
            "total_monthly": self.total_monthly,
            "total_hourly": self.total_hourly,
            "total_yearly": self.total_yearly,
            "breakdown": [b.to_dict() for b in self.breakdown],
        }


@dataclass
class RegionPriceComparison:
    """Price comparison across regions"""
    sku: str
    prices_by_region: Dict[str, float] = field(default_factory=dict)
    
    def get_cheapest_region(self) -> Optional[str]:
        if not self.prices_by_region:
            return None
        return min(self.prices_by_region, key=self.prices_by_region.get)
    
    def get_expensive_region(self) -> Optional[str]:
        if not self.prices_by_region:
            return None
        return max(self.prices_by_region, key=self.prices_by_region.get)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sku": self.sku,
            "prices_by_region": self.prices_by_region,
            "cheapest_region": self.get_cheapest_region(),
            "expensive_region": self.get_expensive_region(),
        }


# Common Azure regions
AZURE_REGIONS = [
    "westus",
    "eastus",
    "westus2",
    "eastus2",
    "centralus",
    "northcentralus",
    "southcentralus",
    "westcentralus",
    "canadacentral",
    "canadaeast",
    "brazilsouth",
    "northeurope",
    "westeurope",
    "uksouth",
    "ukwest",
    "francecentral",
    "germanywestcentral",
    "norwayeast",
    "switzerlandnorth",
    "swedencentral",
    "eastasia",
    "southeastasia",
    "australiaeast",
    "australiasoutheast",
    "japaneast",
    "japanwest",
    "koreacentral",
    "southindia",
    "centralindia",
    "uaenorth",
]


# Common VM SKUs
VM_SKUS = [
    "Standard_A1_v2",
    "Standard_A2_v2",
    "Standard_A4_v2",
    "Standard_A8_v2",
    "Standard_B1s",
    "Standard_B1ms",
    "Standard_B2s",
    "Standard_B2ms",
    "Standard_B4ms",
    "Standard_B8ms",
    "Standard_D1_v2",
    "Standard_D2_v2",
    "Standard_D4_v2",
    "Standard_D8_v2",
    "Standard_D16_v2",
    "Standard_D32_v2",
    "Standard_D2s_v3",
    "Standard_D4s_v3",
    "Standard_D8s_v3",
    "Standard_D16s_v3",
    "Standard_D32s_v3",
    "Standard_E2s_v3",
    "Standard_E4s_v3",
    "Standard_E8s_v3",
    "Standard_E16s_v3",
    "Standard_E32s_v3",
]


# SQL Database SKUs
SQL_SKUS = [
    "GP_Gen5_2",
    "GP_Gen5_4",
    "GP_Gen5_8",
    "GP_Gen5_16",
    "GP_Gen5_32",
    "BC_Gen5_2",
    "BC_Gen5_4",
    "BC_Gen5_8",
    "BC_Gen5_16",
    "BC_Gen5_32",
]


# Redis Cache SKUs
REDIS_SKUS = [
    "Basic C0",
    "Basic C1",
    "Basic C2",
    "Basic C3",
    "Basic C4",
    "Basic C5",
    "Basic C6",
    "Standard C0",
    "Standard C1",
    "Standard C2",
    "Standard C3",
    "Standard C4",
    "Standard C5",
    "Standard C6",
    "Premium P1",
    "Premium P2",
    "Premium P3",
    "Premium P4",
]