"""
Image Analyzer Plugin
- Takes an image path and a question.
- Uses a multimodal LLM to answer the question about the image.
"""
from pathlib import Path

# Assuming the main GUI application has set up sys.path correctly.
try:
    from core.igris_core import ask_ollama_with_image
except ImportError:
    ask_ollama_with_image = None

def run(image_path: str, question: str) -> str:
    """
    Analyzes an image with a given question using a multimodal LLM.
    """
    if not ask_ollama_with_image:
        return "[ERROR] Core function `ask_ollama_with_image` not available."
    if not Path(image_path).exists():
        return f"[ERROR] Image not found at path: {image_path}"

    try:
        response_data = ask_ollama_with_image(question, image_path)
        analysis = response_data.get("response", "[ERROR] AI returned no analysis.")
        return f"Analysis for '{Path(image_path).name}':\n{analysis}"
    except Exception as e:
        return f"[ERROR] Failed to analyze image: {e}"