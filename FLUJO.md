# Flujo del Azure Cost Agent — Guía Completa de Implementación

## Índice

1. [Visión General del Flujo](#1-visión-general-del-flujo)
2. [Flujo Principal: Consulta de Precios](#2-flujo-principal-consulta-de-precios)
3. [Flujo de Cálculo Multi-Servicio](#3-flujo-de-cálculo-multi-servicio)
4. [Flujo de Generación de Reportes](#4-flujo-de-generación-de-reportes)
5. [Sistema de Caché](#5-sistema-de-caché)
6. [Comunicación entre Componentes](#6-comunicación-entre-componentes)
7. [Guía de Implementación Paso a Paso](#7-guía-de-implementación-paso-a-paso)
8. [Extensibilidad: Cómo Agregar Funcionalidades](#8-extensibilidad-cómo-agregar-funcionalidades)
9. [Dependencias y Configuración](#9-dependencias-y-configuración)
10. [Debugging y Troubleshooting](#10-debugging-y-troubleshooting)

---

## 1. Visión General del Flujo

El **Azure Cost Agent** opera en 3 modos principales:

```
                    ┌──────────────────┐
                    │   ENTRADA         │
                    │ CLI / API / MCP   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────────┐
        │  CLI     │  │ FastAPI  │  │  Agente IA   │
        │interactiva│  │  REST   │  │  (LangChain)  │
        └────┬─────┘  └────┬─────┘  └──────┬───────┘
             │              │               │
             └──────────────┼───────────────┘
                            ▼
                   ┌─────────────────┐
                   │   MCP SERVER    │  ← Orquestador central
                   │ server.py       │
                   └────────┬────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐ ┌──────────┐ ┌──────────────┐
        │ Pricing  │ │  Charts  │ │   Reports    │
        │  Tools   │ │Generator │ │  Generator   │
        └────┬─────┘ └──────────┘ └──────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌──────────┐    ┌──────────┐
│Azure API │    │  Cache   │
│ Client   │◄──►│  System  │
└────┬─────┘    └──────────┘
     │
     ▼
┌──────────────────┐
│ Azure Retail     │
│ Prices API       │
│ (HTTPS GET)      │
└──────────────────┘
```

## 2. Flujo Principal: Consulta de Precios

Este es el flujo más simple y el que más se ejecuta.

### Paso a paso

```
Paso 1 ─── Usuario escribe: prices Virtual Machines
              │
Paso 2 ─── CLI.parse_input("prices Virtual Machines")
              │ cmd = "prices", args = "Virtual Machines"
              ▼
Paso 3 ─── AzureCostCLI.cmd_prices("Virtual Machines")
              │ self.api.get_service_prices("Virtual Machines")
              ▼
Paso 4 ─── AzurePricingAPI.get_service_prices("Virtual Machines")
              │
              ├──► _build_filter({"serviceName": "Virtual Machines", 
              │                    "armRegionName": "westus"})
              │    → "serviceName eq 'Virtual Machines' and armRegionName eq 'westus'"
              │
              ├──► _get_prices_cached(filter_str)
              │         │
              │         ├──► LRU Cache HIT? → retorna datos cacheados
              │         │
              │         └──► MISS → _get_prices_with_pagination(filter_str)
              │                        │
              │                        ├──► _make_request(url)
              │                        │    GET https://prices.azure.com/api/retail/prices
              │                        │         ?$filter=...&currencyCode=USD
              │                        │    → response.json()
              │                        │
              │                        ├──► Paginación: sigue NextPageLink
              │                        │
              │                        └──► Retorna List[Dict]
              │
              ▼
Paso 5 ─── Formateo de resultados (top 10 items)
              │
              ▼
Paso 6 ─── Output al usuario:
              Results for Virtual Machines:
                Standard_D2s_v3: $0.0960/hour
                Standard_D4s_v3: $0.1920/hour
                ...
```

### Código equivalente

```python
# Lo mínimo para este flujo
from src.core.azure_client import AzurePricingAPI

api = AzurePricingAPI(currency="USD", region="westus")
results = api.get_service_prices("Virtual Machines")

for item in results[:5]:
    print(f"{item['armSkuName']}: ${item['retailPrice']}/hour")
```

## 3. Flujo de Cálculo Multi-Servicio

El flujo más complejo: estimar costo de un proyecto completo.

### Diagrama de secuencia

```
CLI              MCP Server         PricingTools      AzureClient         Cache        Azure API
 │                   │                   │                 │                │              │
 │ calculate AKS+SQL+Redis              │                 │                │              │
 │──────────────────►│                   │                 │                │              │
 │                   │ call_tool()       │                 │                │              │
 │                   │──────────────────►│                 │                │              │
 │                   │                   │ calculate_cost()│                │              │
 │                   │                   │────────────────►│                │              │
 │                   │                   │                 │                │              │
 │                   │                   │  ┌─── Para AKS: │                │              │
 │                   │                   │  │   calculate_aks_cluster()     │              │
 │                   │                   │  │──────────────►│               │              │
 │                   │                   │  │               │ get_aks_pricing()           │
 │                   │                   │  │               │──────────────►│              │
 │                   │                   │  │               │               │ cache.get()  │
 │                   │                   │  │               │               │─────────────►│
 │                   │                   │  │               │               │◄── MISS ────││
 │                   │                   │  │               │               │ GET /prices  │
 │                   │                   │  │               │               │─────────────►│
 │                   │                   │  │               │               │◄─── data ───││
 │                   │                   │  │               │               │ cache.set()  │
 │                   │                   │  │               │◄──────────────│              │
 │                   │                   │  │◄──────────────│               │              │
 │                   │                   │  │               │                │              │
 │                   │                   │  ├─── Para SQL: │                │              │
 │                   │                   │  │   get_sql_database_pricing()  │              │
 │                   │                   │  │──────────────►│               │              │
 │                   │                   │  │               │──────────────►│              │
 │                   │                   │  │               │◄── cache HIT ─│              │
 │                   │                   │  │◄──────────────│               │              │
 │                   │                   │  │               │                │              │
 │                   │                   │  ├─── Para Redis:                │              │
 │                   │                   │  │   get_redis_cache_pricing()   │              │
 │                   │                   │  │──────────────►│               │              │
 │                   │                   │  │               │──────────────►│              │
 │                   │                   │  │               │◄── cache HIT ─│              │
 │                   │                   │  │◄──────────────│               │              │
 │                   │                   │  │               │                │              │
 │                   │                   │  │ calculate_entire_project()     │              │
 │                   │                   │  │ agrega totales                │              │
 │                   │                   │◄─┴──────────────│               │              │
 │                   │◄──────────────────│                 │                │              │
 │◄──────────────────│                   │                 │                │              │
 │                                                                           │              │
 │ 💰 Total: $368.38/month                                                  │              │
```

### Estructura de datos del resultado

```python
# Lo que retorna calculate_entire_project()
{
    "Azure Kubernetes Service (AKS)": {
        "cluster_management": {"hourly": 0.0, "monthly": 0.0},
        "nodes": [{
            "sku": "Standard_D2s_v3",
            "per_node_hourly": 0.096,
            "per_node_monthly": 70.08,
            "total_nodes": 3,
            "total_hourly": 0.288,
            "total_monthly": 210.24
        }],
        "total_monthly": 210.24
    },
    "Azure SQL Database": {
        "compute": [{
            "type": "compute",
            "description": "General Purpose - 2 vCores",
            "sku": "GP_Gen5_2",
            "hourly_rate": 0.20
        }],
        "total_monthly": 146.00
    },
    "Azure Cache for Redis": {
        "config": {"tier": "Standard", "size": "C0", ...},
        "total_monthly": 24.82
    },
    "summary": {
        "total_monthly_cost_usd": 381.06,
        "total_hourly_cost_usd": 0.522,
        "currency": "USD",
        "region": "westus"
    }
}
```

## 4. Flujo de Generación de Reportes

```
Usuario pide "report" (PDF/Excel)
        │
        ▼
CLI.cmd_report(services, format="pdf")
        │
        ├──► calculator.calculate_entire_project(services)
        │         → genera cost_data completo
        │
        ├──► PDFReportGenerator.generate_report(cost_data, title)
        │         │
        │         ├── Crea SimpleDocTemplate (A4, márgenes)
        │         ├── Título + fecha
        │         ├── Tabla "Cost Summary" (Total Monthly, Hourly, Currency, Region)
        │         ├── Tabla "Service Breakdown" (servicio → costo mensual)
        │         └── doc.build(story) → guarda PDF
        │
        └──► Retorna path: output/reports/azure_cost_report_20260101_120000.pdf

Alternativa Excel:
        │
        └──► ExcelReportGenerator.generate_report(cost_data)
                  │
                  ├── Sheet "Summary"   → métricas generales
                  ├── Sheet "Services"  → servicio | costo mensual | costo hourly
                  └── Sheet "Details"   → servicio | propiedad | valor
```

### Fallback sin dependencias

Si `reportlab` u `openpyxl` no están instalados, el sistema usa `SimpleTextReport` que genera un `.txt` formateado:

```python
from src.reports.pdf_generator import SimpleTextReport

gen = SimpleTextReport()
path = gen.generate_report(cost_data)
# → output/reports/azure_cost_report_20260101_120000.txt
```

## 5. Sistema de Caché

### Arquitectura de doble capa

```
┌─────────────────────────────────────┐
│           CacheManager              │
│                                     │
│  get(key)                           │
│    ├──► MemoryCache.get(key)        │  ← Capa 1: rápida, en RAM
│    │      ├── HIT → retorna         │
│    │      └── MISS ↓                │
│    │                                  │
│    └──► FileCache.get(key)          │  ← Capa 2: persistente, en disco
│           ├── HIT → retorna         │
│           │      → promueve a memoria│
│           └── MISS → retorna None   │
│                                     │
│  set(key, value, ttl)              │
│    ├──► MemoryCache.set()           │
│    └──► FileCache.set()             │
└─────────────────────────────────────┘
```

### Configuración

```yaml
# config/config.yaml
cache:
  enabled: true
  ttl_seconds: 3600       # Memoria: 1 hora
  max_size: 1000          # Máx entradas en memoria
  storage_type: "memory"  # memory | file | redis

# FileCache usa data/cache/*.json con TTL de 24h
```

### Uso directo

```python
from src.core.cache import CacheManager

cache = CacheManager(
    use_memory=True,
    use_file=True,
    memory_ttl=3600,       # 1 hora en RAM
    file_ttl=86400,        # 24 horas en disco
    cache_dir="./data/cache"
)

cache.set("mi_key", {"data": "value"})
value = cache.get("mi_key")  # → {"data": "value"}

stats = cache.memory_cache.stats()
print(f"Hit rate: {stats['hit_rate']:.1%}")
```

## 6. Comunicación entre Componentes

```
src/core/azure_client.py
    │
    ├── AzurePricingAPI        ← Cliente HTTP principal
    │   • __init__(currency, region)
    │   • get_service_prices() → List[Dict]
    │   • get_prices_by_sku()  → List[Dict]
    │   • get_aks_pricing()    → Dict
    │   • get_sql_database_pricing() → List[Dict]
    │   • get_redis_cache_pricing()  → List[Dict]
    │   • get_container_registry_pricing() → Dict
    │   • get_dns_pricing()    → Dict
    │   • get_devops_pricing() → List[Dict]
    │
    └── AzureCostCalculator    ← Agrega costos
        • __init__(api_client)
        • calculate_aks_cluster()    → Dict
        • calculate_entire_project() → Dict con summary

src/mcp_server/server.py
    │
    └── AzurePricingServer
        • __init__() → crea AzurePricingAPI + AzureCostCalculator
        • _register_tools() → 5 herramientas
        • call_tool(name, args) → ejecuta handler async
        • Handlers:
            _handle_search_prices()    → search_azure_prices
            _handle_calculate_cost()   → calculate_deployment_cost
            _handle_compare_regions()  → compare_regions
            _handle_create_chart()     → create_cost_chart
            _handle_generate_report()  → generate_cost_report

src/mcp_server/tools/pricing.py
    │
    └── PricingTools            ← Versión standalone del server
        • search_prices()
        • calculate_cost()
        • compare_regions()
        • list_available_services()

src/visualization/charts.py
    │
    └── ChartGenerator
        • create_bar_chart()     → PNG
        • create_pie_chart()     → PNG
        • create_line_chart()    → PNG
        • create_stacked_bar()   → PNG

src/visualization/diagrams.py
    │
    └── DiagramGenerator
        • create_mermaid_flowchart()   → código Mermaid
        • create_mermaid_sequence()    → código Mermaid
        • create_architecture_mermaid() → código Mermaid
        • create_plantuml()            → código PlantUML

src/reports/pdf_generator.py
    │
    ├── PDFReportGenerator
    └── SimpleTextReport        ← Fallback sin reportlab

src/reports/excel_generator.py
    │
    └── ExcelReportGenerator
        • generate_report() → 3 sheets: Summary, Services, Details
```

## 7. Guía de Implementación Paso a Paso

### Paso 1: Requisitos Previos

```bash
# Python 3.10+
python --version

# Clonar o descargar
cd pricing

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac
```

### Paso 2: Instalar Dependencias

```bash
# Instalación completa
pip install -r requirements.txt

# O instalación mínima (solo core)
pip install requests pydantic python-dotenv pyyaml loguru
```

### Paso 3: Configurar

```yaml
# Editar config/config.yaml
azure:
  pricing_api:
    currency: "USD"
    default_region: "westus"     # Tu región preferida
    timeout: 30
    max_retries: 3

cache:
  enabled: true
  ttl_seconds: 3600
  storage_type: "memory"          # memory | file

cli:
  default_region: "westus"
  default_currency: "USD"
  interactive_mode: true
```

### Paso 4: Verificar Funcionamiento

```bash
# Test básico: script standalone
python AzurePricing.py

# Test interactivo
python -c "from src.interfaces.cli import main; import asyncio; asyncio.run(main())"

# Dentro del CLI:
# > prices Virtual Machines
# > aks Standard_D2s_v3 3
# > compare Standard_D2s_v3
```

### Paso 5: Usar como Librería

```python
# mi_script.py
from src.core.azure_client import AzurePricingAPI, AzureCostCalculator

api = AzurePricingAPI(region="eastus")
calculator = AzureCostCalculator(api)

# Consulta simple
prices = api.get_service_prices("Virtual Machines")
print(f"Encontrados {len(prices)} precios")

# Cálculo de proyecto
config = {
    "aks": {"node_sku": "Standard_D4s_v3", "node_count": 5},
    "sql": {"tier": "General Purpose", "vcores": 4},
    "redis": {"tier": "Standard", "size": "C1"},
    "acr": {"tier": "Standard", "storage_gb": 200},
    "dns": {"zones": 2, "queries_per_month": 5000000}
}

result = calculator.calculate_entire_project(config)
print(f"Total Monthly: ${result['summary']['total_monthly_cost_usd']:.2f}")
```

### Paso 6: Generar Reportes

```python
from src.reports.pdf_generator import PDFReportGenerator
from src.reports.excel_generator import ExcelReportGenerator
from src.visualization.charts import ChartGenerator

# 1. Calcular costos (igual que paso 5)
result = calculator.calculate_entire_project(config)

# 2. Generar PDF
pdf_gen = PDFReportGenerator()
pdf_path = pdf_gen.generate_report(result, "Proyecto Producción")
print(f"PDF: {pdf_path}")

# 3. Generar Excel
excel_gen = ExcelReportGenerator()
excel_path = excel_gen.generate_report(result)
print(f"Excel: {excel_path}")

# 4. Generar gráfico
chart_gen = ChartGenerator()
cost_data = {}
for svc, details in result.items():
    if svc != "summary" and "total_monthly" in details:
        cost_data[svc] = details["total_monthly"]

chart_path = chart_gen.create_bar_chart(cost_data, "Cost Breakdown")
print(f"Chart: {chart_path}")
```

### Paso 7: Ejecutar MCP Server

```python
# mcp_runner.py
import asyncio
from src.mcp_server.server import AzurePricingServer

async def main():
    server = AzurePricingServer()
    
    # Listar herramientas disponibles
    tools = server.list_tools()
    for tool in tools:
        print(f"  {tool['name']}: {tool['description']}")
    
    # Ejecutar una herramienta
    result = await server.call_tool("search_azure_prices", {
        "service_name": "Virtual Machines",
        "region": "westus"
    })
    print(result)
    
    # Calcular costo
    result = await server.call_tool("calculate_deployment_cost", {
        "services": [
            {"type": "aks", "sku": "Standard_D2s_v3", "quantity": 3},
            {"type": "sql", "tier": "General Purpose", "vcores": 2},
            {"type": "redis", "tier": "Standard", "size": "C0"}
        ],
        "region": "westus"
    })
    print(result)

asyncio.run(main())
```

## 8. Extensibilidad: Cómo Agregar Funcionalidades

### Agregar un nuevo servicio (ej: Azure OpenAI)

**Archivo** | **Qué modificar**
---|---
`src/core/models.py` | Agregar `OPENAI = "Azure OpenAI"` a `ServiceType`
`src/core/azure_client.py` | Agregar método `get_openai_pricing(tier, tokens_per_month)`
`src/core/azure_client.py` | Agregar bloque `if "openai" in usage_config` en `calculate_entire_project()`
`src/mcp_server/server.py` | Agregar `elif "openai" in service_type` en `_handle_calculate_cost()`
`src/mcp_server/tools/pricing.py` | Agregar `elif "openai" in service_type` en `calculate_cost()`
`AzurePricing.py` | Agregar entrada `"openai": {...}` al `project_config`

### Agregar una nueva herramienta MCP

1. **Crear schema en `schemas.py`**:
```python
class NewToolRequest(BaseModel):
    param1: str = Field(description="Descripción")
    param2: int = Field(1)
```

2. **Registrar en `server.py`** — método `_register_tools()`:
```python
self._tools["new_tool"] = {
    "name": "new_tool",
    "description": "...",
    "input_schema": NewToolRequest.model_json_schema(),
    "handler": self._handle_new_tool,
}
```

3. **Crear handler en `server.py`**:
```python
async def _handle_new_tool(self, args: Dict[str, Any]) -> str:
    input_data = NewToolRequest(**args)
    # lógica...
    return "resultado"
```

### Agregar un nuevo formato de reporte (ej: HTML)

1. Crear `src/reports/html_generator.py`
2. Implementar clase `HTMLReportGenerator` con método `generate_report()`
3. Agregar caso `"html"` en `cli.py:cmd_report()`

## 9. Dependencias y Configuración

### Dependencias por capa

```
CORE (siempre requeridas):
  requests, pydantic, pyyaml, python-dotenv, loguru

MCP SERVER:
  mcp, fastmcp, langchain, langgraph, langchain-openai

VISUALIZACIÓN (opcional):
  matplotlib, plotly

REPORTES (opcional):
  reportlab (PDF), openpyxl (Excel)

API REST:
  fastapi, uvicorn

IA/MEMORIA:
  langchain-anthropic, chromadb
```

### Variables de Entorno

Crear `.env`:

```env
# Azure
AZURE_SUBSCRIPTION_ID=
AZURE_TENANT_ID=

# IA (para LangChain)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Redis (para caché distribuido)
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 10. Debugging y Troubleshooting

### Logs

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

O usar la configuración incluida:

```python
import logging.config
logging.config.fileConfig("config/logging.conf")
```

Los logs se escriben a `logs/azure_cost_agent.log` con rotación diaria.

### Errores Comunes

| Error | Causa | Solución |
|---|---|---|
| `No results found` | API no tiene datos para ese SKU/región | Verificar nombre exacto del servicio/SKU |
| `ConnectionError` | Sin internet | Verificar conectividad |
| `rate limit` | Demasiadas requests | Aumentar `retry_delay` en config |
| `matplotlib not installed` | Falta dependencia opcional | `pip install matplotlib` |
| `reportlab not installed` | Falta dependencia opcional | `pip install reportlab` |

### Verificar conectividad con Azure API

```bash
# Test directo
curl "https://prices.azure.com/api/retail/prices?\$filter=serviceName eq 'Virtual Machines'&currencyCode=USD"
```

### Cache debugging

```python
from src.core.cache import get_cache

cache = get_cache()
print(cache.stats())
# → {'memory': {'hits': 15, 'misses': 3, 'hit_rate': 0.83, ...}}
```

---

## Resumen de Archivos Clave

| Archivo | Rol | Líneas |
|---|---|---|
| `AzurePricing.py` | Script standalone de ejemplo | 529 |
| `src/core/azure_client.py` | Cliente API + calculadora | 441 |
| `src/core/models.py` | Modelos de datos + constantes | 275 |
| `src/core/cache.py` | Sistema de caché 2-capas | 355 |
| `src/mcp_server/server.py` | Servidor MCP con 5 herramientas | 307 |
| `src/mcp_server/schemas.py` | Esquemas Pydantic + catálogos | 206 |
| `src/mcp_server/tools/pricing.py` | PricingTools standalone | 225 |
| `src/interfaces/cli.py` | CLI interactiva | 265 |
| `src/visualization/charts.py` | Gráficos matplotlib | 266 |
| `src/visualization/diagrams.py` | Diagramas Mermaid/PlantUML | 285 |
| `src/reports/pdf_generator.py` | PDF + texto fallback | 286 |
| `src/reports/excel_generator.py` | Excel 3-sheets | 257 |
| `config/config.yaml` | Configuración central | 134 |
| `config/logging.conf` | Configuración de logs | 50 |
