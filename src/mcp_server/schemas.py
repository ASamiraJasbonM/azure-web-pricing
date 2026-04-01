"""
Schemas and type definitions for MCP server
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SearchPricesRequest(BaseModel):
    """Request schema for search_azure_prices tool"""
    service_name: Optional[str] = Field(
        None,
        description="Name of the Azure service (e.g., 'Virtual Machines', 'Azure SQL Database')"
    )
    sku: Optional[str] = Field(
        None,
        description="ARM SKU name (e.g., 'Standard_D2s_v3', 'GP_Gen5_2')"
    )
    region: str = Field(
        "westus",
        description="Azure region code"
    )


class ServiceConfigRequest(BaseModel):
    """Service configuration for cost calculation"""
    type: str = Field(description="Service type (aks, sql, redis, etc.)")
    sku: str = Field(description="SKU identifier")
    quantity: int = Field(1, description="Number of instances")
    hours_per_month: int = Field(730, description="Hours per month")
    tier: Optional[str] = Field(None, description="Service tier")
    region: str = Field("westus", description="Azure region")


class CalculateCostRequest(BaseModel):
    """Request schema for calculate_deployment_cost tool"""
    services: List[Dict[str, Any]] = Field(
        description="List of service configurations"
    )
    region: str = Field("westus", description="Azure region")


class CompareRegionsRequest(BaseModel):
    """Request schema for compare_regions tool"""
    sku: str = Field(description="SKU to compare")
    regions: List[str] = Field(
        default=["westus", "eastus", "westeurope", "southeastasia"],
        description="List of regions to compare"
    )


class ChartRequest(BaseModel):
    """Request schema for create_cost_chart tool"""
    data: Dict[str, float] = Field(description="Cost data as key-value pairs")
    chart_type: str = Field(
        "bar",
        description="Chart type: bar, pie, line"
    )
    title: str = Field("Azure Cost Breakdown", description="Chart title")


class ReportRequest(BaseModel):
    """Request schema for generate_cost_report tool"""
    cost_data: Dict[str, Any] = Field(description="Cost breakdown data")
    format: str = Field("pdf", description="Format: pdf or excel")
    include_charts: bool = Field(True, description="Include charts in report")


class DiagramRequest(BaseModel):
    """Request schema for create_architecture_diagram tool"""
    services: List[Dict[str, str]] = Field(
        description="List of services for diagram"
    )
    diagram_format: str = Field(
        "mermaid",
        description="Diagram format: mermaid, plantuml"
    )


# Response schemas
class PriceResult(BaseModel):
    """Single price result"""
    service_name: str
    sku: str
    price: float
    unit: str
    region: str


class CostBreakdownResult(BaseModel):
    """Cost breakdown result"""
    service: str
    monthly_cost: float
    hourly_cost: float
    details: Dict[str, Any]


class RegionComparisonResult(BaseModel):
    """Region comparison result"""
    sku: str
    prices: Dict[str, float]
    cheapest_region: str
    expensive_region: str


# Tool definitions
TOOL_DEFINITIONS = {
    "search_azure_prices": {
        "name": "search_azure_prices",
        "description": "Search for Azure service prices and SKUs. Use this to get pricing information for specific Azure services.",
        "parameters": SearchPricesRequest,
    },
    "calculate_deployment_cost": {
        "name": "calculate_deployment_cost",
        "description": "Calculate total estimated monthly and hourly cost for a deployment across multiple services.",
        "parameters": CalculateCostRequest,
    },
    "compare_regions": {
        "name": "compare_regions",
        "description": "Compare prices for a specific SKU across different Azure regions to find the cheapest option.",
        "parameters": CompareRegionsRequest,
    },
    "create_cost_chart": {
        "name": "create_cost_chart",
        "description": "Create a visualization chart showing cost breakdown by service.",
        "parameters": ChartRequest,
    },
    "generate_cost_report": {
        "name": "generate_cost_report",
        "description": "Generate a professional PDF or Excel report with cost analysis.",
        "parameters": ReportRequest,
    },
    "create_architecture_diagram": {
        "name": "create_architecture_diagram",
        "description": "Generate a Mermaid or PlantUML diagram showing the architecture.",
        "parameters": DiagramRequest,
    },
}


# Azure service categories
AZURE_SERVICES = {
    "compute": [
        "Virtual Machines",
        "Azure Kubernetes Service",
        " Azure Kubernetes Service",
        "App Service",
        "Functions",
        "Azure Batch",
    ],
    "data": [
        "Azure SQL Database",
        "Azure Cosmos DB",
        "Azure Database for PostgreSQL",
        "Azure Database for MySQL",
        "Azure Blob Storage",
    ],
    " cache": [
        "Azure Cache for Redis",
    ],
    "integration": [
        "Azure Event Hubs",
        "Azure Service Bus",
        "Azure Logic Apps",
    ],
    "devops": [
        "Azure DevOps",
        "GitHub Actions",
    ],
    "networking": [
        "Virtual Network",
        "Azure DNS",
        "Azure Load Balancer",
        "Azure Application Gateway",
    ],
    "security": [
        "Azure Key Vault",
        "Azure Security Center",
    ],
}


# Common SKUs by service type
COMMON_SKUS = {
    "Virtual Machines": [
        "Standard_D2s_v3",
        "Standard_D4s_v3",
        "Standard_D8s_v3",
        "Standard_E4s_v3",
        "Standard_E8s_v3",
    ],
    "Azure SQL Database": [
        "GP_Gen5_2",
        "GP_Gen5_4",
        "GP_Gen5_8",
        "BC_Gen5_4",
        "BC_Gen5_8",
    ],
    "Azure Cache for Redis": [
        "Standard C0",
        "Standard C1",
        "Standard C2",
        "Standard C3",
        "Premium P1",
    ],
}