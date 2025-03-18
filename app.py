import streamlit as st
import pandas as pd
import sqlite3
import datetime
import random
import string
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from contextlib import contextmanager
import importlib.metadata
import sys



# En la sección de datas
from PyInstaller.utils.hooks import collect_data_files

streamlit_datas = collect_data_files('streamlit')
datas = streamlit_datas + [
    ("facturacion_capilar.db", "."),
    ("*.pdf", ".")
]

# Solución para evitar errores de metadatos en PyInstaller
if getattr(sys, 'frozen', False):
    import importlib
    importlib.reload(importlib.metadata)

# Configuración de la empresa
EMPRESA = {
    "nombre": "Cuidado Capilar RD",
    "direccion": "C.8 con esquina 29 #59 Pueblo Nuevo\nLos Alcarrizos",
    "telefono": "(829) 719-3863",
    
}
DESCUENTO = 50
COLOR_PRINCIPAL = HexColor("#2A2A2A")  # Negro oscuro
COLOR_SECUNDARIO = HexColor("#F5F5F5")  # Gris claro

# Configuración de la base de datos
@contextmanager
def database_connection():
    conn = sqlite3.connect("facturacion_capilar.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with database_connection() as conn:
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT UNIQUE, 
            precio REAL CHECK(precio > 0)
        )''') 
        
        c.execute('''CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            fecha TEXT, 
            total REAL CHECK(total > 0),
            numero_factura TEXT UNIQUE,
            descuento REAL DEFAULT 0)
        ''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS ventas_detalle (
            venta_id INTEGER,
            producto_id INTEGER,
            cantidad INTEGER CHECK(cantidad > 0),
            precio_unitario REAL CHECK(precio_unitario > 0),
            FOREIGN KEY(venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
            FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE SET NULL)
        ''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            cedula TEXT UNIQUE,
            telefono TEXT,
            direccion TEXT,
            codigo_descuento TEXT UNIQUE,
            activo BOOLEAN DEFAULT 1)
        ''')
        conn.commit()

class ProductoManager:
    @staticmethod
    def obtener_productos():
        with database_connection() as conn:
            return conn.execute("SELECT id, nombre, precio FROM productos").fetchall()

    @staticmethod
    def agregar_producto(nombre, precio):
        try:
            with database_connection() as conn:
                conn.execute("INSERT INTO productos (nombre, precio) VALUES (?, ?)", (nombre, precio))
                conn.commit()
                return True, "Producto agregado exitosamente"
        except sqlite3.IntegrityError:
            return False, "Error: El nombre del producto ya existe"
        except Exception as e:
            return False, f"Error inesperado: {str(e)}"

    @staticmethod
    def eliminar_producto(producto_id):
        try:
            with database_connection() as conn:
                conn.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
                conn.commit()
                return True, "Producto eliminado exitosamente"
        except Exception as e:
            return False, f"No se puede eliminar: {str(e)}"

    @staticmethod
    def actualizar_producto(producto_id, nuevo_nombre, nuevo_precio):
        try:
            with database_connection() as conn:
                conn.execute("UPDATE productos SET nombre = ?, precio = ? WHERE id = ?", 
                           (nuevo_nombre, nuevo_precio, producto_id))
                conn.commit()
                return True, "Producto actualizado exitosamente"
        except sqlite3.IntegrityError:
            return False, "Error: El nuevo nombre ya existe"
        except Exception as e:
            return False, f"Error inesperado: {str(e)}"

class VentaManager:
    @staticmethod
    def registrar_venta(factura):
        try:
            with database_connection() as conn:
                fecha = datetime.date.today().isoformat()
                total = sum(item['subtotal'] for item in factura['items'])
                descuento = DESCUENTO if factura['descuento'] else 0
                total -= descuento
                numero_factura = f"FACT-{datetime.datetime.now().strftime('%d%m%y%H%M')}"
                
                c = conn.execute('''INSERT INTO ventas 
                                  (fecha, total, numero_factura, descuento)
                                  VALUES (?, ?, ?, ?)''',
                                 (fecha, total, numero_factura, descuento))
                venta_id = c.lastrowid
                
                for item in factura['items']:
                    conn.execute('''INSERT INTO ventas_detalle 
                                  (venta_id, producto_id, cantidad, precio_unitario)
                                  VALUES (?, ?, ?, ?)''',
                               (venta_id, item['producto_id'], item['cantidad'], item['precio']))
                conn.commit()
                return True, numero_factura
        except Exception as e:
            return False, f"Error al registrar venta: {str(e)}"

    @staticmethod
    def obtener_ventas_por_fecha(fecha):
        with database_connection() as conn:
            query = '''SELECT v.numero_factura, v.total, p.nombre, vd.cantidad, 
                      vd.precio_unitario, v.descuento
                      FROM ventas v
                      JOIN ventas_detalle vd ON v.id = vd.venta_id
                      JOIN productos p ON vd.producto_id = p.id
                      WHERE v.fecha = ?'''
            return conn.execute(query, (fecha,)).fetchall()

class ClienteManager:
    @staticmethod
    def obtener_clientes(activos=True):
        with database_connection() as conn:
            query = "SELECT * FROM clientes WHERE activo = ?" if activos else "SELECT * FROM clientes"
            params = (1,) if activos else ()
            return conn.execute(query, params).fetchall()

    @staticmethod
    def generar_codigo_descuento(nombre):
        iniciales = ''.join([part[0] for part in nombre.split()[:2]]).upper()
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{iniciales}-{random_part}"

    @staticmethod
    def agregar_cliente(nombre, cedula, telefono, direccion):
        try:
            codigo = ClienteManager.generar_codigo_descuento(nombre)
            with database_connection() as conn:
                conn.execute('''INSERT INTO clientes 
                             (nombre, cedula, telefono, direccion, codigo_descuento)
                             VALUES (?, ?, ?, ?, ?)''',
                             (nombre, cedula, telefono, direccion, codigo))
                conn.commit()
                return True, codigo
        except sqlite3.IntegrityError as e:
            return False, "Error: Cédula o código ya existen"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    def actualizar_cliente(cliente_id, nombre, cedula, telefono, direccion):
        try:
            with database_connection() as conn:
                conn.execute('''UPDATE clientes SET
                             nombre = ?, cedula = ?, telefono = ?, direccion = ?
                             WHERE id = ?''',
                             (nombre, cedula, telefono, direccion, cliente_id))
                conn.commit()
                return True, "Cliente actualizado"
        except sqlite3.IntegrityError:
            return False, "Error: Cédula ya existe"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    def eliminar_cliente(cliente_id):
        try:
            with database_connection() as conn:
                conn.execute("UPDATE clientes SET activo = 0 WHERE id = ?", (cliente_id,))
                conn.commit()
                return True, "Cliente desactivado"
        except Exception as e:
            return False, f"Error: {str(e)}"

def generar_pdf(factura_data, numero_factura, total):
    pdf_output = f"factura_{numero_factura}.pdf"
    doc = SimpleDocTemplate(pdf_output, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=COLOR_PRINCIPAL,
        alignment=TA_CENTER
    )
    
    elements.append(Paragraph(EMPRESA["nombre"], header_style))
    elements.append(Paragraph(EMPRESA["direccion"], styles['Normal']))
    elements.append(Paragraph(f"Tel: {EMPRESA['telefono']}", styles['Normal']))
    elements.append(Paragraph(f"RNC: {EMPRESA['rnc']}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    elements.append(Paragraph(f"Factura N°: {numero_factura}", styles['Heading3']))
    elements.append(Paragraph(f"Fecha: {datetime.date.today().strftime('%d/%m/%Y')}", styles['Normal']))
    
    if factura_data['descuento']:
        elements.append(Paragraph(f"Código descuento: {factura_data['codigo_usado']}", styles['Normal']))
        elements.append(Paragraph(f"Descuento aplicado: ${DESCUENTO:.2f}", styles['Normal']))
    
    elements.append(Spacer(1, 24))
    
    # Tabla modificada con las columnas requeridas
    table_data = [["Producto", "Cantidad", "Precio", "Total"]]
    for item in factura_data['items']:
        table_data.append([
            item['nombre'][:35],
            str(item['cantidad']),
            f"${item['precio']:.2f}",
            f"${item['subtotal']:.2f}"
        ])
    
    table = Table(table_data, colWidths=[220, 60, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_PRINCIPAL),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), COLOR_SECUNDARIO),
        ('GRID', (0,0), (-1,-1), 1, COLOR_PRINCIPAL)
    ]))
    elements.append(table)
    
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"Total: ${total:.2f}", styles['Heading3']))
    elements.append(Paragraph("¡Gracias por su preferencia!", styles['Normal']))
    doc.build(elements)
    return pdf_output

def generar_reporte_pdf(ventas_data, fecha_reporte, total_dia):
    pdf_output = f"rep_{fecha_reporte.replace('/', '-')}.pdf"
    doc = SimpleDocTemplate(pdf_output, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=COLOR_PRINCIPAL,
        alignment=TA_CENTER
    )
    
    elements.append(Paragraph(EMPRESA["nombre"], header_style))
    elements.append(Paragraph(f"Fecha del reporte: {fecha_reporte}", styles['Heading4']))
    elements.append(Spacer(1, 12))
    
    facturas = {}
    for venta in ventas_data:
        num_fact = venta[0]
        if num_fact not in facturas:
            facturas[num_fact] = {
                'total': venta[1],
                'descuento': venta[5],
                'productos': []
            }
        facturas[num_fact]['productos'].append(venta[2:5])
    
    for num_fact, datos in facturas.items():
        elements.append(Paragraph(f"Factura: {num_fact}", styles['Heading4']))
        elements.append(Paragraph(f"Total: ${datos['total']:.2f} | Descuento: ${datos['descuento']:.2f}", styles['Normal']))
        
        # Tabla modificada para el reporte
        table_data = [["Producto", "Cantidad", "Precio", "Total"]]
        for prod in datos['productos']:
            total_producto = prod[1] * prod[2]  # Cantidad * Precio Unitario
            table_data.append([
                prod[0][:35],
                str(prod[1]),
                f"${prod[2]:.2f}",
                f"${total_producto:.2f}"
            ])
        
        table = Table(table_data, colWidths=[220, 60, 80, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_PRINCIPAL),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BACKGROUND', (0,1), (-1,-1), COLOR_SECUNDARIO),
            ('GRID', (0,0), (-1,-1), 1, COLOR_PRINCIPAL)
        ]))
        elements.append(table)
        elements.append(Spacer(1, 10))
    
    elements.append(Paragraph(f"Total del día: ${total_dia:.2f}", styles['Heading3']))
    doc.build(elements)
    return pdf_output

def pantalla_facturacion():
    st.title("📄 Sistema de Facturación")
    
    if 'factura' not in st.session_state:
        st.session_state.factura = {
            'items': [],
            'descuento': False,
            'codigo_usado': None
        }
    
    productos = ProductoManager.obtener_productos()
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("Agregar Productos")
        if productos:
            producto_seleccionado = st.selectbox(
                "Seleccionar producto:", 
                productos, 
                format_func=lambda p: f"{p[1]} - ${p[2]:.2f}"
            )
            cantidad = st.number_input("Cantidad:", min_value=1, value=1)
            
            if st.button("Agregar a la factura"):
                producto_id = producto_seleccionado[0]
                nombre = producto_seleccionado[1]
                precio = producto_seleccionado[2]
                subtotal = cantidad * precio
                
                nuevo_item = {
                    'producto_id': producto_id,
                    'nombre': nombre,
                    'precio': precio,
                    'cantidad': cantidad,
                    'subtotal': subtotal
                }
                
                st.session_state.factura['items'].append(nuevo_item)
                st.success("Producto agregado a la factura")
        
        st.subheader("Aplicar Descuento")
        codigo = st.text_input("Código de descuento:")
        if st.button("Aplicar Descuento"):
            with database_connection() as conn:
                cliente = conn.execute("SELECT * FROM clientes WHERE codigo_descuento = ?", (codigo,)).fetchone()
                if cliente:
                    st.session_state.factura['descuento'] = True
                    st.session_state.factura['codigo_usado'] = codigo
                    st.success(f"Descuento de ${DESCUENTO} aplicado")
                else:
                    st.error("Código inválido o ya utilizado")
        
        if st.session_state.factura['descuento']:
            st.info(f"Código aplicado: {st.session_state.factura['codigo_usado']}")
            if st.button("Remover Descuento"):
                st.session_state.factura['descuento'] = False
                st.session_state.factura['codigo_usado'] = None
                st.rerun()
    
    with col2:
        st.subheader("Factura Actual")
        if st.session_state.factura['items']:
            df = pd.DataFrame(st.session_state.factura['items'])
            # Mostrar solo las columnas requeridas
            st.dataframe(df[['nombre', 'cantidad', 'subtotal']]
                         .rename(columns={
                             'nombre': 'Producto',
                             'cantidad': 'Cantidad',
                             'subtotal': 'Total'
                         }), 
                         hide_index=True)
            
            total = sum(item['subtotal'] for item in st.session_state.factura['items'])
            
            if st.session_state.factura['descuento']:
                st.write(f"Subtotal: ${total:.2f}")
                total -= DESCUENTO
                st.write(f"Descuento: -${DESCUENTO:.2f}")
            
            st.metric("Total a Pagar", f"${max(total, 0):.2f}")
            
            if st.button("Finalizar Venta", type="primary"):
                success, result = VentaManager.registrar_venta(st.session_state.factura)
                if success:
                    pdf_path = generar_pdf(st.session_state.factura, result, total)
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "Descargar Factura",
                            f,
                            file_name=f"factura_{result}.pdf",
                            mime="application/pdf"
                        )
                    st.session_state.factura = {'items': [], 'descuento': False, 'codigo_usado': None}
                    st.success("Venta registrada exitosamente")
                else:
                    st.error(result)
            
            if st.button("Limpiar Factura"):
                st.session_state.factura = {'items': [], 'descuento': False, 'codigo_usado': None}
                st.rerun()
        else:
            st.info("Agrega productos para comenzar una factura")

def pantalla_gestion_productos():
    st.title("🛠️ Gestión de Productos")
    opcion = st.sidebar.radio("Opciones", ["Agregar", "Editar", "Eliminar"])
    
    if opcion == "Agregar":
        st.subheader("Nuevo Producto")
        with st.form("nuevo_producto"):
            nombre = st.text_input("Nombre del producto")
            precio = st.number_input("Precio", min_value=0.01, format="%.2f")
            if st.form_submit_button("Guardar"):
                success, mensaje = ProductoManager.agregar_producto(nombre, precio)
                if success:
                    st.success(mensaje)
                else:
                    st.error(mensaje)
    
    elif opcion == "Editar":
        st.subheader("Editar Producto")
        productos = ProductoManager.obtener_productos()
        if productos:
            producto_seleccionado = st.selectbox(
                "Seleccionar producto:",
                productos,
                format_func=lambda p: f"{p[1]} - ${p[2]:.2f}"
            )
            nuevo_nombre = st.text_input("Nuevo nombre", value=producto_seleccionado[1])
            nuevo_precio = st.number_input(
                "Nuevo precio", 
                min_value=0.01, 
                value=float(producto_seleccionado[2]),
                format="%.2f"
            )
            if st.button("Actualizar"):
                success, mensaje = ProductoManager.actualizar_producto(
                    producto_seleccionado[0],
                    nuevo_nombre,
                    nuevo_precio
                )
                if success:
                    st.success(mensaje)
                else:
                    st.error(mensaje)
        else:
            st.warning("No hay productos registrados")
    
    elif opcion == "Eliminar":
        st.subheader("Eliminar Producto")
        productos = ProductoManager.obtener_productos()
        if productos:
            producto_seleccionado = st.selectbox(
                "Seleccionar producto a eliminar:",
                productos,
                format_func=lambda p: f"{p[1]} - ${p[2]:.2f}"
            )
            if st.button("Eliminar", type="primary"):
                success, mensaje = ProductoManager.eliminar_producto(producto_seleccionado[0])
                if success:
                    st.success(mensaje)
                else:
                    st.error(mensaje)
        else:
            st.warning("No hay productos registrados")

def pantalla_gestion_clientes():
    st.title("👥 Gestión de Clientes")
    opcion = st.sidebar.radio("Opciones", ["Registrar", "Editar", "Eliminar"])
    
    if opcion == "Registrar":
        st.subheader("Nuevo Cliente")
        with st.form("nuevo_cliente"):
            nombre = st.text_input("Nombre completo*")
            cedula = st.text_input("Cédula*")
            telefono = st.text_input("Teléfono")
            direccion = st.text_area("Dirección")
            
            if st.form_submit_button("Registrar"):
                if nombre and cedula:
                    success, resultado = ClienteManager.agregar_cliente(nombre, cedula, telefono, direccion)
                    if success:
                        st.success("Cliente registrado exitosamente")
                        st.markdown(f"""
                        **Detalles del cliente:**
                        - Nombre: {nombre}
                        - Cédula: {cedula}
                        - Código Descuento: `{resultado}`
                        """)
                    else:
                        st.error(resultado)
                else:
                    st.error("Campos obligatorios (*) requeridos")
    
    elif opcion == "Editar":
        st.subheader("Editar Cliente")
        clientes = ClienteManager.obtener_clientes()
        if clientes:
            cliente_seleccionado = st.selectbox(
                "Seleccionar cliente:",
                clientes,
                format_func=lambda c: f"{c[1]} - {c[2]} (Código: {c[5]})"
            )
            
            with st.form("editar_cliente"):
                st.markdown(f"**Código de descuento actual:** `{cliente_seleccionado[5]}`")
                nuevo_nombre = st.text_input("Nombre*", value=cliente_seleccionado[1])
                nueva_cedula = st.text_input("Cédula*", value=cliente_seleccionado[2])
                nuevo_telefono = st.text_input("Teléfono", value=cliente_seleccionado[3])
                nueva_direccion = st.text_area("Dirección", value=cliente_seleccionado[4])
                
                if st.form_submit_button("Actualizar"):
                    success, mensaje = ClienteManager.actualizar_cliente(
                        cliente_seleccionado[0],
                        nuevo_nombre,
                        nueva_cedula,
                        nuevo_telefono,
                        nueva_direccion
                    )
                    if success:
                        st.success(f"{mensaje} - Código mantiene: `{cliente_seleccionado[5]}`")
                    else:
                        st.error(mensaje)
        else:
            st.warning("No hay clientes registrados")
    
    elif opcion == "Eliminar":
        st.subheader("Eliminar Cliente")
        clientes = ClienteManager.obtener_clientes()
        if clientes:
            cliente_seleccionado = st.selectbox(
                "Seleccionar cliente a eliminar:",
                clientes,
                format_func=lambda c: f"{c[1]} - Código: {c[5]}"
            )
            
            if st.button("Confirmar Eliminación", type="primary"):
                success, mensaje = ClienteManager.eliminar_cliente(cliente_seleccionado[0])
                if success:
                    st.success(f"{mensaje} - Código eliminado: `{cliente_seleccionado[5]}`")
                else:
                    st.error(mensaje)
        else:
            st.warning("No hay clientes registrados")

def pantalla_reportes():
    st.title("📊 Reportes de Ventas")
    fecha = st.date_input("Seleccionar fecha", datetime.date.today())
    
    if st.button("Generar Reporte"):
        ventas = VentaManager.obtener_ventas_por_fecha(fecha.isoformat())
        
        if ventas:
            df = pd.DataFrame(ventas, columns=[
                "N° Factura", "Total", "Producto", "Cantidad", "P. Unitario", "Descuento"
            ])
            
            # Calcular total por producto
            df['Total Producto'] = df['Cantidad'] * df['P. Unitario']
            
            df_productos = df.groupby('Producto').agg({
                'Cantidad': 'sum',
                'Total Producto': 'sum'
            }).reset_index()
            
            total_dia = df['Total'].sum()
            descuentos = df['Descuento'].sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total del día", f"${total_dia:.2f}")
            with col2:
                st.metric("Unidades vendidas", df['Cantidad'].sum())
            with col3:
                st.metric("Descuentos aplicados", f"${descuentos:.2f}")
            
            st.subheader("Análisis por Producto")
            tab1, tab2 = st.tabs(["Cantidad Vendida", "Contribución al Total"])
            
            with tab1:
                st.bar_chart(df_productos, x="Producto", y="Cantidad", color="#2A2A2A")
            
            with tab2:
                st.bar_chart(df_productos, x="Producto", y="Total Producto", color="#4A4A4A")
            
            st.subheader("Detalle Completo")
            st.dataframe(df[['N° Factura', 'Producto', 'Cantidad', 'P. Unitario', 'Total Producto']]
                         .rename(columns={
                             'P. Unitario': 'Precio',
                             'Total Producto': 'Total'
                         }), 
                         hide_index=True, use_container_width=True)
            
            pdf_path = generar_reporte_pdf(ventas, fecha.strftime("%d-%m-%Y"), total_dia)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "Descargar Reporte Completo",
                    f,
                    file_name=f"reporte_{fecha.strftime('%d%m%y')}.pdf",
                    mime="application/pdf"
                )
        else:
            st.info("No hay ventas registradas para esta fecha")

def main():
    init_db()
    st.set_page_config(page_title="Cuidado Capilar RD", page_icon="💇♀️", layout="wide")
    st.sidebar.title("Menú Principal")
    menu = st.sidebar.radio(
        "Seleccionar módulo:",
        ["Facturación", "Gestión de Productos", "Gestión de Clientes", "Reportes"]
    )
    
    if menu == "Facturación":
        pantalla_facturacion()
    elif menu == "Gestión de Productos":
        pantalla_gestion_productos()
    elif menu == "Gestión de Clientes":
        pantalla_gestion_clientes()
    elif menu == "Reportes":
        pantalla_reportes()

if __name__ == "__main__":
    main()