# 🏦 Sistema de Préstamos y Gestión de Cartera Crediticia

![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.108%2B-009688?logo=fastapi)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?logo=sqlalchemy)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap)
![Chart.js](https://img.shields.io/badge/Chart.js-4.x-FF6384?logo=chartdotjs)
![License](https://img.shields.io/badge/License-MIT-green)

Aplicación web full-stack de alto rendimiento diseñada para la administración, originación y cobranza de microcréditos, préstamos comerciales y personales. El sistema cuenta con un **motor de amortización financiero**, liquidación de pagos mediante **algoritmo FIFO**, **control automático de mora**, **directorio 360° de clientes**, **dashboard ejecutivo interactivo** y **exportación de contratos y comprobantes en PDF**.

---

## 🏗️ 1. Arquitectura Modular del Sistema

El software está diseñado bajo principios de arquitectura modular y desacoplada para garantizar escalabilidad y fácil mantenimiento:

```mermaid
flowchart TD
    subgraph UI ["Capa de Presentación (Frontend)"]
        A["Panel de Préstamos"]
        B["Ficha 360° Clientes"]
        C["Dashboard KPIs & Chart.js"]
        D["Contratos & Recibos PDF"]
    end

    subgraph Routers ["Capa de Enrutamiento (FastAPI)"]
        R_AUTH["routers/auth.py"]
        R_CLIENTS["routers/clientes.py"]
        R_LOANS["routers/prestamos.py"]
        R_REP["routers/reportes.py"]
    end

    subgraph Core ["Lógica de Negocio & Motor Financiero"]
        S_AMORT["Motor de Amortización (services.py)"]
        S_FIFO["Distribución FIFO de Pagos"]
        S_RISK["Analizador de Riesgo & Mora"]
    end

    subgraph Data ["Persistencia & Modelos ORM"]
        M_USER["UsuarioDB"]
        M_CLI["ClienteDB"]
        M_PRES["PrestamoDB"]
        M_CUOTA["CuotaDB"]
        M_PAGO["PagoDB"]
    end

    UI --> Routers
    Routers --> Core
    Core --> Data
```

*   **Módulo de Autenticación (`auth`)**: Control de acceso basado en roles (*RBAC*). Diferenciación entre administradores (aprobación y control global) y cobradores (gestión de rutas y registro de cobros). Sesiones firmadas con cookies seguras `HttpOnly`.
*   **Módulo de Clientes (`clients`)**: Registro de deudores, búsqueda multicriterio por DNI, contacto rápido con WhatsApp, evaluación de riesgo crediticio (*Excelente*, *Regular*, *Riesgo Alto*) y consolidados de deuda.
*   **Módulo de Préstamos y Amortización (`loans`)**: Motor financiero que calcula el cronograma exacto de pagos según la periodicidad (*Diario con salto de domingos*, *Semanal*, *Quincenal*, *Mensual*).
*   **Módulo de Pagos y Caja (`payments`)**: Liquidación de cuotas bajo regla FIFO (*First-In, First-Out*), abonos parciales, actualización de saldos en tiempo real y emisión de vouchers.
*   **Módulo de Reportes y Business Intelligence (`dashboard`)**: Panel ejecutivo con métricas de capital colocado, recuperado, cartera en riesgo (mora), flujo de cobranza semanal y gráficos interactivos con **Chart.js**.

---

## 📊 2. Modelo de Datos Relacional (ERD)

```mermaid
erDiagram
    USUARIOS ||--o{ PRESTAMOS : "asigna / crea"
    CLIENTES ||--o{ PRESTAMOS : "solicita"
    PRESTAMOS ||--o{ CUOTAS : "desglosa en"
    PRESTAMOS ||--o{ PAGOS : "recibe"
    CUOTAS ||--o{ PAGOS : "amortiza"

    USUARIOS {
        int id PK
        string username UK
        string password_hash
        string rol
        string nombre
    }

    CLIENTES {
        int id PK
        string documento_identidad UK
        string nombre_completo
        string telefono
        string direccion
        string calificacion
        boolean activo
    }

    PRESTAMOS {
        string id PK
        int cliente_id FK
        float monto
        float interes
        float total
        float saldo
        string modalidad
        int numero_cuotas
        string fecha_inicio
        string fecha_vencimiento
        string estado
        string cobrador_asignado
    }

    CUOTAS {
        int id PK
        string prestamo_id FK
        int numero_cuota
        string fecha_vencimiento
        float monto_capital
        float monto_interes
        float total_cuota
        float saldo_cuota
        string estado
    }

    PAGOS {
        int id PK
        string prestamo_id FK
        int cuota_id FK
        string fecha
        float monto
        string registrado_por
        string metodo_pago
    }
```

---

## ⚙️ 3. Lógica de Ingeniería Financiera

### A. Motor de Amortización y Ajuste de Centavos
Para un capital $M$, una tasa de interés $I\%$ y un número de cuotas pactadas $N$:
$$\text{Interés Total} = M \times \left(\frac{I}{100}\right)$$
$$\text{Total a Pagar} = M + \text{Interés Total}$$
$$\text{Cuota Base} = \frac{\text{Total a Pagar}}{N}$$

> **Resolución de Redondeo Flotante**: En operaciones financieras, las divisiones pueden generar centavos flotantes sobrantes (ej: $100 / 3 = 33.33$). El motor financiero del sistema acumula los importes de las primeras $N-1$ cuotas y ajusta la última cuota para que la sumatoria física de las cuotas coincida al $100.00\%$ con el total contratado.

### B. Algoritmo de Liquidación FIFO (First In, First Out)
Cuando un cliente realiza un abono, el sistema no descuenta simplemente un saldo ciego; distribuye el pago ordenadamente entre las cuotas pendientes más antiguas:
1. Si el monto cubre la cuota $K$, su `saldo_cuota` pasa a `0.00` y su estado a `'Pagada'`.
2. Si el monto cubre parcialmente una cuota, su estado se actualiza a `'Parcial'`.
3. Cualquier excedente avanza automáticamente a saldar la cuota $K+1$.

### C. Detección Automatizada de Mora
Cada consulta evalúa las fechas de vencimiento de las cuotas impagas frente a la fecha del sistema (`date.today()`). Si una cuota con saldo pendiente superó su fecha límite:
*   La cuota se marca como `'Vencida'`.
*   El préstamo completo cambia de estado a `'⚠️ En Mora'`.
*   Su saldo se añade a la métrica ejecutiva de **Capital en Riesgo** y al **Panel de Alertas**.

---

## 📄 4. Documentación y Exportación en PDF

*   **Contrato y Cronograma Oficial**: Plantilla membretada con desglose de cuotas, capital, interés, declaración de conformidad y casillas formales para firma del deudor y del acreedor.
*   **Comprobantes Digitales**: Generación de recibos con hoja de estilos optimizada para impresión en ticket térmico o PDF estándar A4.
*   **Integración WhatsApp API**: Generación de enlaces con mensajes preconfigurados de cobranza y recordatorios de pago para apertura inmediata en WhatsApp Web o móvil.

---

## 🚀 5. Instalación y Puesta en Marcha

### Prerrequisitos
*   Python 3.11 o superior.
*   Git.

### Pasos de Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/prestamos-saurin.git
   cd prestamos-saurin
   ```

2. **Crear y activar el entorno virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # En Linux/macOS
   # .venv\Scripts\activate   # En Windows
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Ejecutar migraciones automáticas:**
   ```bash
   python migrate.py
   ```

5. **Iniciar el servidor de desarrollo:**
   ```bash
   uvicorn app:app --reload --port 8000
   ```

6. **Acceder a la aplicación:**
   Abre en tu navegador: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 🔑 Credenciales por Defecto (Semillas)

| Usuario | Contraseña | Rol | Acceso |
| :--- | :--- | :--- | :--- |
| `Geison` | `xiomara789` | **Admin** | Control total, crear préstamos, reportes y clientes. |
| `juan` | `juan123` | **Cobrador** | Visualización de ruta y registro de pagos. |
| `pedro` | `pedro123` | **Cobrador** | Visualización de ruta y registro de pagos. |

---

## ☁️ 6. Guía de Despliegue en la Nube (Render / Railway / Docker)

### Variables de Entorno Opcionales

*   `DATABASE_URL`: Cadena de conexión para PostgreSQL en producción (ej: `postgresql://user:password@host:5432/dbname`). Si no se define, utiliza SQLite local (`sqlite:///./test.db`).
*   `SECRET_KEY`: Llave criptográfica para firmas de sesión.
*   `SESSION_MAX_AGE`: Tiempo de vida de la sesión en segundos (por defecto: `86400` / 24 horas).

### Despliegue en Render / Railway
*   **Build Command**: `pip install -r requirements.txt`
*   **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`

---

## 🛡️ 7. Seguridad y Buenas Prácticas

*   **PBKDF2 con Salt Dinámico**: Las contraseñas se almacenan mediante 260,000 iteraciones de PBKDF2-SHA256, sin texto plano en base de datos.
*   **Protección contra SQL Injection**: Uso estricto de SQLAlchemy 2.0 ORM con consultas parametrizadas.
*   **Transacciones Atómicas**: Bloques `try/except` con `db.rollback()` para evitar inconsistencias en el estado de la base de datos ante errores imprevistos.

---

Desarrollado con fines de ingeniería de software profesional, arquitectura limpia y gestión financiera.
