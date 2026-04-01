"""
Pricing tools for MCP server
"""

from typing import Any, Dict, List, Optional
import logging

from ...core.azure_client import AzurePricingAPI, AzureCostCalculator

logger = logging.getLogger(__name__)


class PricingTools:
    """Collection of pricing-related MCP tools"""
    
    def __init__(self):
        self.api = AzurePricingAPI()
        self.calculator = AzureCostCalculator(self.api)
    
    def search_prices(
        self,
        service_name: Optional[str] = None,
        sku: Optional[str] = None,
        region: str = "westus"
    ) -> str:
        """
        Search for Azure service prices
        
        Args:
            service_name: Name of the service
            sku: Specific SKU
            region: Azure region
            
        Returns:
            Formatted price results
        """
        self.api.region = region
        
        if service_name:
            results = self.api.get_service_prices(service_name)
        elif sku:
            results = self.api.get_prices_by_sku(sku)
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
    
    def calculate_cost(
        self,
        services: List[Dict[str, Any]],
        region: str = "westus"
    ) -> str:
        """
        Calculate total cost for a deployment
        
        Args:
            services: List of service configurations
            region: Azure region
            
        Returns:
            Formatted cost breakdown
        """
        self.api.region = region
        
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
        lines = ["💰 Cost Estimate 💰\n"]
        
        for service, details in result.items():
            if service == "summary":
                continue
            
            if "total_monthly" in details:
                lines.append(f"\n{service}:")
                lines.append(f"  Monthly: ${details['total_monthly']:.2f}")
        
        # Add summary
        summary = result.get("summary", {})
        lines.append(f"\n{'='*40}")
        lines.append(f"Total Monthly: ${summary.get('total_monthly_cost_usd', 0):.2f}")
        lines.append(f"Total Hourly: ${summary.get('total_hourly_cost_usd', 0):.2f}")
        
        return "\n".join(lines)
    
    def compare_regions(
        self,
        sku: str,
        regions: Optional[List[str]] = None
    ) -> str:
        """
        Compare prices across regions
        
        Args:
            sku: SKU to compare
            regions: List of regions (default: major regions)
            
        Returns:
            Formatted comparison
        """
        if regions is None:
            regions = [
                "westus", "eastus", "westeurope", 
                "southeastasia", "northeurope"
            ]
        
        results = []
        
        for region in regions:
            self.api.region = region
            prices = self.api.get_prices_by_sku(sku)
            
            if prices:
                price = prices[0].get("retailPrice", 0.0)
                results.append({
                    "region": region,
                    "price": price,
                })
        
        # Sort by price
        results.sort(key=lambda x: x["price"])
        
        # Format output
        lines = [f"📊 Price Comparison for {sku}\n"]
        
        for i, r in enumerate(results):
            marker = "⭐ (cheapest)" if i == 0 else ""
            lines.append(f"  {r['region']}: ${r['price']:.4f}/hour {marker}")
        
        return "\n".join(lines)
    
    def list_available_services(self) -> str:
        """
        List available Azure services
        
        Returns:
            Formatted list of services
        """
        services = [
            "Virtual Machines",
            "Azure SQL Database",
            "Azure Cache for Redis",
            "Azure Kubernetes Service",
            "Container Registry",
            "DNS",
            "Azure DevOps",
            "App Service",
            "Functions",
            "Storage Accounts",
        ]
        
        lines = ["Available Azure Services:\n"]
        for svc in services:
            lines.append(f"  • {svc}")
        
        return "\n".join(lines)


# Singleton instance
_pricing_tools: Optional[PricingTools] = None


def get_pricing_tools() -> PricingTools:
    """Get pricing tools instance"""
    global _pricing_tools
    if _pricing_tools is None:
        _pricing_tools = PricingTools()
    return _pricing_tools