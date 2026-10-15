"""Download the OpenCV Zoo ONNX models used by the local face matcher."""
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "models"
MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/refs/heads/main/"
        "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    ),
    "face_recognition_sface_2021dec.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/refs/heads/main/"
        "models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
    ),
}


def main() -> None:
    MODEL_DIR.mkdir(exist_ok=True)
    for filename, url in MODELS.items():
        destination = MODEL_DIR / filename
        if destination.exists() and destination.stat().st_size:
            print(f"Ya existe: {destination}")
            continue
        print(f"Descargando {filename}...")
        urlretrieve(url, destination)
        print(f"Guardado: {destination}")
    print("Modelos listos. La comparación se ejecuta localmente.")


if __name__ == "__main__":
    main()
