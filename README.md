# Stock AI - Plataforma Inteligente de Gestión de Inventario

Stock AI es una plataforma que permite a las empresas automatizar la gestión de inventario utilizando inteligencia artificial, con el fin de evitar roturas de stock, minimizar excesos de almacenamiento y facilitar la toma de decisiones logísticas.

## Características Principales
- 🔐 **Login con control de roles** (admin y empresas)
- 📊 **Visualización del punto de pedido** por producto
- 📁 **Subida de facturas en PDF** y procesamiento automático con GPT-4
- 🔢 **Base de datos SQLite por empresa** para almacenamiento seguro
- 📊 **Filtros avanzados para facturas** (fecha, producto, número de factura)
- 📖 **Interfaz moderna con Streamlit**
- 🛌 **Soporte directo al cliente** desde el dashboard

## Tecnologías
- Python 3.10+
- Streamlit
- PyMuPDF (fitz)
- OpenAI GPT-4 API
- SQLite
- Pandas / JSON

## Instalación
1. Clona el repositorio:
```bash
git clone https://github.com/tu_usuario/stock-ai.git
cd stock-ai
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Coloca tus facturas PDF en `data/facturas/` y configura los usuarios en `users.json`.

4. Ejecuta la aplicación:
```bash
streamlit run app.py
```

## Estructura del Proyecto
```
stock-ai/
├── app.py
├── read_invoice.py
├── users.json
├── data/
│   ├── facturas/
│   ├── facturas_procesadas/
│   └── bases_datos/
└── README.md
```

## Licencia
Este proyecto está bajo licencia MIT
