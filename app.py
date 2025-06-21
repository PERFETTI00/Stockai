import streamlit as st
import sqlite3
import os
import pandas as pd
import json
from datetime import datetime
import base64 # Importa la librería base64

# --- Configuraciones ---
CARPETA_BASES_DATOS = "data/bases_datos"
TIEMPO_REPOSICION_DIAS = 5  # estándar

# Definir la ruta de la carpeta de facturas para el procesamiento
CARPETA_FACTURAS_PENDIENTES = "data/facturas"
CARPETA_FACTURAS_PROCESADAS = "data/facturas_procesadas"

# Importar funciones de procesamiento de facturas desde read_invoice.py
from read_invoice import procesar_facturas_en_carpeta # Importa la función principal

# --- Funciones de Usuarios ---
def cargar_usuarios():
    with open("users.json", "r") as f:
        return json.load(f)

USUARIOS = cargar_usuarios()

# --- Funciones de datos ---
def obtener_datos_empresa(nombre_empresa):
    db_path = os.path.join(CARPETA_BASES_DATOS, f"{nombre_empresa}.db")
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM facturas", conn)
    conn.close()
    return df

def calcular_punto_pedido(df):
    if df.empty:
        return pd.DataFrame()

    df["fecha_emision"] = pd.to_datetime(df["fecha_emision"], errors="coerce")
    df["cantidad"] = pd.to_numeric(df["cantidad"].str.extract(r"([\d,.]+)")[0].str.replace(".", "").str.replace(",", "."), errors='coerce')
    df = df.dropna(subset=["fecha_emision", "nombre_producto", "cantidad"])

    df_grouped = df.groupby(["nombre_producto", "fecha_emision"]).agg({"cantidad": "sum"}).reset_index()

    resultados = []
    for producto, grupo in df_grouped.groupby("nombre_producto"):
        grupo = grupo.sort_values("fecha_emision")
        if len(grupo) < 2:
            continue

        total_dias = (grupo["fecha_emision"].max() - grupo["fecha_emision"].min()).days
        total_unidades = grupo["cantidad"].sum()

        if total_dias == 0:
            demanda_diaria = total_unidades
        else:
            demanda_diaria = total_unidades / total_dias

        stock_seguridad = demanda_diaria * 7 * 0.2
        punto_pedido = (demanda_diaria * TIEMPO_REPOSICION_DIAS) + stock_seguridad

        resultados.append({
            "Producto": producto,
            "Demanda diaria estimada": round(demanda_diaria, 2),
            "Stock de seguridad": int(round(stock_seguridad)),
            "Punto de pedido (unidades)": int(round(punto_pedido))
        })

    return pd.DataFrame(resultados)

# --- FUNCIÓN DE UTILIDAD: Contar facturas pendientes ---
def contar_facturas_pendientes():
    # Asegúrate de que la carpeta exista antes de intentar listar su contenido
    if not os.path.exists(CARPETA_FACTURAS_PENDIENTES):
        return 0
    return len([f for f in os.listdir(CARPETA_FACTURAS_PENDIENTES) if f.endswith(".pdf")])


# --- FUNCIÓN DE UTILIDAD: Eliminar factura de la base de datos ---
def eliminar_factura_de_db(nombre_empresa, factura_id):
    db_path = os.path.join(CARPETA_BASES_DATOS, f"{nombre_empresa}.db")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM facturas WHERE id = ?", (factura_id,))
        conn.commit()
        st.success(f"Factura con ID {factura_id} eliminada de la base de datos.")
    except sqlite3.Error as e:
        st.error(f"Error al eliminar factura con ID {factura_id}: {e}")
    finally:
        if conn:
            conn.close()

# --- Login ---
def login():
    st.title("🔐 Stock AI - Login")
    usuario = st.text_input("Usuario")
    clave = st.text_input("Contraseña", type="password")
    if st.button("Iniciar sesión"):
        if usuario in USUARIOS and USUARIOS[usuario]["password"] == clave:
            st.session_state.usuario = usuario
            st.success(f"Bienvenido, {usuario}")
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

