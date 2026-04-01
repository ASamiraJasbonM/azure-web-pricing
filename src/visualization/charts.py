"""
Chart generation for cost visualization
"""

from typing import Dict, List, Any, Optional
import os
from pathlib import Path

# Try to import matplotlib/plotly, but provide fallback
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


class ChartGenerator:
    """Generate charts for cost visualization"""
    
    def __init__(self, output_dir: str = "output/charts"):
        """
        Initialize chart generator
        
        Args:
            output_dir: Directory to save charts
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_bar_chart(
        self,
        data: Dict[str, float],
        title: str = "Cost Breakdown",
        filename: Optional[str] = None
    ) -> str:
        """
        Create a bar chart
        
        Args:
            data: Dictionary of label -> value
            title: Chart title
            filename: Output filename
            
        Returns:
            Path to saved chart
        """
        if not HAS_MATPLOTLIB:
            return "Error: matplotlib not installed"
        
        labels = list(data.keys())
        values = list(data.values())
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        bars = ax.bar(labels, values, color=['#0078D4', '#107C10', '#D83B01', 
                                            '#B4009E', '#00BCF2', '#FFB900'])
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylabel('Monthly Cost (USD)', fontsize=12)
        ax.set_xlabel('Service', fontsize=12)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'${height:.2f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=10)
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Save
        if filename is None:
            filename = f"{title.lower().replace(' ', '_')}.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def create_pie_chart(
        self,
        data: Dict[str, float],
        title: str = "Cost Distribution",
        filename: Optional[str] = None
    ) -> str:
        """
        Create a pie chart
        
        Args:
            data: Dictionary of label -> value
            title: Chart title
            filename: Output filename
            
        Returns:
            Path to saved chart
        """
        if not HAS_MATPLOTLIB:
            return "Error: matplotlib not installed"
        
        labels = list(data.keys())
        values = list(data.values())
        
        colors = ['#0078D4', '#107C10', '#D83B01', '#B4009E', '#00BCF2', '#FFB900']
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors[:len(values)],
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 11}
        )
        
        for text in texts:
            text.set_fontsize(10)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        # Save
        if filename is None:
            filename = f"{title.lower().replace(' ', '_')}_pie.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def create_line_chart(
        self,
        data: Dict[str, float],
        title: str = "Cost Trend",
        filename: Optional[str] = None
    ) -> str:
        """
        Create a line chart for trends
        
        Args:
            data: Dictionary of label -> value
            title: Chart title
            filename: Output filename
            
        Returns:
            Path to saved chart
        """
        if not HAS_MATPLOTLIB:
            return "Error: matplotlib not installed"
        
        labels = list(data.keys())
        values = list(data.values())
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.plot(labels, values, marker='o', linewidth=2, markersize=8,
               color='#0078D4')
        
        ax.fill_between(labels, values, alpha=0.3, color='#0078D4')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylabel('Cost (USD)', fontsize=12)
        ax.set_xlabel('Month', fontsize=12)
        
        # Add value labels
        for i, v in enumerate(values):
            ax.annotate(f'${v:.0f}', xy=(i, v), xytext=(0, 10),
                      textcoords="offset points",
                      ha='center', va='bottom', fontsize=10)
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Save
        if filename is None:
            filename = f"{title.lower().replace(' ', '_')}_trend.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close()
        
        return str(filepath)
    
    def create_stacked_bar(
        self,
        data: Dict[str, Dict[str, float]],
        title: str = "Stacked Cost Chart",
        filename: Optional[str] = None
    ) -> str:
        """
        Create a stacked bar chart
        
        Args:
            data: Dictionary of category -> {subcategory -> value}
            title: Chart title
            filename: Output filename
            
        Returns:
            Path to saved chart
        """
        if not HAS_MATPLOTLIB:
            return "Error: matplotlib not installed"
        
        categories = list(data.keys())
        
        # Get all unique subcategories
        all_subs = set()
        for sub_data in data.values():
            all_subs.update(sub_data.keys())
        subcategories = list(all_subs)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        bottom = [0] * len(categories)
        colors = ['#0078D4', '#107C10', '#D83B01', '#B4009E', '#00BCF2']
        
        for i, subcat in enumerate(subcategories):
            values = []
            for cat in categories:
                values.append(data[cat].get(subcat, 0))
            
            ax.bar(categories, values, bottom=bottom, label=subcat, color=colors[i % len(colors)])
            
            # Update bottom for next subcategory
            bottom = [b + v for b, v in zip(bottom, values)]
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylabel('Cost (USD)', fontsize=12)
        ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
        
        plt.tight_layout()
        
        # Save
        if filename is None:
            filename = f"{title.lower().replace(' ', '_')}_stacked.png"
        
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=100, bbox_inches='tight')
        plt.close()
        
        return str(filepath)


# Singleton
_chart_generator: Optional[ChartGenerator] = None


def get_chart_generator() -> ChartGenerator:
    """Get chart generator instance"""
    global _chart_generator
    if _chart_generator is None:
        _chart_generator = ChartGenerator()
    return _chart_generator