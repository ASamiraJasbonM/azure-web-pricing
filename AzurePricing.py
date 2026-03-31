import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time
from functools import lru_cache
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzurePricingAPI:
    """Azure Retail Prices API client for fetching service pricing data"""
    
    BASE_URL = "https://prices.azure.com/api/retail/prices"
    
    def __init__(self, currency: str = "USD", region: str = "westus"):
        """
        Initialize the Azure Pricing API client
        
        Args:
            currency: Currency code (USD, EUR, GBP, etc.)
            region: Azure region (westus, eastus, etc.)
        """
        self.currency = currency
        self.region = region
        self.cache = {}
        self.cache_expiry = {}
        self.cache_ttl = 3600  # Cache for 1 hour
        
    def _make_request(self, url: str, retries: int = 3) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        for attempt in range(retries):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        return {}
    
    def _build_filter(self, filters: Dict[str, str]) -> str:
        """Build OData filter string"""
        filter_parts = []
        for key, value in filters.items():
            if value:
                filter_parts.append(f"{key} eq '{value}'")
        return " and ".join(filter_parts)
    
    @lru_cache(maxsize=128)
    def _get_prices_cached(self, filter_str: str) -> List[Dict[str, Any]]:
        """Cached version of price fetching"""
        return self._get_prices_with_pagination(filter_str)
    
    def _get_prices_with_pagination(self, filter_str: str) -> List[Dict[str, Any]]:
        """Fetch all pages of pricing data"""
        all_items = []
        url = f"{self.BASE_URL}?$filter={filter_str}&currencyCode={self.currency}"
        
        while url:
            logger.info(f"Fetching: {url}")
            data = self._make_request(url)
            items = data.get("Items", [])
            all_items.extend(items)
            
            # Check for next page
            url = data.get("NextPageLink")
            
            # Rate limiting - be nice to the API
            time.sleep(0.1)
            
        return all_items
    
    def get_service_prices(self, service_name: str) -> List[Dict[str, Any]]:
        """
        Get all prices for a specific service
        
        Args:
            service_name: Name of the service (DNS, Azure DevOps, Kubernetes Service, etc.)
            
        Returns:
            List of price items
        """
        filter_str = self._build_filter({
            "serviceName": service_name,
            "armRegionName": self.region
        })
        
        return self._get_prices_cached(filter_str)
    
    def get_prices_by_sku(self, sku_name: str) -> List[Dict[str, Any]]:
        """
        Get prices for a specific SKU across regions
        
        Args:
            sku_name: ARM SKU name (Standard_D4s_v3, GP_Gen5_2, etc.)
            
        Returns:
            List of price items
        """
        filter_str = f"armSkuName eq '{sku_name}' and currencyCode eq '{self.currency}'"
        return self._get_prices_cached(filter_str)
    
    def get_aks_pricing(self, node_sku: Optional[str] = None) -> Dict[str, Any]:
        """
        Get AKS pricing (cluster management + node VMs)
        
        Args:
            node_sku: Optional VM SKU for node pricing
            
        Returns:
            Dictionary with AKS management fee and node pricing
        """
        result = {
            "management_fee": {"hourly": 0.0, "monthly": 0.0},
            "nodes": [],
            "total": {"hourly": 0.0, "monthly": 0.0}
        }
        
        # AKS management fee (free in most cases)
        aks_prices = self.get_service_prices("Kubernetes Service")
        if aks_prices:
            # AKS cluster management is typically $0.00/hour
            # But we include for completeness
            result["management_fee"]["hourly"] = aks_prices[0].get("retailPrice", 0.0)
            result["management_fee"]["monthly"] = result["management_fee"]["hourly"] * 730  # avg hours/month
        
        # Get node VM pricing if SKU provided
        if node_sku:
            node_prices = self.get_prices_by_sku(node_sku)
            for price in node_prices:
                if price.get("type") == "Consumption":
                    node_info = {
                        "sku": node_sku,
                        "hourly_rate": price.get("retailPrice", 0.0),
                        "region": price.get("armRegionName", self.region),
                        "monthly_rate": price.get("retailPrice", 0.0) * 730
                    }
                    result["nodes"].append(node_info)
                    result["total"]["hourly"] += node_info["hourly_rate"]
                    result["total"]["monthly"] += node_info["monthly_rate"]
        
        # Add management fee to total
        result["total"]["hourly"] += result["management_fee"]["hourly"]
        result["total"]["monthly"] += result["management_fee"]["monthly"]
        
        return result
    
    def get_sql_database_pricing(self, tier: str = "General Purpose", vcores: int = 2) -> List[Dict[str, Any]]:
        """
        Get Azure SQL Database pricing for specific configuration
        
        Args:
            tier: General Purpose, Business Critical, Hyperscale
            vcores: Number of vCores (2, 4, 8, etc.)
            
        Returns:
            List of price items for compute and storage
        """
        result = []
        
        # Map tier to SKU prefix
        tier_map = {
            "General Purpose": "GP_Gen5",
            "Business Critical": "BC_Gen5",
            "Hyperscale": "HS_Gen5"
        }
        
        sku_prefix = tier_map.get(tier, "GP_Gen5")
        sku_name = f"{sku_prefix}_{vcores}"
        
        # Get compute pricing
        compute_prices = self.get_prices_by_sku(sku_name)
        for price in compute_prices:
            if price.get("armRegionName") == self.region:
                result.append({
                    "type": "compute",
                    "description": f"{tier} - {vcores} vCores",
                    "sku": sku_name,
                    "hourly_rate": price.get("retailPrice", 0.0),
                    "unit": price.get("unitOfMeasure", "1 vCore/hour")
                })
        
        return result
    
    def get_devops_pricing(self) -> List[Dict[str, Any]]:
        """Get Azure DevOps licensing costs"""
        prices = self.get_service_prices("Azure DevOps")
        
        devops_costs = []
        for price in prices:
            if self.region in price.get("armRegionName", ""):
                devops_costs.append({
                    "type": price.get("meterName", "license"),
                    "description": price.get("productName", "Azure DevOps"),
                    "price_per_month": price.get("retailPrice", 0.0),
                    "unit": price.get("unitOfMeasure", "1 user/month")
                })
        
        return devops_costs
    
    def get_redis_cache_pricing(self, tier: str = "Standard", size: str = "C0") -> List[Dict[str, Any]]:
        """
        Get Azure Cache for Redis pricing
        
        Args:
            tier: Basic, Standard, Premium
            size: C0, C1, C2, etc.
            
        Returns:
            List of price items
        """
        redis_prices = self.get_service_prices("Azure Cache for Redis")
        
        results = []
        for price in redis_prices:
            sku = price.get("armSkuName", "")
            if sku and tier.lower() in sku.lower() and size.upper() in sku.upper():
                results.append({
                    "tier": tier,
                    "size": size,
                    "sku": sku,
                    "hourly_rate": price.get("retailPrice", 0.0),
                    "monthly_rate": price.get("retailPrice", 0.0) * 730
                })
        
        return results
    
    def get_container_registry_pricing(self, tier: str = "Standard") -> Dict[str, Any]:
        """
        Get Azure Container Registry pricing
        
        Args:
            tier: Basic, Standard, Premium
            
        Returns:
            Dictionary with tier pricing and storage costs
        """
        acr_prices = self.get_service_prices("Container Registry")
        
        result = {
            "tier": tier,
            "tier_cost": 0.0,
            "storage_cost_per_gb": 0.0,
            "storage_free_tier": 0
        }
        
        for price in acr_prices:
            meter_name = price.get("meterName", "")
            if tier.lower() in meter_name.lower():
                result["tier_cost"] = price.get("retailPrice", 0.0) / 730  # Convert monthly to hourly
            elif "storage" in meter_name.lower():
                result["storage_cost_per_gb"] = price.get("retailPrice", 0.0)
                result["storage_free_tier"] = 100  # Free 100GB in Standard tier
        
        return result
    
    def get_dns_pricing(self, zones: int = 1, queries_per_month: int = 1000000) -> Dict[str, Any]:
        """
        Get Azure DNS pricing
        
        Args:
            zones: Number of DNS zones
            queries_per_month: Number of DNS queries per month
            
        Returns:
            Dictionary with zone costs and query costs
        """
        dns_prices = self.get_service_prices("DNS")
        
        zone_cost = 0.0
        query_cost_per_million = 0.0
        
        for price in dns_prices:
            meter_name = price.get("meterName", "")
            if "Zone" in meter_name:
                zone_cost = price.get("retailPrice", 0.0)
            elif "Query" in meter_name:
                query_cost_per_million = price.get("retailPrice", 0.0)
        
        total_cost = (zone_cost * zones) + (query_cost_per_million * (queries_per_month / 1000000))
        
        return {
            "zone_cost": zone_cost,
            "zones": zones,
            "total_zone_cost": zone_cost * zones,
            "query_cost_per_million": query_cost_per_million,
            "queries_per_month": queries_per_month,
            "total_query_cost": query_cost_per_million * (queries_per_month / 1000000),
            "total_monthly_cost": total_cost
        }


