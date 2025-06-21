import os
import sqlite3

def normalizar_nombre_archivo(nombre):
    return nombre.lower().replace(" ", "_").replace(".", "").replace(",", "").replace("-", "_")

def guardar_datos_en_base(datos):
    nombre_empresa = datos.get("nombre_empresa")
    if not nombre_empresa:
        raise ValueError("La clave 'nombre_empresa' no existe o está vacía.")

    nombre_normalizado = normalizar_nombre_archivo(nombre_empresa)
    base_datos = f"data/bases_datos/{nombre_normalizado}.db"

    conn = sqlite3.connect(base_datos)
    cursor = conn.cursor()

    # ✅ Crear tabla con campo numero_factura
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS facturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_factura TEXT,
        fecha_emision TEXT,
        nombre_producto TEXT,
        cantidad INTEGER,
        precio_unitario REAL,
        total_producto REAL,
        total_factura REAL
    )
    """)

    for producto in datos["productos"]:
        cursor.execute("""
        INSERT INTO facturas (
            numero_factura,
            fecha_emision,
            nombre_producto,
            cantidad,
            precio_unitario,
            total_producto,
            total_factura
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datos["numero_factura"],
            datos["fecha_emision"],
            producto["nombre"],
            producto["cantidad"],
            producto["precio_unitario"],
            producto["total_por_producto"],
            datos["total_factura"]
        ))

    conn.commit()
    conn.close()

    print(f"✅ Datos guardados en la base de datos: {base_datos}")
