from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
DATABASE_DIR = ROOT / "base_datos"
DETECTOR_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_PATH = MODEL_DIR / "face_recognition_sface_2021dec.onnx"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_PROFILE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
# OpenCV SFace cosine threshold from its model example; calibrate for your images.
COSINE_THRESHOLD = 0.363

app = FastAPI(title="Comparador facial local", docs_url="/api/docs")


def _models():
    missing = [p.name for p in (DETECTOR_PATH, RECOGNIZER_PATH) if not p.is_file()]
    if missing:
        raise HTTPException(503, f"Faltan modelos. Ejecuta: python download_models.py ({', '.join(missing)})")
    return (
        cv2.FaceDetectorYN_create(str(DETECTOR_PATH), "", (320, 320), 0.8, 0.3, 5000),
        cv2.FaceRecognizerSF_create(str(RECOGNIZER_PATH), ""),
    )


def _decode_image(data: bytes) -> np.ndarray | None:
    if not data:
        return None
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)


def _docx_contents(data: bytes) -> tuple[list[bytes], str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as document:
            images = [
                document.read(name)
                for name in document.namelist()
                if name.startswith("word/media/") and not name.endswith("/")
            ]
            xml = document.read("word/document.xml")
            root = ET.fromstring(xml)
            namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            text = "".join(node.text or "" for node in root.iter(f"{namespace}t"))
            return images, text
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        raise HTTPException(400, "El archivo DOCX no es válido.")


def _features(image: np.ndarray, detector, recognizer) -> list[np.ndarray]:
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    if faces is None:
        return []
    return [recognizer.feature(recognizer.alignCrop(image, face)) for face in faces]


def _extract_id_number(document_text: str) -> str:
    """Find exactly one 8- or 9-digit ID written as text in the DOCX."""
    candidates = set(re.findall(r"(?<!\d)\d{8,9}(?!\d)", document_text))
    if not candidates:
        raise HTTPException(422, "El Word debe incluir el número de identificación de 8 o 9 dígitos como texto.")
    if len(candidates) > 1:
        raise HTTPException(422, "El Word contiene varios números de 8 o 9 dígitos; no se puede elegir el DNI automáticamente.")
    return candidates.pop()


def _id_from_filename(filename: str) -> str:
    """Extract a single 8- or 9-digit ID from the uploaded DOCX filename."""
    stem = Path(filename).stem
    candidates = set(re.findall(r"(?<!\d)\d{8,9}(?!\d)", stem))
    if len(candidates) > 1:
        raise HTTPException(422, "El nombre del archivo contiene varios números de identificación posibles.")
    return candidates.pop() if candidates else ""


def _find_profile(dni: str) -> Path | None:
    if not DATABASE_DIR.is_dir():
        return None
    for path in DATABASE_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in ALLOWED_PROFILE_EXTENSIONS:
            filename_dni = re.sub(r"[^A-Z0-9]", "", path.stem.upper())
            if filename_dni == dni:
                return path
    return None


async def _read_upload(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Cada archivo debe pesar menos de 15 MB.")
    return data


@app.get("/")
def home():
    return FileResponse(ROOT / "index.html")


@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "models_ready": DETECTOR_PATH.is_file() and RECOGNIZER_PATH.is_file(),
        "database_ready": DATABASE_DIR.is_dir(),
    }


@app.post("/api/compare-face")
async def compare_face(
    document_photo: UploadFile = File(...),
):
    doc_data = await _read_upload(document_photo)
    filename = document_photo.filename or ""
    extension = Path(filename).suffix.lower()
    document_text = ""
    if extension == ".docx":
        image_data, document_text = _docx_contents(doc_data)
    elif extension in ALLOWED_PROFILE_EXTENSIONS:
        image_data = [doc_data]
    else:
        raise HTTPException(415, "Sube un archivo DOCX, JPG, JPEG o PNG.")

    document_images = [_decode_image(item) for item in image_data]
    document_images = [image for image in document_images if image is not None]
    if not document_images:
        raise HTTPException(400, "No se pudo leer una imagen del documento.")

    dni = _id_from_filename(filename)
    if not dni:
        if extension != ".docx":
            raise HTTPException(422, "El nombre de la imagen debe incluir el número de identificación de 8 o 9 dígitos.")
        dni = _extract_id_number(document_text)
    profile_path = _find_profile(dni)
    if profile_path is None:
        raise HTTPException(404, f"No hay una foto para el DNI {dni} en la carpeta base_datos.")
    profile_image = _decode_image(profile_path.read_bytes())
    if profile_image is None:
        raise HTTPException(400, f"La foto asociada al DNI {dni} no se pudo leer.")

    detector, recognizer = _models()
    profile_features = _features(profile_image, detector, recognizer)
    if not profile_features:
        raise HTTPException(422, "No se detectó un rostro en la foto de perfil.")
    document_features = [
        feature
        for image in document_images
        for feature in _features(image, detector, recognizer)
    ]
    if not document_features:
        raise HTTPException(422, "No se detectó un rostro en la foto del documento.")

    best_score = max(
        float(recognizer.match(left, right, cv2.FaceRecognizerSF_FR_COSINE))
        for left in document_features
        for right in profile_features
    )
    return {"match": best_score >= COSINE_THRESHOLD}
