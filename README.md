# BillMed — Gestión de Producción Médica

Sistema para la administración y liquidación de producción médica. Gestiona médicos, tarifas, producción y genera recibos de honorarios.

## Modelo de Base de Datos

### Entidades

#### Medico
| Campo | Tipo | Descripción |
|---|---|---|
| id | PK | Identificador único |
| nombre | VARCHAR(100) | Nombre completo |
| numero_documento | VARCHAR(20) _unique_ | Número de identificación |
| especialidad | VARCHAR(100) | Neumología, Cardiología, etc. |
| email | EmailField _unique_ | Correo electrónico |
| telefono | VARCHAR(20) | Teléfono de contacto |
| sede | VARCHAR(100) | Sede asignada (Principal, Cabecera, Machado, etc.) |
| registrado_por | FK → User _nullable_ | Usuario que registró |
| fecha_registro | DATETIME _auto_ | Fecha de creación |

**Relaciones:**
- M:N con **Tarifa** vía tabla intermedia `medicos_medico_servicios` (servicios que presta cada médico)
- 1:N con **Produccion** (`producciones`)

---

#### Tarifa
| Campo | Tipo | Descripción |
|---|---|---|
| id | PK | Identificador único |
| nombre | VARCHAR(100) | Nombre del servicio |
| precio | INTEGER | Precio del servicio |
| unidad_negocio | VARCHAR(50) | Servicio Médico, Interconsulta, Lab. Pulmonar, etc. |
| subunidad_procedimientos | VARCHAR(100) _nullable_ | Diagnósticos / Intervencionismo |
| descripcion | TEXT _nullable_ | Descripción del servicio |
| registrado_por | FK → User _nullable_ | Usuario que registró |
| fecha_registro | DATETIME _auto_ | Fecha de creación |

**Relaciones:**
- M:N con **Medico** (`medicos`)
- 1:N con **Produccion** (`producciones_servicio`)

---

#### Produccion
| Campo | Tipo | Descripción |
|---|---|---|
| id | PK | Identificador único |
| medico | FK → Medico | Médico que realizó el servicio |
| servicio | FK → Tarifa | Servicio prestado |
| precio_aplicado | DECIMAL(10,2) | Precio al momento de registrar |
| cantidad | INTEGER _default: 1_ | Unidades realizadas |
| sede_momento | VARCHAR(100) | Sede al momento del registro |
| unidad_negocio_momento | VARCHAR(100) | Unidad de negocio al momento |
| subunidad_momento | VARCHAR(100) _nullable_ | Sub-unidad al momento |
| fecha_labor | DATE | Fecha en que se realizó el servicio |
| registrado_por | FK → User _nullable_ | Usuario que registró |
| fecha_registro | DATETIME _auto_ | Fecha del registro en sistema |

**Propiedades:**
- `subtotal`: cantidad × precio_aplicado

**Relaciones:**
- N:1 con **Medico**
- N:1 con **Tarifa**

---

### Diagrama de Relaciones

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│    User     │     │  Medico_Tarifa   │     │   Medico    │
│  (auth)     │     │    (M:N inter)   │     │             │
└──────┬──────┘     └────────┬─────────┘     └──────┬──────┘
       │                     │                      │
       │  registrado_por     │ M:N                  │ 1:N
       ▼                     ▼                      ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Tarifa    │     │   Produccion     │     │             │
│             │────▶│  (tabla central) │◀────│             │
│             │ 1:N │                  │     │             │
└─────────────┘     └──────────────────┘     └─────────────┘
```

### Convenciones

- **on_delete=CASCADE** en Medico → Produccion: al eliminar un médico se eliminan sus producciones
- **on_delete=PROTECT** en Tarifa → Produccion: no permite eliminar una tarifa con producción asociada
- **on_delete=SET_NULL** en FK a User: al eliminar un usuario se conservan los registros
- La tabla intermedia `medicos_medico_servicios` se genera automáticamente por el ManyToManyField
- `precio_aplicado` se congela al momento de crear la producción (editable=False)