# --- Dashboard para Empresas ---
def mostrar_dashboard_empresa(nombre_empresa):
    st.title(f"📦 Stock AI - {nombre_empresa.replace('_', ' ').title()}")

    tabs = st.tabs(["📊 Punto de Pedido", "📄 Ver Facturas"])

    with tabs[0]: # Punto de Pedido
        df = obtener_datos_empresa(nombre_empresa)
        if df.empty:
            st.info("🔍 No hay facturas disponibles. Sube una para comenzar.")
        else:
            tabla = calcular_punto_pedido(df)
            if tabla.empty:
                st.warning("⚠️ No hay suficiente historial para calcular el punto de pedido.")
            else:
                st.markdown("<h4 style='color:#4CAF50'>Punto de Pedido Calculado</h4>", unsafe_allow_html=True)
                st.dataframe(tabla, use_container_width=True)

    with tabs[1]: # Ver Facturas - MODIFICADA para incluir eliminar
        df = obtener_datos_empresa(nombre_empresa)
        if df.empty:
            st.warning("No hay facturas para mostrar.")
        else:
            st.subheader("📄 Historial de Facturas con Filtros y Eliminación")

            df["fecha_emision"] = pd.to_datetime(df["fecha_emision"], errors="coerce")
            df["id"] = pd.to_numeric(df["id"], errors="coerce")

            col1, col2 = st.columns(2)
            with col1:
                fecha_min = df["fecha_emision"].min() if not df["fecha_emision"].empty else datetime.now().date()
                fecha_max = df["fecha_emision"].max() if not df["fecha_emision"].empty else datetime.now().date()
                if fecha_min == fecha_max:
                    fechas_default = [fecha_min, fecha_max + pd.Timedelta(days=1)]
                else:
                    fechas_default = [fecha_min, fecha_max]
                fechas = st.date_input("Rango de fechas", fechas_default)
            with col2:
                productos = df["nombre_producto"].dropna().unique().tolist()
                producto_sel = st.selectbox("Producto", ["Todos"] + productos)

            df_filtrado = df.copy()
            if fechas and len(fechas) == 2:
                start, end = pd.to_datetime(fechas[0]), pd.to_datetime(fechas[1])
                df_filtrado = df_filtrado[(df_filtrado["fecha_emision"] >= start) & (df_filtrado["fecha_emision"] <= end)]
            if producto_sel != "Todos":
                df_filtrado = df_filtrado[df_filtrado["nombre_producto"] == producto_sel]

            st.dataframe(df_filtrado.sort_values("fecha_emision", ascending=False), use_container_width=True)

            st.markdown("---")
            st.subheader("Eliminar Factura por ID")
            factura_id_a_eliminar = st.number_input("Introduce el ID de la factura a eliminar:", min_value=1, step=1, value=None, format="%d", help="Encuentra el ID en la primera columna de la tabla superior.")

            if st.button("🗑️ Eliminar Factura Seleccionada"):
                if factura_id_a_eliminar:
                    if factura_id_a_eliminar in df_filtrado["id"].values:
                        eliminar_factura_de_db(nombre_empresa, int(factura_id_a_eliminar))
                        st.rerun()
                    else:
                        st.warning("El ID de factura introducido no se encuentra en la tabla mostrada o ya fue eliminada. Por favor, introduce un ID válido.")
                else:
                    st.warning("Por favor, introduce un ID de factura para eliminar.")


# --- NUEVA SECCIÓN: Gestión de Facturas para el Administrador ---
def mostrar_gestion_facturas_admin():
    st.title("⚙️ Stock AI - Gestión de Facturas")

    st.subheader("Subir y Procesar Facturas Pendientes")
    st.info("Sube aquí las facturas de CUALQUIER empresa. El sistema las identificará y procesará automáticamente.")

    # Subir Factura
    archivo = st.file_uploader("Selecciona un archivo PDF", type="pdf", key="admin_file_uploader")
    if archivo:
        os.makedirs(CARPETA_FACTURAS_PENDIENTES, exist_ok=True)
        ruta_destino = os.path.join(CARPETA_FACTURAS_PENDIENTES, archivo.name)
        with open(ruta_destino, "wb") as f:
            f.write(archivo.getbuffer())
        st.success(f"Factura '{archivo.name}' subida correctamente. Pulsa 'Procesar Facturas Ahora' para que se añada a la base de datos.")

    st.markdown("---")

    # Procesar Facturas
    st.subheader("Procesar Facturas Pendientes")

    num_facturas_pendientes_actual = contar_facturas_pendientes()

    if num_facturas_pendientes_actual > 0:
        st.warning(f"Hay {num_facturas_pendientes_actual} factura(s) pendiente(s) de procesar.")
    else:
        st.info("No hay facturas pendientes de procesar en este momento.")

    if st.button("🚀 Procesar Facturas Ahora", key="process_invoices_admin_button"):
        with st.spinner("Procesando facturas... Esto puede tomar un momento."):
            try:
                resumen_procesamiento = procesar_facturas_en_carpeta()
                st.success("🎉 ¡Proceso de facturas completado!")
                st.text(resumen_procesamiento)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Ocurrió un error general al procesar las facturas: {e}")
        st.info("Para ver los cambios, elije una empresa en el menú lateral y navega a sus pestañas.")


