"""
MCP Server for Azure pricing tools
"""

from typing import Any, Dict, List, Optional
import asyncio
import logging

from pydantic import BaseModel, Field

from ..core.azure_client import AzurePricingAPI, AzureCostCalculator
from ..core.models import AZURE_REGIONS, VM_SKUS, SQL_SKUS, REDIS_SKUS

logger = logging.getLogger(__name__)


# Tool input schemas
class SearchPricesInput(BaseModel):
    """Input for search_azure_prices tool"""
    service_name: Optional[str] = Field(
        None,
        description="Name of the service (e.g., 'Virtual Machines', 'Azure SQL Database')"
    )
    sku: Optional[str] = Field(
        None,
        description="Specific SKU (e.g., 'Standard_D2s_v3', 'GP_Gen5_2')"
    )
    region: str = Field(
        "westus",
        description="Azure region (e.g., 'westus', 'eastus')"
    )


class CalculateCostInput(BaseModel):
    """Input for calculate_deployment_cost tool"""
    services: List[Dict[str, Any]] = Field(
        description="List of services with configurations"
    )
    region: str = Field("westus", description="Azure region")


class CompareRegionsInput(BaseModel):
    """Input for compare_regions tool"""
    sku: str = Field(description="SKU to compare")
    regions: List[str] = Field(
        default=["westus", "eastus", "westeurope", "southeastasia"],
        description="Regions to compare"
    )


class ChartInput(BaseModel):
    """Input for create_cost_chart tool"""
    data: Dict[str, float] = Field(description="Cost data for chart")
    chart_type: str = Field(
        "bar",
        description="Chart type: bar, pie, line"
    )
    title: str = Field("Azure Cost Breakdown", description="Chart title")


class ReportInput(BaseModel):
    """Input for generate_cost_report tool"""
    cost_data: Dict[str, Any] = Field(description="Cost breakdown data")
    format: str = Field("pdf", description="Report format: pdf, excel")
    include_charts: bool = Field(True, description="Include charts in report")


