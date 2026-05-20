"""
Baixa o modelo Real-ESRGAN x4plus (~66MB) do HuggingFace.
Execute: python models/download_model.py
"""
import os
import sys
import urllib.request

MODEL_URL = "https://huggingface.co/Meeperomi/RealESRGAN_x4-onnx/resolve/main/RealESRGAN_x4.onnx"
MODEL_PATH = os.path.join(os.path.dirname(__file__), "realesrgan-x4plus.onnx")


def download():
    if os.path.isfile(MODEL_PATH):
        size_mb = os.path.getsize(MODEL_PATH) / 1024 / 1024
        print(f"Modelo já existe: {MODEL_PATH} ({size_mb:.0f}MB)")
        return

    print(f"Baixando Real-ESRGAN x4plus (~66MB)...")
    print(f"  De: {MODEL_URL}")
    print(f"  Para: {MODEL_PATH}")

    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        pct = min(100, downloaded * 100 / total_size) if total_size > 0 else 0
        mb = downloaded / 1024 / 1024
        sys.stdout.write(f"\r  {pct:.0f}% ({mb:.1f}MB)")
        sys.stdout.flush()

    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, reporthook=progress)
    print(f"\n  Pronto! ({os.path.getsize(MODEL_PATH) / 1024 / 1024:.0f}MB)")


if __name__ == "__main__":
    download()
