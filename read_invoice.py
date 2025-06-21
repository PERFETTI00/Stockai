import os
import json
import shutil
import sqlite3
import fitz  # PyMuPDF
import re
from openai import OpenAI
from datetime import datetime
import logging
from dotenv import load_dotenv

# Configuración de logging para una mejor depuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cargar variables de entorno (como OPENAI_API_KEY)
load_dotenv()

# Configuración
CARPETA_FACTURAS = "data/facturas"
CARPETA_PROCESADAS = "data/facturas_procesadas"
CARPETA_BASES_DATOS = "data/bases_datos"

# Asegurarse de que las carpetas existan
os.makedirs(CARPETA_FACTURAS, exist_ok=True)
os.makedirs(CARPETA_PROCESADAS, exist_ok=True)
os.makedirs(CARPETA_BASES_DATOS, exist_ok=True)

# Inicializa cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def limpiar_numero(valor):
    """Convierte strings como '60.000 unidades', '12,5', '1.000,25' a float."""
    if not isinstance(valor, str):
        try:
            return float(valor)
        except (ValueError, TypeError):
            logging.warning(f"No se pudo convertir a float: {valor}. Devolviendo 0.0")
            return 0.0
    
    limpio = re.sub(r"[^\d,\.]", "", valor)
    
    if "," in limpio and "." in limpio:
        if limpio.rfind(',') > limpio.rfind('.'):
            limpio = limpio.replace(".", "").replace(",", ".")
        else:
            limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    elif limpio.count(".") > 1:
        limpio = limpio.replace(".", "")
    
    try:
        return float(limpio)
    except ValueError:
        logging.warning(f"No se pudo limpiar y convertir a float: '{valor}' -> '{limpio}'. Devolviendo 0.0")
        return 0.0

def extraer_texto_pdf(ruta_pdf):
    doc = fitz.open(ruta_pdf)
    texto = ""
    for pagina in doc:
        texto += pagina.get_text()
    doc.close()
    return texto

def normalizar_nombre_empresa(nombre):
    """Normaliza el nombre de la empresa para usarlo en nombres de archivos/BD."""
    if not isinstance(nombre, str):
        return "empresa_desconocida"
    return nombre.lower().replace(" ", "_").replace(".", "").replace(",", "").strip()

# --- NUEVA FUNCIÓN: Normalizar nombre del producto usando IA ---
def normalizar_nombre_producto_ia(nombre_producto):
    """
    Normaliza el nombre de un producto utilizando la IA para estandarizarlo.
    Elimina plurales, marcas, tamaños, unidades de medida o cualquier descriptor que no sea esencial.
    """
    if not isinstance(nombre_producto, str) or not nombre_producto.strip():
        return "Producto Desconocido"

    prompt = f"""
    Normaliza el siguiente nombre de producto para que sea genérico y estandarizado, eliminando plurales, marcas, tamaños, unidades de medida o cualquier descriptor que no sea esencial para identificar el producto principal.
    Ejemplos:
    - "Mascarillas quirúrgicas IIR caja de 50 unidades" -> "Mascarilla quirúrgica"
    - "Guantes de latex talla M" -> "Guante de látex"
    - "Batas desechables azules" -> "Bata desechable"
    - "Gel hidroalcoholico 500ml" -> "Gel hidroalcohólico"
    - "Lapiz HB Staedtler" -> "Lápiz"
    - "Ordenador portatil HP Pavilion" -> "Ordenador portátil"
    
    Producto a normalizar: "{nombre_producto}"
    Devuelve solo el nombre normalizado, sin explicaciones ni texto adicional.
    """
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o", # O gpt-4, gpt-3.5-turbo. gpt-4o es bueno para esto.
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1 # Baja temperatura para resultados consistentes
        )
        normalizado = respuesta.choices[0].message.content.strip()
        # Una limpieza final por si la IA añade algo inesperado
        normalizado = re.sub(r"[^a-záéíóúüñ\d\s]", "", normalizado.lower()) # solo letras, numeros, espacios
        normalizado = re.sub(r"\s+", " ", normalizado).strip() # Multiples espacios a uno, trim
        
        return normalizado if normalizado else "Producto Desconocido"
    except Exception as e:
        logging.error(f"❌ Error al normalizar '{nombre_producto}' con IA: {e}")
        # En caso de error, volvemos a la normalización básica para no perder el dato
        return re.sub(r"[^a-záéíóúüñ\d\s]", "", nombre_producto.lower()).replace("  ", " ").strip()


