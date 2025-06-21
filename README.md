# 📦 Stock AI

**Stock AI** es una plataforma inteligente de gestión de inventario para empresas. Automatiza la lectura de facturas, el cálculo del punto de pedido y facilita el contacto con proveedores, ayudando a evitar roturas de stock y exceso de almacenamiento.

## 🚀 Funcionalidades

- Visualización del stock y demanda por producto
- Cálculo automatizado del punto de pedido
- Subida y procesamiento automático de facturas PDF
- Extracción de datos con IA (OpenAI)
- Gestión por empresa con paneles individuales
- Contacto automático a proveedores (próximamente)
- Módulo de atención al cliente desde la app

## 🛠️ Tecnologías

- Streamlit
- SQLite
- PyMuPDF
- OpenAI API

## 📂 Estructura del proyecto

stock-ai/
├── app.py
├── read_invoice.py
├── users.json
├── data/
│ ├── facturas/
│ ├── facturas_procesadas/
│ └── bases_datos/
└── README.md


## 📦 Instalación

```bash
pip install -r requirements.txt
streamlit run app.py



