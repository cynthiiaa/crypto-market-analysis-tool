import subprocess
import modal

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.8.0-devel-ubuntu22.04", add_python="3.12")
         .pip_install("vllm==0.10.2", "huggingface_hub[hf_transfer]==0.35.0")
         .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("crypto-market-news-signal")

MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True) # better to cache the 16GB model weights instead of redownloading them all the time

@app.function(image=vllm_image, gpu="A10G", timeout=600, scaledown_window=300, volumes={"/root/.cache/huggingface": hf_cache_vol}, secrets=[modal.Secret.from_name("huggingface-secret")])
@modal.web_server(port=8000, startup_timeout=600)
def serve():
    cmd = [
        "vllm", "serve", MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", "8000",
        "--gpu-memory-utilization", "0.90",
        "--max-model-len", "4096"
    ]
    subprocess.Popen(cmd)