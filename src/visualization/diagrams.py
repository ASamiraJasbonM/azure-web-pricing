"""
Diagram generation for architecture visualization
"""

from typing import Dict, List, Any, Optional
from pathlib import Path


class DiagramGenerator:
    """Generate architecture diagrams"""
    
    def __init__(self, output_dir: str = "output/charts"):
        """
        Initialize diagram generator
        
        Args:
            output_dir: Directory to save diagrams
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_mermaid_flowchart(
        self,
        services: List[Dict[str, str]],
        title: str = "Architecture"
    ) -> str:
        """
        Create a Mermaid flowchart
        
        Args:
            services: List of services with 'name' and optional 'connects_to'
            title: Diagram title
            
        Returns:
            Mermaid diagram code
        """
        lines = ["flowchart TD"]
        
        # Add nodes
        for service in services:
            name = service.get("name", "Unknown")
            node_id = name.lower().replace(" ", "_")
            lines.append(f"    {node_id}[{name}]")
        
        # Add connections
        for service in services:
            name = service.get("name", "Unknown")
            node_id = name.lower().replace(" ", "_")
            
            connects_to = service.get("connects_to", [])
            if isinstance(connects_to, str):
                connects_to = [connects_to]
            
            for target in connects_to:
                target_id = target.lower().replace(" ", "_")
                lines.append(f"    {node_id} --> {target_id}")
        
        return "\n".join(lines)
    
    def create_mermaid_sequence(
        self,
        participants: List[str],
        interactions: List[Dict[str, str]]
    ) -> str:
        """
        Create a Mermaid sequence diagram
        
        Args:
            participants: List of participant names
            interactions: List of {from, to, message} dicts
            
        Returns:
            Mermaid diagram code
        """
        lines = ["sequenceDiagram"]
        
        # Add participants
        for p in participants:
            lines.append(f"    participant {p}")
        
        # Add interactions
        for interaction in interactions:
            frm = interaction.get("from", "")
            to = interaction.get("to", "")
            msg = interaction.get("message", "")
            
            if frm and to and msg:
                lines.append(f"    {frm}->>{to}: {msg}")
        
        return "\n".join(lines)
    
    def create_mermaid_class(
        self,
        classes: List[Dict[str, Any]]
    ) -> str:
        """
        Create a Mermaid class diagram
        
        Args:
            classes: List of class definitions
            
        Returns:
            Mermaid diagram code
        """
        lines = ["classDiagram"]
        
        for cls in classes:
            name = cls.get("name", "Class")
            lines.append(f"    class {name}{{")
            
            # Add properties
            for prop in cls.get("properties", []):
                lines.append(f"        +{prop}")
            
            # Add methods
            for method in cls.get("methods", []):
                lines.append(f"        +{method}()")
            
            lines.append(f"    }}")
        
        return "\n".join(lines)
    
    def create_architecture_mermaid(
        self,
        services: List[Dict[str, Any]]
    ) -> str:
        """
        Create an architecture diagram for Azure services
        
        Args:
            services: List of service configs with type, name, tier, etc.
            
        Returns:
            Mermaid diagram code
        """
        lines = ["flowchart TB"]
        
        # Define subgraphs for layers
        lines.append("    subgraph compute[Compute]")
        lines.append("    end")
        lines.append("    subgraph data[Data]")
        lines.append("    end")
        lines.append("    subgraph cache[Cache]")
        lines.append("    end")
        lines.append("    subgraph network[Networking]")
        lines.append("    end")
        
        # Add services to layers
        compute_services = []
        data_services = []
        cache_services = []
        
        for service in services:
            svc_type = service.get("type", "").lower()
            name = service.get("name", "Service")
            node_id = name.lower().replace(" ", "_").replace("-", "_")
            
            if "aks" in svc_type or "k8s" in svc_type or "vm" in svc_type:
                lines.append(f"        {node_id}[{name}]")
                compute_services.append(node_id)
            elif "sql" in svc_type or "cosmos" in svc_type or "blob" in svc_type:
                lines.append(f"        {node_id}[{name}]")
                data_services.append(node_id)
            elif "redis" in svc_type or "cache" in svc_type:
                lines.append(f"        {node_id}[{name}]")
                cache_services.append(node_id)
            else:
                lines.append(f"        {node_id}[{name}]")
        
        lines.append("")
        
        # Add direction arrows between layers
        if compute_services and data_services:
            lines.append(f"    compute --> data")
        
        if data_services and cache_services:
            lines.append(f"    data --> cache")
        
        return "\n".join(lines)
    
    def save_mermaid_svg(
        self,
        mermaid_code: str,
        filename: str
    ) -> str:
        """
        Save Mermaid code to file
        
        Args:
            mermaid_code: Mermaid diagram code
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        filepath = self.output_dir / filename
        
        with open(filepath, "w") as f:
            f.write("# Architecture Diagram\n\n")
            f.write("```mermaid\n")
            f.write(mermaid_code)
            f.write("\n```\n")
        
        return str(filepath)
    
    def create_plantuml(
        self,
        services: List[Dict[str, str]]
    ) -> str:
        """
        Create PlantUML diagram
        
        Args:
            services: List of services
            
        Returns:
            PlantUML diagram code
        """
        lines = ["@startuml"]
        
        # Add nodes
        for service in services:
            name = service.get("name", "Service")
            node_type = service.get("type", "node").upper()
            
            lines.append(f"{node_type} {name}{{")
            lines.append(f"  {name}")
            lines.append(f"}}")
        
        # Add connections
        for service in services:
            name = service.get("name", "Unknown")
            connects_to = service.get("connects_to", [])
            
            for target in connects_to:
                lines.append(f"{name} --> {target}")
        
        lines.append("@enduml")
        
        return "\n".join(lines)


# Functions for easy diagram creation
def create_azure_architecture_diagram(
    services: List[Dict[str, Any]]
) -> str:
    """
    Create a simple architecture diagram for Azure services
    
    Args:
        services: List of service configurations
        
    Returns:
        Mermaid diagram code
    """
    generator = DiagramGenerator()
    return generator.create_architecture_mermaid(services)


def create_flowchart(
    services: List[Dict[str, str]]
) -> str:
    """
    Create a simple flowchart
    
    Args:
        services: List of service configs
        
    Returns:
        Mermaid diagram code
    """
    generator = DiagramGenerator()
    return generator.create_mermaid_flowchart(services)


# Singleton instance
_diagram_generator: Optional[DiagramGenerator] = None


def get_diagram_generator() -> DiagramGenerator:
    """Get diagram generator instance"""
    global _diagram_generator
    if _diagram_generator is None:
        _diagram_generator = DiagramGenerator()
    return _diagram_generator