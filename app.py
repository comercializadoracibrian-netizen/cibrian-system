import os
import subprocess
from flask import Flask, request, render_template_string
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image, ImageOps
from datetime import datetime

app = Flask(__name__)

# En la nube, las fotos se procesarán en una carpeta temporal antes de ir a Drive si lo deseas,
# por ahora creamos una ruta local en el servidor de Render para asegurar que el código corra.
RUTA_BASE = "./registros"
os.makedirs(RUTA_BASE, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Revisiones LRM</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f0f4f4; padding: 20px; margin: 0; }
        .container { max-width: 600px; margin: 20px auto; background: white; padding: 30px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
        h2 { color: #004d4d; border-bottom: 3px solid #004d4d; padding-bottom: 12px; text-align: center; font-size: 24px; }
        label { font-weight: bold; color: #333; display: block; margin-top: 15px; font-size: 16px; }
        .form-control { width: 100%; padding: 14px; margin-top: 8px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 10px; font-size: 16px; box-sizing: border-box; -webkit-appearance: none; }
        .btn-verde { background-color: #004d4d; color: white; width: 100%; padding: 18px; border: none; border-radius: 12px; font-size: 18px; font-weight: bold; cursor: pointer; margin-top: 15px; transition: background 0.2s; }
        .btn-verde:active { background-color: #003333; }
    </style>
</head>
<body>
    <div class='container'>
        <h2>REVISIONES LRM</h2>
        <form action='/procesar-registro' method='post' enctype='multipart/form-data'>
            <label>CLIENTE:</label>
            <select name='cliente' class='form-control'><option>CAPSA</option><option>LEAR</option></select>

            <label>NÚMERO DE REGISTRO / FOLIO:</label>
            <input type='text' name='nombreRegistro' class='form-control' placeholder='Ej. REG-1234' required>

            <label>¿TIENE PACKING LIST?:</label>
            <select name='tienePacking' class='form-control'><option>SÍ</option><option selected>NO</option></select>

            <label>TOMAR O SELECCIONAR FOTOS:</label>
            <input type='file' name='fotos' class='form-control' multiple accept='image/*' required>

            <button type='submit' class='btn-verde'>📸 GUARDAR Y GENERAR PDF</button>
        </form>
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/procesar-registro", methods=["POST"])
def procesar():
    cliente = request.form.get("cliente")
    nombre_reg = request.form.get("nombreRegistro")
    tiene_pk = request.form.get("tienePacking")
    fotos = request.files.getlist("fotos")

    ahora = datetime.now()
    mes_str = ahora.strftime("%B").upper()
    ruta_final = os.path.join(RUTA_BASE, ahora.strftime("%Y"), mes_str, cliente, nombre_reg)
    os.makedirs(ruta_final, exist_ok=True)

    lista_rutas = []
    for i, foto_file in enumerate(fotos):
        img = Image.open(foto_file)
        img = ImageOps.exif_transpose(img)
        img = img.convert('RGB')

        w_porc = (800 / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_porc)))
        img = img.resize((800, h_size), Image.Resampling.LANCZOS)

        ruta_guardado = os.path.join(ruta_final, f"FOTO_{i+1:02}.jpg")
        img.save(ruta_guardado, "JPEG", quality=70, optimize=True)
        lista_rutas.append(ruta_guardado)

    pdf_path = os.path.join(ruta_final, f"SOPORTE_{nombre_reg}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=letter)

    for i, path in enumerate(lista_rutas):
        if i > 0: c.showPage()
        c.setFillColorRGB(0, 0.3, 0.3)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, 770, f"REPORTE DE REVISIÓN - {cliente.upper()}")
        c.setStrokeColorRGB(0, 0.3, 0.3)
        c.setLineWidth(2)
        c.line(50, 760, 550, 760)

        c.setFont("Helvetica", 14)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(50, 735, f"Folio: {nombre_reg} | Packing List: {tiene_pk} | Generado: {ahora.strftime('%H:%M:%S')}")
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.setLineWidth(1)
        c.line(50, 725, 550, 725)

        c.drawImage(path, 100, 150, width=400, height=500, preserveAspectRatio=True, anchor='c')

    c.save()

    try:
        pdf_opt = os.path.join(ruta_final, f"SOPORTE_{nombre_reg}_OPTIMIZADO.pdf")
        comando = [
            "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
            "-dPDFSETTINGS=/ebook", "-dNOPAUSE", "-dQUIET", "-dBATCH",
            f"-sOutputFile={pdf_opt}", pdf_path
        ]
        subprocess.run(comando, check=True)
    except Exception:
        pass

    return "<div style='font-family:sans-serif; text-align:center; margin-top:50px;'><h2>✅ ¡Éxito!</h2><p>Reporte generado con éxito.</p><br><a href='/' style='background:#004d4d; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;'>Volver a registrar</a></div>"

if __name__ == "__main__":
    # Render asigna el puerto automáticamente mediante una variable de entorno
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto)
