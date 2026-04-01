"""
Command-line interface for Azure Cost Agent
"""

import sys
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.azure_client import AzurePricingAPI, AzureCostCalculator
from src.reports.pdf_generator import PDFReportGenerator, SimpleTextReport
from src.reports.excel_generator import ExcelReportGenerator
from src.visualization.charts import ChartGenerator


class AzureCostCLI:
    """Command-line interface for Azure Cost Agent"""
    
    def __init__(self, region: str = "westus", currency: str = "USD"):
        """
        Initialize CLI
        
        Args:
            region: Default Azure region
            currency: Default currency
        """
        self.region = region
        self.currency = currency
        
        self.api = AzurePricingAPI(currency=currency, region=region)
        self.calculator = AzureCostCalculator(self.api)
    
    def print_banner(self):
        """Print welcome banner"""
        print("=" * 60)
        print("  Azure Cost Agent - CLI")
        print("  Estimate Azure service costs with AI-powered insights")
        print("=" * 60)
        print()
    
    def print_help(self):
        """Print help message"""
        print("Available commands:")
        print("  prices <service>    - Search for service prices")
        print("  sku <sku_name>      - Search by SKU")
        print("  aks                 - Estimate AKS cluster cost")
        print("  sql                 - Estimate SQL Database cost")
        print("  redis               - Estimate Redis cache cost")
        print("  calculate           - Calculate custom deployment")
        print("  compare <sku>       - Compare prices across regions")
        print("  report              - Generate PDF/Excel report")
        print("  chart               - Generate cost chart")
        print("  help                - Show this help")
        print("  exit                - Exit")
        print()
    
    def cmd_prices(self, service: str) -> str:
        """Search prices"""
        results = self.api.get_service_prices(service)
        
        if not results:
            return f"No results found for {service}"
        
        lines = [f"Results for {service}:"]
        for item in results[:10]:
            price = item.get("retailPrice", 0.0)
            lines.append(
                f"  {item.get('armSkuName')}: ${price:.4f}/"
                f"{item.get('unitOfMeasure', 'hour')}"
            )
        
        return "\n".join(lines)
    
    def cmd_sku(self, sku: str) -> str:
        """Search by SKU"""
        results = self.api.get_prices_by_sku(sku)
        
        if not results:
            return f"No results found for SKU {sku}"
        
        lines = [f"Results for {sku}:"]
        for item in results[:10]:
            price = item.get("retailPrice", 0.0)
            lines.append(
                f"  {item.get('armRegionName')}: ${price:.4f}/"
                f"{item.get('unitOfMeasure', 'hour')}"
            )
        
        return "\n".join(lines)
    
    def cmd_aks(
        self,
        node_sku: str = "Standard_D2s_v3",
        node_count: int = 3
    ) -> str:
        """Estimate AKS cluster cost"""
        result = self.calculator.calculate_aks_cluster(
            node_sku=node_sku,
            node_count=node_count
        )
        
        cost = result.get("total_monthly", 0)
        
        lines = [
            f"AKS Cluster Estimate ({node_count} x {node_sku}):",
            f"  Monthly: ${cost:.2f}",
            f"  Hourly: ${cost/730:.2f}",
        ]
        
        return "\n".join(lines)
    
    def cmd_sql(
        self,
        tier: str = "General Purpose",
        vcores: int = 2
    ) -> str:
        """Estimate SQL Database cost"""
        results = self.api.get_sql_database_pricing(tier=tier, vcores=vcores)
        
        if not results:
            return f"No pricing found for {tier} {vcores}vCores"
        
        cost = results[0].get("hourly_rate", 0) * 730
        
        lines = [
            f"Azure SQL Database ({tier} {vcores}vCores):",
            f"  Monthly: ${cost:.2f}",
            f"  Hourly: ${cost/730:.2f}",
        ]
        
        return "\n".join(lines)
    
    def cmd_redis(self, tier: str = "Standard", size: str = "C0") -> str:
        """Estimate Redis cost"""
        results = self.api.get_redis_cache_pricing(tier=tier, size=size)
        
        if not results:
            return f"No pricing found for Redis {tier} {size}"
        
        cost = results[0].get("monthly_rate", 0)
        
        lines = [
            f"Azure Cache for Redis ({tier} {size}):",
            f"  Monthly: ${cost:.2f}",
        ]
        
        return "\n".join(lines)
    
    def cmd_compare(self, sku: str, regions: list = None) -> str:
        """Compare prices across regions"""
        if regions is None:
            regions = ["westus", "eastus", "westeurope", "southeastasia"]
        
        results = []
        
        for region in regions:
            self.api.region = region
            prices = self.api.get_prices_by_sku(sku)
            
            if prices:
                price = prices[0].get("retailPrice", 0)
                results.append({"region": region, "price": price})
        
        results.sort(key=lambda x: x["price"])
        
        lines = [f"Price comparison for {sku}:"]
        for i, r in enumerate(results):
            marker = " (cheapest)" if i == 0 else ""
            lines.append(f"  {r['region']}: ${r['price']:.4f}/hour{marker}")
        
        return "\n".join(lines)
    
    def cmd_report(self, services: Dict[str, Any], format: str = "pdf") -> str:
        """Generate report"""
        result = self.calculator.calculate_entire_project(services)
        
        if format == "pdf":
            generator = PDFReportGenerator()
            return generator.generate_report(result)
        elif format == "excel":
            generator = ExcelReportGenerator()
            return generator.generate_report(result)
        else:
            generator = SimpleTextReport()
            return generator.generate_report(result)
    
    def cmd_chart(self, services: Dict[str, Any]) -> str:
        """Generate chart"""
        # Build cost data
        cost_data = {}
        
        if "aks" in services:
            result = self.calculator.calculate_aks_cluster(
                node_sku=services["aks"].get("node_sku", "Standard_D2s_v3"),
                node_count=services["aks"].get("node_count", 3)
            )
            cost_data["AKS"] = result.get("total_monthly", 0)
        
        # Add to charts
        if cost_data:
            generator = ChartGenerator()
            filepath = generator.create_bar_chart(cost_data, "Azure Cost Breakdown")
            return f"Chart saved to: {filepath}"
        
        return "No data to chart"
    
    def run_interactive(self):
        """Run interactive mode"""
        self.print_banner()
        self.print_help()
        
        while True:
            try:
                user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["exit", "quit", "salir"]:
                    print("Goodbye!")
                    break
                
                if user_input.lower() == "help":
                    self.print_help()
                    continue
                
                # Simple parsing
                parts = user_input.split()
                cmd = parts[0].lower()
                
                if cmd == "prices" and len(parts) > 1:
                    print(self.cmd_prices(" ".join(parts[1:])))
                elif cmd == "sku" and len(parts) > 1:
                    print(self.cmd_sku(parts[1]))
                elif cmd == "aks":
                    node_sku = parts[1] if len(parts) > 1 else "Standard_D2s_v3"
                    node_count = int(parts[2]) if len(parts) > 2 else 3
                    print(self.cmd_aks(node_sku, node_count))
                elif cmd == "sql":
                    print(self.cmd_sql("General Purpose", 2))
                elif cmd == "redis":
                    print(self.cmd_redis())
                elif cmd == "compare" and len(parts) > 1:
                    print(self.cmd_compare(parts[1]))
                else:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


async def main():
    """Main entry point"""
    cli = AzureCostCLI()
    cli.run_interactive()


if __name__ == "__main__":
    asyncio.run(main())