# Azure Cost Agent - Documentación del Agente

## Índice

1. [Visión General](#visión-general)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Flujo de Trabajo](#flujo-de-trabajo)
4. [Componentes y Archivos](#componentes-y-archivos)
5. [Comunicación entre Componentes](#comunicación-entre-componentes)
6. [Herramientas MCP](#herramientas-mcp)
7. [Ejemplos de Uso](#ejemplos-de-uso)
8. [Extensibilidad](#extensibilidad)

---

## Visión General

El **Azure Cost Agent** es un sistema de estimación de costos para servicios de Azure que utiliza el protocolo MCP (Model Context Protocol) para proporcionar herramientas de pricing a agentes de IA. El sistema permite:

- Consultar precios de servicios Azure en tiempo real
- Calcular costos de despliegues multi-servicio
- Comparar precios entre regiones
- Generar visualizaciones y reportes profesionales

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                     CAPA DE INTERFAZ                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │    CLI      │  │   API REST  │  │   Agente IA (externo)  │ │
│  │ (Terminal)  │  │  (FastAPI)  │  │   (LangChain)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA ORQUESTACIÓN                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    MCP SERVER                             │   │
│  │  • Registro de herramientas                               │   │
│  │  • Manejo de solicitudes                                │   │
│  │  • Validación de argumentos                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE HERRAMIENTAS                        │
│  ┌───────────────┐ ┌───────────────┐ ┌─────────────────────────┐   │
│  │  Pricing    │ │ Visualization│ │ Reports              │   │
│  │  Tools     │ │ Tools        │ │ Tools                │   │
│  └───────────────┘ └───────────────┘ └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE DATOS Y CORE                         │
│  ┌───────────────┐ ┌───────────────┐ ┌─────────────────────────┐   │
│  │ Azure Client │ │   Cache      │ │ Models                │   │
│  │ (API Client) │ │   System    │ │ (Data Types)          │   │
│  └───────────────┘ └───────────────┘ └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 SERVICIOS EXTERNOS                              │
│  • Azure Retail Prices API                                   │
│  • Matplotlib/Plotly (gráficos)                          │
│  • ReportLab (PDF)                                       │
│  • OpenPyXL (Excel)                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flujo de Trabajo

### Flujo Principal: Consulta de Precios

```
Usuario/Agente
      │
      ▼
┌─────────────────────────────────────┐
│  1. Solicitud (Command/API/Tool)     │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│  2. MCP Server recibe solicitud      │
│     - Valida argumentos           │
│     - Identifica herramienta     │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│  3. Pricing Tools procesa           │
│     - AzurePricingAPI.fetch()      │
│     - Cache.check()              │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│  4. Azure Retail Prices API         │
│     - HTTP GET /retail/prices    │
│     - Paginación automática    │
└─────────────────────────────────────┘
      │ (si no hay cache)
      ▼
┌─────────────────────────────────────┐
���  5. Respuesta formateada        │
│     - Lista de precios         │
│     - Totales calculados     │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│  6. Retorno al usuario/agente      │
└─────────────────────────────────────┘
```

### Flujo de Cálculo de Costo Completo

```
1. Usuario → "Calcular costo de AKS + SQL + Redis"
      │
      ▼
2. MCP Server → extract_services(solicitud)
      │
      ▼
3. Para cada servicio:
   a) PricingTools.get_pricing(servicio)
          │
          ▼
   b) AzurePricingAPI.get_X_pricing()
          │
          ▼
   c) Cache.check() → si existe, retorna cache
          │         si no, llama API
          ▼
   d) Azure Retail Prices API
          │
          ▼
   e) Cache.set(resultado)
      │
      ▼
4. AzureCostCalculator.aggregate(servicios)
      │
      ▼
5. Retorna breakdown completo con totales
```

---

## Componentes y Archivos

### 1. Core - `src/core/`

#### `azure_client.py` (16573 bytes)
**Responsabilidad**: Cliente principal para la Azure Retail Prices API

**Clases principales**:
- `AzurePricingAPI`: Cliente HTTP con manejo de paginación, retry, y caché
  - `BASE_URL = "https://prices.azure.com/api/retail/prices"`
  - Métodos:
    - `get_service_prices(service_name)` - Obtiene precios por servicio
    - `get_prices_by_sku(sku_name)` - Obtiene precios por SKU
    - `get_aks_pricing(node_sku)` - precios específicos de AKS
    - `get_sql_database_pricing(tier, vcores)` - precios de SQL
    - `get_redis_cache_pricing(tier, size)` - precios de Redis
    - `get_container_registry_pricing(tier)` - precios de ACR
    - `get_dns_pricing(zones, queries)` - precios de DNS
    - `get_devops_pricing()` - precios de Azure DevOps

- `AzureCostCalculator`: Calcula costos totales de proyectos
  - `calculate_aks_cluster(node_sku, node_count)` - Calcula costo de AKS
  - `calculate_entire_project(usage_config)` - Calcula costo total

**Dependencias**: requests, lru_cache, logging

#### `models.py` (7034 bytes)
**Responsabilidad**: Definiciones de tipos y modelos de datos

**Enumeraciones**:
- `ServiceType`: Tipos de servicios Azure (VIRTUAL_MACHINES, AKS, SQL_DATABASE, etc.)
- `PricingTier`: Niveles de precios (STANDARD, PREMIUM, GENERAL_PURPOSE, etc.)

**DataClasses**:
- `PriceItem`: Un item de precio individual
  - Campos: service_name, sku_name, retail_price, unit_of_measure, region, currency
- `ServiceConfig`: Configuración de un servicio en despliegue
  - Campos: service_type, sku, quantity, hours_per_month, tier, region
- `CostBreakdown`: Desglose de costos por servicio
  - Campos: service_name, hourly_cost, monthly_cost, yearly_cost, currency
- `DeploymentEstimate`: Estimación completa de despliegue
  - Campos: services, region, currency, totales, breakdown

**Constantes**:
- `AZURE_REGIONS`: Lista de regiones Azure disponibles
- `VM_SKUS`: SKUs comunes de VMs
- `SQL_SKUS`: SKUs de SQL Database
- `REDIS_SKUS`: SKUs de Redis Cache

#### `cache.py` (10673 bytes)
**Responsabilidad**: Sistema de caché para optimizar llamadas API

**Clases**:
- `MemoryCache`: Caché en memoria con TTL
  - Métodos: `get(key)`, `set(key, value, ttl)`, `delete(key)`, `clear()`, `cleanup()`, `stats()`
- `FileCache`: Caché basada en archivos JSON
  - Similar API a MemoryCache pero persiste en disco
- `CacheManager`: Unifica MemoryCache y FileCache
  - Intenta memoria primero, luego archivo

**Características**:
- TTL configurable (default 3600 segundos para memoria, 86400 para archivo)
- Estadísticas de hits/misses
- Limpieza automática de entradas expiradas

---

### 2. MCP Server - `src/mcp_server/`

#### `server.py` (11172 bytes)
**Responsabilidad**: Servidor principal que registra y ejecuta herramientas MCP

**Clases principales**:
- `AzurePricingServer`: Servidor MCP
  - `_register_tools()`: Registra todas las herramientas disponibles
  - `list_tools()`: Retorna lista de herramientas
  - `call_tool(tool_name, arguments)`: Ejecuta una herramienta específica

**Herramientas registradas**:
1. `search_azure_prices` - Búsqueda de precios por servicio o SKU
2. `calculate_deployment_cost` - Cálculo de costo total de despliegue
3. `compare_regions` - Comparación de precios entre regiones
4. `create_cost_chart` - Creación de gráficos de costos
5. `generate_cost_report` - Generación de reportes PDF/Excel

**Handlers** (privados):
- `_handle_search_prices(args)` → Procesa búsqueda de precios
- `_handle_calculate_cost(args)` → Procesa cálculo de costos
- `_handle_compare_regions(args)` → Procesa comparación de regiones
- `_handle_create_chart(args)` → Procesa creación de gráficos
- `_handle_generate_report(args)` → Procesa generación de reportes

#### `schemas.py` (6112 bytes)
**Responsabilidad**: Definiciones de esquemas Pydantic para validación

**Modelos**:
- `SearchPricesRequest`: Input para búsqueda de precios
- `CalculateCostRequest`: Input para cálculo de costos
- `CompareRegionsRequest`: Input para comparación de regiones
- `ChartRequest`: Input para creación de gráficos
- `ReportRequest`: Input para generación de reportes
- `DiagramRequest`: Input para diagramas de arquitectura

#### `tools/pricing.py` (6991 bytes)
**Responsabilidad**: Herramientas de pricing independientes del servidor

**Clase**:
- `PricingTools`: Colección de funciones de pricing
  - `search_prices(service_name, sku, region)` → Busca precios
  - `calculate_cost(services, region)` → Calcula costos
  - `compare_regions(sku, regions)` → Compara regiones
  - `list_available_services()` → Lista servicios disponibles

---

### 3. Visualization - `src/visualization/`

#### `charts.py` (8073 bytes)
**Responsabilidad**: Generación de gráficos de costos

**Clase**:
- `ChartGenerator`: Genera visualizaciones con matplotlib
  - `create_bar_chart(data, title, filename)` → Gráfico de barras
  - `create_pie_chart(data, title, filename)` → Gráfico circular
  - `create_line_chart(data, title, filename)` → Gráfico de tendencias
  - `create_stacked_bar(data, title, filename)` → Gráfico de barras apiladas

**Características**:
- Colores corporativos de Azure (#0078D4, #107C10, #D83B01, etc.)
- Guardado automático en `output/charts/`
- Manejo graceful si matplotlib no está instalado

#### `diagrams.py` (8425 bytes)
**Responsabilidad**: Generación de diagramas de arquitectura

**Clase**:
- `DiagramGenerator`: Genera diagramas Mermaid/PlantUML
  - `create_mermaid_flowchart(services)` → Diagrama de flujo
  - `create_mermaid_sequence(participants, interactions)` → Diagrama de secuencia
  - `create_architecture_mermaid(services)` → Diagrama de arquitectura Azure

**Funciones helpers**:
- `create_azure_architecture_diagram(services)` → Crea diagrama de arquitectura
- `create_flowchart(services)` → Crea diagrama de flujo simple

---

### 4. Reports - `src/reports/`

#### `pdf_generator.py` (9439 bytes)
**Responsabilidad**: Generación de reportes PDF profesionales

**Clases**:
- `PDFReportGenerator`: Genera PDFs con ReportLab
  - `generate_report(cost_data, title, include_charts)` → Genera reporte completo
  - `add_chart_to_report(pdf_path, chart_path)` → Agrega gráfico a PDF

- `SimpleTextReport`: Alternativa simple sin dependencias
  - Genera archivos de texto formateados

**Características**:
- Estilos profesionales (colores Azure)
- Tablas con formato (Summary, Service Breakdown)
- Soporte para gráficos integrados

#### `excel_generator.py` (8072 bytes)
**Responsabilidad**: Generación de reportes Excel

**Clase**:
- `ExcelReportGenerator`: Genera Excel con OpenPyXL
  - `generate_report(cost_data, title)` → Genera workbook con múltiples sheets
  - `add_chart_sheet(excel_path, chart_data)` → Agrega sheet con gráfico

**Sheets generados**:
1. **Summary**: Resumen ejecutivo con totales
2. **Services**: Desglose por servicio
3. **Details**: Detalle completo de propiedades

---

### 5. Interfaces - `src/interfaces/`

#### `cli.py` (9200 bytes)
**Responsabilidad**: Interfaz de línea de comandos interactiva

**Clase**:
- `AzureCostCLI`: CLI principal
  - `cmd_prices(service)` → Busca precios
  - `cmd_sku(sku)` → Busca por SKU
  - `cmd_aks(node_sku, node_count)` → Estima AKS
  - `cmd_sql(tier, vcores)` → Estima SQL Database
  - `cmd_redis(tier, size)` → Estima Redis
  - `cmd_compare(sku, regions)` → Compara regiones
  - `cmd_report(services, format)` → Genera reporte
  - `cmd_chart(services)` → Genera gráfico
  - `run_interactive()` → Modo interactivo

---

## Comunicación entre Componentes

### Diagrama de Dependencias

```
┌────────────────────────────────────────────────────────────────────┐
│                           USUARIO/CLI                               │
│  (AzureCostCLI.run_interactive())                                     │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                      MCP SERVER (server.py)                           │
│  • AzurePricingServer.call_tool()                                    │
│  • Valida entrada → selecciona handler                              │
└────────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
┌──────────────────────────┐   ┌────────────────────────────────────┐
│   Pricing Tools        │   │  Visualization/Reports (handlers) │
│   (tools/pricing.py) │   │  (cuando se usan)                 │
│                    │   │                                 │
│  • PricingTools.search   │   │  • ChartGenerator.create_xxx()   │
│  • PricingTools.calculate│   │  • PDFReportGenerator.generate() │
│  • PricingTools.compare  │   │  • ExcelReportGenerator.generate │
└──────────────────────────┘   └────────────────────────────────────┘
                    │                       │
                    └───────────┬───────────┘
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                    AZURE PRICING API CLIENT                        │
│  (core/azure_client.py)                                           │
│                                                                     │
│  ┌────────────────────────┐  ┌──────────────────────────────────┐ │
│  │  AzurePricingAPI     │  │  AzureCostCalculator           │ │
│  │  • get_service_prices()│  │  • calculate_aks_cluster()     │ │
│  │  • get_prices_by_sku() │  │  • calculate_entire_project()   │ │
│  └───────────┬────────────┘  └──────────────┬───────────────────┘ │
│              │                               │                     │
│              ▼                               │                     │
│  ┌───────────────────────────────────────────┴───────────────────┐   │
│  │                      CACHE SYSTEM (cache.py)             │   │
│  │  CacheManager.get() → MemoryCache.get() → FileCache.get()  │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │                  AZURE RETAIL PRICES API                 │   │
│  │  https://prices.azure.com/api/retail/prices          │   │
│  │  GET /?$filter=...&currencyCode=USD                 │   │
│  └─────────────────────��─��───────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

### Flujo de datos detallado

```
1. CLI/Usuario → MCP Server
   cli.py:input("prices Virtual Machines")
       │
       ▼
   server.py:call_tool("search_azure_prices", {"service_name": "..."})
       │
       ▼
2. MCP Server → Pricing Tools
   server.py:_handle_search_prices(args)
       │
       ▼
   tools/pricing.py:PricingTools.search_prices()
       │
       ▼
3. Pricing Tools → Azure Client
   PricingTools.api.get_service_prices(service_name)
       │
       ▼
4. Azure Client → Cache
   AzurePricingAPI._get_prices_cached(filter_str)
       │
       ├──→ MemoryCache.get(key) → HIT → retorna valor
       │
       └──→ MISS → FileCache.get(key)
                   │
                   ├──→ HIT → retorna, promote to memory
                   │
                   └──→ MISS → Azure API call
                                    │
                                    ▼
5. Azure API Response → Cache → Pricing Tools → MCP Server → CLI
   Cache.set(key, value) ←── retorna valor ──→ formatear resultado ──→ return string
```

---

## Herramientas MCP

### 1. search_azure_prices

**Propósito**: Buscar precios de servicios Azure por nombre o SKU

**Entrada**:
```json
{
  "service_name": "Virtual Machines",
  "sku": "Standard_D2s_v3",
  "region": "westus"
}
```

**Proceso**:
1. MCP Server recibe solicitud
2. Valida argumentos con `SearchPricesInput`
3. Llama a `azure_api.get_service_prices()` o `get_prices_by_sku()`
4. El API client usa caché primero, luego API si es necesario
5. Formatea resultados y retorna

**Salida**:
```
Found 50 results:

• Virtual Machines - Standard_D2s_v3
  Price: $0.0960 per hour
  Region: westus
```

### 2. calculate_deployment_cost

**Propósito**: Calcular costo total de un despliegue multi-servicio

**Entrada**:
```json
{
  "services": [
    {"type": "aks", "sku": "Standard_D2s_v3", "quantity": 3},
    {"type": "sql", "tier": "General Purpose", "vcores": 2},
    {"type": "redis", "tier": "Standard", "size": "C0"}
  ],
  "region": "westus"
}
```

**Proceso**:
1. Parsea configuración de servicios
2. Para cada servicio, obtiene precios individuales
3. Calcula costo usando `AzureCostCalculator.calculate_entire_project()`
4. Genera breakdown detallado

**Salida**:
```
💰 Cost Estimate 💰

Azure Kubernetes Service (AKS):
  Monthly: $197.64

Azure SQL Database:
  Monthly: $145.92

Azure Cache for Redis:
  Monthly: $24.82

========================================
Total Monthly: $368.38
Total Hourly: $0.5046
```

### 3. compare_regions

**Propósito**: Comparar precios de un SKU entre múltiples regiones

**Entrada**:
```json
{
  "sku": "Standard_D2s_v3",
  "regions": ["westus", "eastus", "westeurope", "southeastasia"]
}
```

**Proceso**:
1. Itera sobre cada región
2. Obtiene precios del SKU en esa región
3. Ordena resultados por precio
4. Identifica la región más económica

**Salida**:
```
📊 Price Comparison for Standard_D2s_v3

  westus: $0.0960/hour ⭐ (cheapest)
  eastus: $0.1020/hour
  westeurope: $0.1080/hour
  southeastasia: $0.1100/hour
```

### 4. create_cost_chart

**Propósito**: Generar visualización de costos

**Entrada**:
```json
{
  "data": {
    "AKS": 197.64,
    "SQL": 145.92,
    "Redis": 24.82
  },
  "chart_type": "bar",
  "title": "Cost Breakdown"
}
```

### 5. generate_cost_report

**Propósito**: Generar reporte profesional

**Entrada**:
```json
{
  "cost_data": {...},
  "format": "pdf",
  "include_charts": true
}
```

---

## Ejemplos de Uso

### Ejemplo 1: Búsqueda simple de precios

```python
from src.core.azure_client import AzurePricingAPI

api = AzurePricingAPI(currency="USD", region="westus")
results = api.get_service_prices("Virtual Machines")

for item in results[:5]:
    print(f"{item['armSkuName']}: ${item['retailPrice']:.4f}/hour")
```

### Ejemplo 2: Cálculo de costo de proyecto

```python
from src.core.azure_client import AzurePricingAPI, AzureCostCalculator

api = AzurePricingAPI(region="westus")
calculator = AzureCostCalculator(api)

config = {
    "aks": {"node_sku": "Standard_D2s_v3", "node_count": 3},
    "sql": {"tier": "General Purpose", "vcores": 2},
    "redis": {"tier": "Standard", "size": "C0"}
}

result = calculator.calculate_entire_project(config)
print(f"Total Monthly: ${result['summary']['total_monthly_cost_usd']:.2f}")
```

### Ejemplo 3: Generación de reporte PDF

```python
from src.reports.pdf_generator import PDFReportGenerator

generator = PDFReportGenerator(output_dir="output/reports")
filepath = generator.generate_report(cost_data, title="Mi Reporte")
print(f"Reporte generado: {filepath}")
```

### Ejemplo 4: Uso del CLI interactivo

```bash
python -c "from src.interfaces.cli import main; main()"

> prices Virtual Machines
> aks Standard_D2s_v3 3
> compare Standard_D2s_v3
> report
> help
```

---

## Extensibilidad

### Agregar nuevo servicio

1. **En `azure_client.py`**: Agregar método `get_<service>_pricing()`

2. **En `models.py`**: Agregar a `ServiceType` enum si es necesario

3. **En `server.py`**: Agregar caso en `_handle_calculate_cost()`

4. **En `tools/pricing.py`**: Agregar método si se necesita función standalone

### Agregar nueva herramienta MCP

1. **En `schemas.py`**: Crear clase de request

2. **En `server.py`**: 
   - Agregar entrada en `_register_tools()`
   - Crear handler `_handle_new_tool()`

---

## Glosario

| Término | Definición |
|---------|-----------|
| MCP | Model Context Protocol - Protocolo para herramientas de IA |
| SKU | Stock Keeping Unit - Identificador de producto Azure |
| ARM | Azure Resource Manager - Sistema de despliegue de Azure |
| TTL | Time To Live - Tiempo de vida de entrada en caché |
| API | Application Programming Interface - Interfaz de programación |