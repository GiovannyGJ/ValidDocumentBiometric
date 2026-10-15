# Comparador facial local

Aplicación personal que obtiene el número de identificación del nombre de un archivo JPG/PNG/DOCX, busca su foto en una carpeta local y compara ambos rostros. En DOCX también puede leer el número del texto y revisar las imágenes incrustadas. Todo se ejecuta localmente; no se usa OCR ni API externa, y no se cobra por comparación. Para instalar dependencias y descargar los modelos se necesita conexión a Internet.

## Requisitos

- Python 3.10 o posterior.
- Windows, macOS o Linux.

## Instalación en Windows

Abre PowerShell en esta carpeta y ejecuta:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python download_models.py
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Luego abre <http://127.0.0.1:8000>. La documentación local de la API está en <http://127.0.0.1:8000/api/docs>.

## Fotos de referencia

Guarda una foto JPG, JPEG o PNG por persona en la carpeta `base_datos` situada junto a `server.py`. El nombre del archivo debe ser el DNI español, por ejemplo:

```text
base_datos/
  12345678.jpg
  123456789.png
```

El nombre debe contener los 8 o 9 dígitos del número de identificación; se aceptan separadores como guiones o puntos. No se sube la foto de referencia desde la página.

Se aceptan JPG, PNG y DOCX. El programa toma primero un número de 8 o 9 dígitos del nombre del archivo (por ejemplo, `Jairo guillergua - 44870765.jpg`). Si es DOCX y el nombre no contiene uno, lo busca como texto seleccionable en el Word y compara las imágenes incrustadas. En cualquiera de los casos, números candidatos múltiples generan un error para evitar una selección ambigua. Word antiguo `.doc` no está soportado.

## API

`POST /api/compare-face` recibe `multipart/form-data` con `document_photo` (JPG, PNG o DOCX). Busca el número de 8 o 9 dígitos en el nombre de archivo; para DOCX, si no está allí, busca en el texto. Luego busca la foto por nombre en `base_datos`. Una comparación válida responde `{"match": true}` o `{"match": false}`. Número ausente o ambiguo, foto faltante o rostro no detectable producen un error HTTP; no se convierten silenciosamente en `false`.

La API escucha solo en `127.0.0.1`, por lo que no queda expuesta a la red. Para integrarla con otros programas en el mismo equipo, estos pueden llamar al endpoint local.

## Modelos y umbral

Se usa detección YuNet y reconocimiento SFace de OpenCV Zoo, ejecutados localmente mediante OpenCV. `python download_models.py` descarga los archivos ONNX desde el repositorio público de OpenCV Zoo; después no se requiere conexión para comparar. Revisa los avisos/licencias publicados junto a los modelos antes de redistribuir el programa o los pesos.

El umbral inicial de similitud coseno es `0.363`, el valor de referencia del ejemplo de SFace. No es una garantía universal: la calidad, pose, iluminación y antigüedad de las fotos afectan el resultado. Prueba el umbral con imágenes representativas antes de usarlo para decisiones importantes.

En DOCX se revisan las imágenes incrustadas para localizar la cara del documento. Se toma la mejor coincidencia facial entre los rostros detectados.
