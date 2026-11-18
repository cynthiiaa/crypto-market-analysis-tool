import subprocess
import modal

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.8.0-devel-ubuntu22.04", add_python="3.12")
         .pip_install("vllm>=0.12.0", "huggingface_hub[hf_transfer]==0.35.0")
         .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("chatbot-for-crypto-market-anaysis-platform")

MODEL_NAME = "kaitchup/Olmo-3.1-32B-Instruct-awq-w4a16-asym"
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)

@app.function(image=vllm_image, gpu="A100-40GB", timeout=600, scaledown_window=300, volumes={"/root/.cache/huggingface": hf_cache_vol}, secrets=[modal.Secret.from_name("huggingface-secret")])
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