# MCP Server class
class AzurePricingServer:
    """MCP Server for Azure pricing operations"""
    
    def __init__(self):
        self.azure_api = AzurePricingAPI()
        self.calculator = AzureCostCalculator(self.azure_api)
        self._tools = self._register_tools()
    
    def _register_tools(self) -> Dict[str, Any]:
        """Register all available tools"""
        return {
            "search_azure_prices": {
                "name": "search_azure_prices",
                "description": "Search for Azure service prices. Use this to find pricing information for specific Azure services or SKUs.",
                "input_schema": SearchPricesInput.model_json_schema(),
                "handler": self._handle_search_prices,
            },
            "calculate_deployment_cost": {
                "name": "calculate_deployment_cost",
                "description": "Calculate total cost for a deployment with multiple services.",
                "input_schema": CalculateCostInput.model_json_schema(),
                "handler": self._handle_calculate_cost,
            },
            "compare_regions": {
                "name": "compare_regions",
                "description": "Compare prices for a SKU across different Azure regions.",
                "input_schema": CompareRegionsInput.model_json_schema(),
                "handler": self._handle_compare_regions,
            },
            "create_cost_chart": {
                "name": "create_cost_chart",
                "description": "Create a visualization chart of cost breakdown.",
                "input_schema": ChartInput.model_json_schema(),
                "handler": self._handle_create_chart,
            },
            "generate_cost_report": {
                "name": "generate_cost_report",
                "description": "Generate a PDF or Excel report with cost analysis.",
                "input_schema": ReportInput.model_json_schema(),
                "handler": self._handle_generate_report,
            },
        }
    
    def list_tools(self) -> List[Dict[str, str]]:
        """List all available tools"""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
            }
            for tool in self._tools.values()
        ]
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> str:
        """Call a specific tool"""
        if tool_name not in self._tools:
            return f"Error: Tool '{tool_name}' not found"
        
        tool = self._tools[tool_name]
        handler = tool["handler"]
        
        try:
            result = await handler(arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return f"Error: {str(e)}"
    
    async def _handle_search_prices(self, args: Dict[str, Any]) -> str:
        """Handle price search"""
        input_data = SearchPricesInput(**args)
        self.azure_api.region = input_data.region
        
        if input_data.service_name:
            results = self.azure_api.get_service_prices(input_data.service_name)
        elif input_data.sku:
            results = self.azure_api.get_prices_by_sku(input_data.sku)
        else:
            return "Error: Must specify service_name or sku"
        
        if not results:
            return f"No results found for the query"
        
        # Format results
        formatted = []
        for item in results[:10]:
            price = item.get("retailPrice", 0.0)
            formatted.append(
                f"• {item.get('serviceName', 'N/A')} - {item.get('armSkuName', 'N/A')}\n"
                f"  Price: ${price:.4f} per {item.get('unitOfMeasure', 'hour')}\n"
                f"  Region: {item.get('armRegionName', 'N/A')}\n"
            )
        
        return f"Found {len(results)} results:\n\n" + "\n".join(formatted)
    
    async def _handle_calculate_cost(self, args: Dict[str, Any]) -> str:
        """Handle cost calculation"""
        input_data = CalculateCostInput(**args)
        self.azure_api.region = input_data.region
        
        services = input_data.services
        
        # Build usage config
        usage_config = {}
        
        for service in services:
            service_type = service.get("type", "").lower()
            
            if "aks" in service_type or "kubernetes" in service_type:
                usage_config["aks"] = {
                    "node_sku": service.get("sku", "Standard_D2s_v3"),
                    "node_count": service.get("quantity", 3),
                }
            
            elif "sql" in service_type:
                tier = service.get("tier", "General Purpose")
                vcores = service.get("vcores", 2)
                usage_config["sql"] = {
                    "tier": tier,
                    "vcores": vcores,
                }
            
            elif "redis" in service_type:
                usage_config["redis"] = {
                    "tier": service.get("tier", "Standard"),
                    "size": service.get("size", "C0"),
                }
            
            elif "acr" in service_type:
                usage_config["acr"] = {
                    "tier": service.get("tier", "Standard"),
                    "storage_gb": service.get("storage_gb", 100),
                }
            
            elif "devops" in service_type:
                usage_config["devops"] = {
                    "users": service.get("users", 5),
                }
            
            elif "dns" in service_type:
                usage_config["dns"] = {
                    "zones": service.get("zones", 1),
                    "queries_per_month": service.get("queries", 1000000),
                }
        
        # Calculate
        result = self.calculator.calculate_entire_project(usage_config)
        
        # Format output
        lines = ["💰 **Cost Estimate** 💰\n"]
        
        for service, details in result.items():
            if service == "summary":
                continue
            
            if "total_monthly" in details:
                lines.append(f"\n{service}:")
                lines.append(f"  Monthly: ${details['total_monthly']:.2f}")
        
        # Add summary
        summary = result.get("summary", {})
        lines.append(f"\n{'='*40}")
        lines.append(f"💵 **Total Monthly**: ${summary.get('total_monthly_cost_usd', 0):.2f}")
        lines.append(f"💵 **Total Hourly**: ${summary.get('total_hourly_cost_usd', 0):.2f}")
        
        return "\n".join(lines)
    
    async def _handle_compare_regions(self, args: Dict[str, Any]) -> str:
        """Handle region comparison"""
        input_data = CompareRegionsInput(**args)
        
        results = []
        
        for region in input_data.regions:
            self.azure_api.region = region
            prices = self.azure_api.get_prices_by_sku(input_data.sku)
            
            if prices:
                price = prices[0].get("retailPrice", 0.0)
                results.append({
                    "region": region,
                    "price": price,
                })
        
        # Sort by price
        results.sort(key=lambda x: x["price"])
        
        # Format output
        lines = [f"📊 **Price Comparison for {input_data.sku}**\n"]
        
        for i, r in enumerate(results):
            marker = "⭐ (cheapest)" if i == 0 else ""
            lines.append(f"  {r['region']}: ${r['price']:.4f}/hour {marker}")
        
        return "\n".join(lines)
    
    async def _handle_create_chart(self, args: Dict[str, Any]) -> str:
        """Handle chart creation"""
        # This would integrate with visualization module
        return "Chart creation requires matplotlib/plotly. Use generate_cost_report with include_charts=True instead."
    
    async def _handle_generate_report(self, args: Dict[str, Any]) -> str:
        """Handle report generation"""
        # This would integrate with reports module
        return "Report generation requires reportlab/openpyxl. Install dependencies and use report generation module."


# Server singleton
_server: Optional[AzurePricingServer] = None


def get_server() -> AzurePricingServer:
    """Get server instance"""
    global _server
    if _server is None:
        _server = AzurePricingServer()
    return _server


async def main():
    """Main entry point for MCP server"""
    server = get_server()
    print("Azure Pricing MCP Server started")
    print(f"Available tools: {len(server.list_tools())}")
    
    for tool in server.list_tools():
        print(f"  - {tool['name']}: {tool['description']}")
    
    # Keep server running
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())