def crear_base_datos_si_no_existe(nombre_empresa_normalizado):
    db_path = os.path.join(CARPETA_BASES_DATOS, f"{nombre_empresa_normalizado}.db")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_factura TEXT,
                fecha_emision TEXT,
                nombre_producto TEXT,
                cantidad REAL,
                precio_unitario REAL,
                total_producto REAL,
                total_factura REAL,
                UNIQUE(numero_factura, fecha_emision) ON CONFLICT IGNORE
            );
        """)
        conn.commit()
        logging.info(f"Base de datos '{db_path}' verificada/creada.")
    except sqlite3.Error as e:
        logging.error(f"Error al crear/conectar la BD {db_path}: {e}")
        raise
    finally:
        if conn:
            conn.close()
    return db_path

def factura_existe(db_path, numero_factura):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM facturas WHERE numero_factura = ?", (numero_factura,))
        count = cursor.fetchone()[0]
        return count > 0
    except sqlite3.Error as e:
        logging.error(f"Error al verificar duplicado en {db_path} para factura {numero_factura}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def guardar_datos_en_bd(nombre_empresa_normalizado, datos):
    if not datos.get("numero_factura"):
        logging.error("La clave 'numero_factura' no existe o está vacía en los datos extraídos.")
        raise ValueError("Datos de factura incompletos: numero_factura requerido.")
    
    numero_factura = datos["numero_factura"]
    db_path = os.path.join(CARPETA_BASES_DATOS, f"{nombre_empresa_normalizado}.db")
    
    crear_base_datos_si_no_existe(nombre_empresa_normalizado)

    if factura_existe(db_path, numero_factura):
        logging.info(f"⏭️ Factura '{numero_factura}' para '{nombre_empresa_normalizado}' ya existe en la BD. Omitiendo inserción.")
        return False
    
    if not datos.get("productos"):
        logging.warning(f"No se encontraron productos en la factura {numero_factura}. No se insertarán líneas de producto.")
        return True

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        total_factura_final = limpiar_numero(datos.get("total_factura", 0.0))

        for producto in datos["productos"]:
            # --- APLICAR NORMALIZACIÓN DEL NOMBRE DEL PRODUCTO USANDO IA AQUÍ ---
            nombre_producto_normalizado = normalizar_nombre_producto_ia(producto.get("nombre", "Producto Desconocido"))
            
            cursor.execute("""
                INSERT INTO facturas (numero_factura, fecha_emision, nombre_producto, cantidad, precio_unitario, total_producto, total_factura)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                numero_factura,
                datos.get("fecha_emision", ""),
                nombre_producto_normalizado, # Usar el nombre normalizado por IA
                limpiar_numero(producto.get("cantidad", 0)),
                limpiar_numero(producto.get("precio_unitario", 0.0)),
                limpiar_numero(producto.get("total_por_producto", 0.0)),
                total_factura_final
            ))
        
        conn.commit()
        logging.info(f"✅ Datos de factura {numero_factura} guardados en: {db_path}")
        return True
    except sqlite3.Error as e:
        logging.error(f"Error al guardar datos de la factura {numero_factura} en BD: {e}")
        raise
    finally:
        if conn:
            conn.close()

