import os
import datetime
from flask import Flask, request, render_template_string
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# Configuración de Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.file']
PARENT_FOLDER_ID = "1AfWS3WlT5j68O5nJ3LD5wrHTp1Qx_fhu"

def get_drive_service():
    # Render guarda el archivo secreto en la raíz o en /etc/secrets/creds.json si se configuró así.
    # Primero buscamos en la raíz donde lo nombramos.
    creds_path = 'creds.json'
    if not os.path.exists(creds_path):
        creds_path = '/etc/secrets/creds.json' # Ruta alternativa por si Render lo movió a secrets
        
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_path, file_name):
    try:
        service = get_drive_service()
        file_metadata = {
            'name': file_name,
            'parents': [PARENT_FOLDER_ID]
        }
        media = MediaFileUpload(file_path, mimetype='application/pdf')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        print(f"Error al subir a Drive: {e}")
        return None

HTML_FORM = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>REVISIONES LRM</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h2 { text-align: center; color: #007bff; }
        label { font-weight: bold; display: block; margin-top: 15px; }
        input, select { width: 100%; padding: 10px; margin-top: 5px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; }
        input[type="submit"] { background-color: #28a745; color: white; border: none; margin-top: 20px; font-size: 16px; cursor: pointer; }
        input[type="submit"]:hover { background-color: #218838; }
    </style>
</head>
<body>
    <div class="container">
        <h2>REVISIONES LRM</h2>
        <form action="/generar" method="post" enctype="multipart/form-data">
            <label>Número de Registro / Folio:</label>
            <input type="text" name="nombre_reg" required placeholder="Ej. LRM-1234">

            <label>Tipo de Operación:</label>
            <select name="tiene_pk">
                <option value="CAPSA">CAPSA</option>
                <option value="LEAR">LEAR</option>
                <option value="OTRO">OTRO</option>
            </select>

            <label>Selecciona las Fotos:</label>
            <input type="file" name="fotos" accept="image/*" multiple required>

            <input type="submit" value="Generar y Guardar Reporte">
        </form>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_FORM)

@app.route('/generar', method=['POST'])
def generar():
    nombre_reg = request.form.get('nombre_reg')
    tiene_pk = request.form.get('tiene_pk')
    archivos_fotos = request.files.getlist('fotos')

    ahora = datetime.datetime.now()
    pdf_name = f"REPORTELRM_{nombre_reg}_{ahora.strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join("/tmp", pdf_name) if os.path.exists("/tmp") else pdf_name

    c = canvas.Canvas(pdf_path, pagesize=letter)
    
    # Encabezado del PDF
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, f"REVISIÓN LRM - Registro: {nombre_reg}")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, f"Tipo: {tiene_pk} | Fecha: {ahora.strftime('%d/%m/%Y %H:%M:%S')}")
    c.setLineWidth(1)
    c.line(50, 725, 560, 725)

    y_position = 450
    for idx, f in enumerate(archivos_fotos):
        if f.filename == '': continue
        
        # Guardar imagen temporal para procesar con Pillow
        img_temp_path = f"temp_{idx}_{f.filename}"
        f.save(img_temp_path)
        
        try:
            # Optimizar y comprimir la imagen para que el PDF no pese demasiado
            img = Image.open(img_temp_path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            img.thumbnail((450, 250))
            optimized_img_path = f"opt_{idx}.jpg"
            img.save(optimized_img_path, "JPEG", quality=70)

            # Dibujar la foto en el PDF
            c.drawImage(optimized_img_path, 80, y_position, width=400, height=250, preserveAspectRatio=True)
            
            # Limpieza de imágenes optimizadas
            if os.path.exists(optimized_img_path): os.remove(optimized_img_path)
        except Exception as e:
            print(f"Error procesando imagen {f.filename}: {e}")

        if os.path.exists(img_temp_path): os.remove(img_temp_path)
        
        # Controlar saltos de página (1 foto por página para orden visual limpio)
        c.showPage()
        # En las siguientes páginas, resetear la posición inicial de dibujo
        y_position = 450

    c.save()

    # Subir el PDF final directamente a Google Drive usando la API
    drive_id = upload_to_drive(pdf_path, pdf_name)

    # Limpiar el PDF local
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    if drive_id:
        return f'<div style="font-family:sans-serif; text-align:center; margin-top:50px;"><h2>¡Éxito!</h2><p>Reporte enviado directamente a tu Google Drive.</p><a href="/">Volver a generar</a></div>'
    else:
        return f'<div style="font-family:sans-serif; text-align:center; margin-top:50px; color:red;"><h2>Error</h2><p>El PDF se creó pero no se pudo subir a Drive. Verifica los permisos del correo de servicio.</p><a href="/">Reintentar</a></div>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