# --- Función para convertir imagen a Base64 ---
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            # Detectar el tipo de imagen para el prefijo Base64 (puedes ajustar según tu logo)
            # Para PNG: data:image/png;base64,
            # Para JPG: data:image/jpeg;base64,
            # Se asume PNG por defecto si el nombre es logo.png
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith((".jpg", ".jpeg")):
                mime_type = "image/jpeg"
            else:
                mime_type = "image/x-icon" # Para .ico o tipos desconocidos, o puedes ajustar

            encoded_string = base64.b64encode(img_file.read()).decode()
            return f"data:{mime_type};base64,{encoded_string}"
    except FileNotFoundError:
        st.error(f"Error: No se encontró el archivo de logo en la ruta: {image_path}")
        return None
    except Exception as e:
        st.error(f"Error al codificar la imagen en Base64: {e}")
        return None

# --- Obtener la cadena Base64 del logo al inicio ---
# Asegúrate de que 'logo.png' esté en la misma carpeta que tu script de Streamlit
LOGO_BASE64_SRC = get_base64_image("logo.png")

# --- App principal ---

# --- INYECTAR ESTILOS CSS PARA EL LOGO REDONDO ---
st.markdown("""
<style>
    .logo-redondo-container {
        border: 3px solid #4CAF50; /* Color y grosor del marco (verde en este caso) */
        border-radius: 50%; /* Hace el marco circular */
        width: 150px; /* Ancho del contenedor */
        height: 150px; /* Alto del contenedor */
        overflow: hidden; /* Oculta cualquier parte de la imagen que sobresalga del círculo */
        display: flex;
        justify-content: center;
        align-items: center;
        margin: 10px auto; /* Centra el logo en el sidebar y añade un poco de margen */
    }
    .logo-redondo-img {
        width: 100%; /* La imagen ocupa todo el ancho del contenedor */
        height: 100%; /* La imagen ocupa todo el alto del contenedor */
        object-fit: cover; /* Asegura que la imagen cubra el área sin distorsionarse */
        border-radius: 50%; /* Hace la imagen también circular */
    }
</style>
""", unsafe_allow_html=True)


if "usuario" not in st.session_state:
    login()
else:
    usuario = st.session_state.usuario
    rol = USUARIOS[usuario]["rol"]

    # LOGO EN EL SIDEBAR (Solo visible después de iniciar sesión)
    # Usamos la cadena Base64 del logo si se pudo generar
    if LOGO_BASE64_SRC:
        st.sidebar.markdown(f"""
        <div class="logo-redondo-container">
            <img class="logo-redondo-img" src="{LOGO_BASE64_SRC}" alt="Logo de Stock AI">
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.warning("No se pudo cargar el logo.") # Mensaje si falla la carga del logo

    st.sidebar.title("📋 Menú")

    if rol == "admin":
        # Nuevas opciones en el sidebar para el administrador
        st.sidebar.subheader("Opciones de Administrador")
        opcion_admin = st.sidebar.radio(
            "Selecciona una acción:",
            ("Ver Dashboards de Empresas", "Gestionar Carga de Facturas")
        )

        if opcion_admin == "Ver Dashboards de Empresas":
            empresas_disponibles = [u for u in USUARIOS if USUARIOS[u]["rol"] == "empresa"]
            if empresas_disponibles:
                empresa_seleccionada = st.sidebar.selectbox("Seleccionar empresa", empresas_disponibles, key="admin_empresa_select")
                mostrar_dashboard_empresa(empresa_seleccionada)
            else:
                st.sidebar.warning("No hay empresas registradas para administrar.")
                st.title("Panel de Administración")
                st.info("No hay empresas configuradas. Por favor, añada usuarios con rol 'empresa' en `users.json`.")
        elif opcion_admin == "Gestionar Carga de Facturas":
            mostrar_gestion_facturas_admin()

    else: # Rol "empresa"
        mostrar_dashboard_empresa(usuario)

    with st.sidebar.expander("📞 Servicio y Atención al Cliente"):
        st.markdown("¿Necesitas ayuda?")
        st.markdown("- 📧 soporte@stockai.com")
        st.markdown("- 📱 WhatsApp: +34 600 123 456")
        st.markdown("- 🕒 Lunes a Viernes, 9h - 18h")
        st.markdown("[Formulario de contacto](https://stockai.com/contacto)")