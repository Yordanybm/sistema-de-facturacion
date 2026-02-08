# Sistema de Facturación (Flask + SQLite)

Aplicación full stack para un pequeño negocio con:
- Gestión de clientes
- Gestión de productos e inventario
- Facturación con ITBIS (18%)
- Historial con filtros
- Generación de comprobantes en PDF e impresión

## Requisitos
- Python 3.10+
- pip

## Instalación
```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución
```bash
python app.py
```

Luego abre: `http://localhost:5000`

## Estructura
- `app.py`: Backend Flask, API REST, lógica de facturación y PDF.
- `templates/index.html`: Interfaz principal con dashboard y menú lateral.
- `static/css/styles.css`: Estilos responsive y diseño profesional.
- `static/js/app.js`: Lógica frontend (CRUD, facturación, historial, filtros).
- `database/`: Base de datos SQLite (`billing.db`) se crea automáticamente.

## Funciones incluidas
1. **Clientes:** crear, editar, eliminar y buscar.
2. **Productos:** crear, editar, eliminar, buscar, stock automático.
3. **Facturación:** número automático, fecha automática, múltiples productos, subtotal, ITBIS y total.
4. **Comprobante:** generación PDF por factura + impresión.
5. **Historial:** listado, filtros por fecha/cliente y reimpresión.
6. **Interfaz:** dashboard, menú lateral y diseño responsive.
