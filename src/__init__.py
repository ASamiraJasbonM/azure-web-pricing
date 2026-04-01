"""
Azure Cost Agent - AI-powered Azure cost estimation tool

This package provides:
- Azure pricing API integration
- MCP server with pricing tools
- AI agent with LangGraph
- Visualization and reporting capabilities
"""

__version__ = "0.1.0"
__author__ = "Azure Cost Agent Team"

from src.core.azure_client import AzurePricingAPI, AzureCostCalculator

__all__ = [
    "AzurePricingAPI",
    "AzureCostCalculator",
]