class AzureCostCalculator:
    """Helper class to calculate total costs for a project"""
    
    def __init__(self, api_client: AzurePricingAPI):
        self.api = api_client
    
    def calculate_aks_cluster(self, 
                             node_sku: str = "Standard_D2s_v3",
                             node_count: int = 3,
                             nodes_per_vm: int = 1) -> Dict[str, Any]:
        """
        Calculate AKS cluster costs
        
        Args:
            node_sku: VM SKU for nodes
            node_count: Number of nodes
            nodes_per_vm: Number of nodes per VM (typically 1)
        """
        aks_pricing = self.api.get_aks_pricing(node_sku)
        
        result = {
            "cluster_management": aks_pricing["management_fee"],
            "nodes": []
        }
        
        # Calculate per node and total costs
        for node in aks_pricing["nodes"]:
            node_cost = {
                "sku": node["sku"],
                "per_node_hourly": node["hourly_rate"],
                "per_node_monthly": node["monthly_rate"],
                "total_nodes": node_count,
                "total_hourly": node["hourly_rate"] * node_count,
                "total_monthly": node["monthly_rate"] * node_count
            }
            result["nodes"].append(node_cost)
        
        result["total_monthly"] = aks_pricing["total"]["monthly"]
        
        return result
    
    def calculate_entire_project(self, 
                                 usage_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate total project costs
        
        Args:
            usage_config: Dictionary with usage parameters
            
        Returns:
            Complete cost breakdown
        """
        results = {}
        total_monthly = 0.0
        
        # AKS
        if "aks" in usage_config:
            aks = usage_config["aks"]
            aks_costs = self.calculate_aks_cluster(
                node_sku=aks.get("node_sku", "Standard_D2s_v3"),
                node_count=aks.get("node_count", 3)
            )
            results["Azure Kubernetes Service (AKS)"] = aks_costs
            total_monthly += aks_costs["total_monthly"]
        
        # Azure SQL Database
        if "sql" in usage_config:
            sql = usage_config["sql"]
            sql_costs = self.api.get_sql_database_pricing(
                tier=sql.get("tier", "General Purpose"),
                vcores=sql.get("vcores", 2)
            )
            results["Azure SQL Database"] = {
                "compute": sql_costs,
                "total_monthly": sum(c["hourly_rate"] for c in sql_costs) * 730
            }
            total_monthly += results["Azure SQL Database"]["total_monthly"]
        
        # Azure DevOps
        if "devops" in usage_config:
            devops = usage_config["devops"]
            devops_costs = self.api.get_devops_pricing()
            if devops_costs:
                users = devops.get("users", 5)
                monthly_cost = users * devops_costs[0]["price_per_month"]
                results["Azure DevOps"] = {
                    "users": users,
                    "price_per_user": devops_costs[0]["price_per_month"],
                    "total_monthly": monthly_cost
                }
                total_monthly += monthly_cost
        
        # Azure Cache for Redis
        if "redis" in usage_config:
            redis = usage_config["redis"]
            redis_costs = self.api.get_redis_cache_pricing(
                tier=redis.get("tier", "Standard"),
                size=redis.get("size", "C0")
            )
            if redis_costs:
                results["Azure Cache for Redis"] = {
                    "config": redis_costs[0],
                    "total_monthly": redis_costs[0]["monthly_rate"]
                }
                total_monthly += redis_costs[0]["monthly_rate"]
        
        # Azure Container Registry
        if "acr" in usage_config:
            acr = usage_config["acr"]
            acr_costs = self.api.get_container_registry_pricing(
                tier=acr.get("tier", "Standard")
            )
            storage_gb = acr.get("storage_gb", 100)
            storage_cost = max(0, storage_gb - acr_costs["storage_free_tier"]) * acr_costs["storage_cost_per_gb"]
            
            results["Azure Container Registry"] = {
                "tier": acr_costs["tier"],
                "tier_monthly": acr_costs["tier_cost"] * 730,
                "storage_gb": storage_gb,
                "storage_cost_monthly": storage_cost,
                "total_monthly": (acr_costs["tier_cost"] * 730) + storage_cost
            }
            total_monthly += results["Azure Container Registry"]["total_monthly"]
        
        # Azure DNS
        if "dns" in usage_config:
            dns = usage_config["dns"]
            dns_costs = self.api.get_dns_pricing(
                zones=dns.get("zones", 1),
                queries_per_month=dns.get("queries_per_month", 1000000)
            )
            results["Azure DNS"] = dns_costs
            total_monthly += dns_costs["total_monthly"]
        
        # Add summary
        results["summary"] = {
            "total_monthly_cost_usd": total_monthly,
            "currency": self.api.currency,
            "region": self.api.region,
            "total_hourly_cost_usd": total_monthly / 730
        }
        
        return results


# Example usage for your AI agent
def main():
    """Example of using the Azure Pricing API for your services"""
    
    # Initialize the API client (change region as needed)
    api = AzurePricingAPI(currency="USD", region="westus")
    calculator = AzureCostCalculator(api)
    
    # Define your project configuration
    project_config = {
        "aks": {
            "node_sku": "Standard_D2s_v3",  # 2 vCPUs, 8GB RAM
            "node_count": 3
        },
        "sql": {
            "tier": "General Purpose",
            "vcores": 2
        },
        "devops": {
            "users": 5  # Basic license for 5 users (first 5 free)
        },
        "redis": {
            "tier": "Standard",
            "size": "C0"  # 250MB cache
        },
        "acr": {
            "tier": "Standard",
            "storage_gb": 100  # Standard includes 100GB free
        },
        "dns": {
            "zones": 1,
            "queries_per_month": 1000000  # 1M queries/month
        }
    }
    
    # Calculate costs
    print("Calculating Azure costs for your project...")
    print("=" * 60)
    
    costs = calculator.calculate_entire_project(project_config)
    
    # Pretty print results
    for service, details in costs.items():
        if service != "summary":
            print(f"\n{service}:")
            if "total_monthly" in details:
                print(f"  Monthly Total: ${details['total_monthly']:.2f}")
            
            # Show specific details based on service type
            if service == "Azure Kubernetes Service (AKS)":
                for node in details["nodes"]:
                    print(f"  Nodes: {node['total_nodes']} x {node['sku']} = ${node['total_monthly']:.2f}/month")
                print(f"  Cluster Total: ${details['total_monthly']:.2f}/month")
            
            elif service == "Azure SQL Database":
                for comp in details["compute"]:
                    print(f"  {comp['description']}: ${comp['hourly_rate'] * 730:.2f}/month")
            
            elif service == "Azure DevOps":
                if details['users'] <= 5:
                    print(f"  First {details['users']} users free (Basic license)")
                else:
                    print(f"  {details['users']} users at ${details['price_per_user']:.2f}/user = ${details['total_monthly']:.2f}/month")
            
            elif service == "Azure Cache for Redis":
                print(f"  {details['config']['tier']} {details['config']['size']}: ${details['config']['monthly_rate']:.2f}/month")
            
            elif service == "Azure Container Registry":
                print(f"  {details['tier']} tier: ${details['tier_monthly']:.2f}/month")
                print(f"  Storage ({details['storage_gb']} GB): ${details['storage_cost_monthly']:.2f}/month")
            
            elif service == "Azure DNS":
                print(f"  DNS Zones ({details['zones']}): ${details['total_zone_cost']:.2f}/month")
                print(f"  DNS Queries ({details['queries_per_month']:,}): ${details['total_query_cost']:.2f}/month")
    
    # Print summary
    print("\n" + "=" * 60)
    print("PROJECT SUMMARY")
    print(f"Region: {costs['summary']['region']}")
    print(f"Currency: {costs['summary']['currency']}")
    print(f"Total Hourly: ${costs['summary']['total_hourly_cost_usd']:.2f}/hour")
    print(f"Total Monthly: ${costs['summary']['total_monthly_cost_usd']:.2f}/month")
    print("=" * 60)


if __name__ == "__main__":
    main()