def extraer_datos_structurados(texto):
    prompt = f"""
Extrae los datos estructurados de la siguiente factura. Devuelve el resultado como JSON con las claves:
- nombre_empresa (string)
- numero_factura (string o número)
- fecha_emision (DD/MM/AAAA o similar, si no está presente, usar formato AAAA-MM-DD y dejar vacío)
- productos (lista de objetos con las claves: nombre, cantidad, precio_unitario, total_por_producto)
- total_factura (número, si no está presente, dejar vacío)

Asegúrate de que 'nombre_empresa', 'numero_factura' y 'fecha_emision' siempre existan.
Para 'productos', asegúrate de que cada objeto tenga 'nombre', 'cantidad', 'precio_unitario' y 'total_por_producto'. Si falta alguna, asigna una cadena vacía o 0.

Texto:
{texto}
"""
    try:
        respuesta = client.chat.completions.create(
            model="gpt-4", # Puedes considerar gpt-3.5-turbo para menor costo si el rendimiento es aceptable
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0 # Para resultados consistentes
        )
        contenido = respuesta.choices[0].message.content.strip()
        
        start_index = contenido.find('{')
        end_index = contenido.rfind('}')
        if start_index != -1 and end_index != -1:
            contenido = contenido[start_index : end_index + 1]
        
        datos_json = json.loads(contenido)
        return datos_json
    except json.JSONDecodeError as e:
        logging.error(f"❌ La respuesta de OpenAI no es un JSON válido:\n'{contenido}'\nError: {e}")
        raise ValueError("❌ La respuesta de OpenAI no es un JSON válido.")
    except Exception as e:
        logging.error(f"❌ Error general al llamar a OpenAI: {e}")
        raise

def procesar_factura(ruta_pdf):
    logging.info(f"\n📥 Procesando archivo: {ruta_pdf}")
    try:
        texto = extraer_texto_pdf(ruta_pdf)
        datos_raw = extraer_datos_structurados(texto)
        logging.info("📄 Datos estructurados (parcial): %s", json.dumps(datos_raw, indent=2, ensure_ascii=False)[:500] + "...")
        
        nombre_empresa_normalizado = normalizar_nombre_empresa(datos_raw.get("nombre_empresa", "empresa_desconocida"))
        
        was_inserted = guardar_datos_en_bd(nombre_empresa_normalizado, datos_raw)
        
        if was_inserted:
            mover_factura_procesada(ruta_pdf)
            return f"✅ '{os.path.basename(ruta_pdf)}' procesada y guardada."
        else:
            mover_factura_procesada(ruta_pdf) 
            return f"ℹ️ '{os.path.basename(ruta_pdf)}' (factura '{datos_raw.get('numero_factura', 'N/A')}') ya existe y fue omitida."

    except Exception as e:
        logging.error(f"❌ Error al procesar {os.path.basename(ruta_pdf)}: {e}")
        return f"❌ Error al procesar '{os.path.basename(ruta_pdf)}': {e}"

def mover_factura_procesada(ruta_pdf):
    if not os.path.exists(CARPETA_PROCESADAS):
        os.makedirs(CARPETA_PROCESADAS)
    nombre_archivo = os.path.basename(ruta_pdf)
    destino = os.path.join(CARPETA_PROCESADAS, nombre_archivo)
    shutil.move(ruta_pdf, destino)
    logging.info(f"📦 Factura movida a: {destino}")

def procesar_facturas_en_carpeta():
    """Función principal para procesar todas las facturas pendientes."""
    archivos = [f for f in os.listdir(CARPETA_FACTURAS) if f.endswith(".pdf")]
    if not archivos:
        logging.info("⚠️ No se encontraron archivos PDF en la carpeta de facturas pendientes.")
        return "No se encontraron facturas pendientes de procesar."
    
    resultados_procesamiento = []
    for archivo in archivos:
        ruta_pdf = os.path.join(CARPETA_FACTURAS, archivo)
        resultado_individual = procesar_factura(ruta_pdf)
        resultados_procesamiento.append(resultado_individual)
    
    return "\n".join(resultados_procesamiento)