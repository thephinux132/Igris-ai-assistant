"""
A plugin to analyze a user-selected image file using a multimodal LLM.
This plugin contains the core logic for analysis, but does not create UI.
The UI (file/question dialogs) is handled by the main GUI application.
"""
import sys
from pathlib import Path

# Need to add core to path to import igris_core
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "core"))

try:
    from igris_core import ask_ollama_with_image
except ImportError:
    # This will be printed in the GUI's console if the import fails
    print("[ERROR] image_analyzer: Could not import ask_ollama_with_image from igris_core.")
    ask_ollama_with_image = None

def run(image_path: str, question: str):
    """
    Main function for the plugin.
    - Takes an image path and a question.
    - Call the multimodal LLM and return the result.
    """
    if not ask_ollama_with_image:
        return "[ERROR] Core vision function is not available."

    if not image_path or not Path(image_path).is_file():
        return f"[ERROR] Invalid image path provided: {image_path}"

    if not question:
        return "[INFO] No question asked. Analysis cancelled."

    print(f"Analyzing {image_path} with prompt: '{question}'...")
    
    # Call the core function
    response_data = ask_ollama_with_image(question, image_path)

    if "error" in response_data:
        return f"[ERROR] AI analysis failed: {response_data.get('details', response_data['error'])}"
    
    return response_data.get("response", "AI returned no analysis.")

if __name__ == '__main__':
    # For direct testing, pass a file path as an argument
    # This part is not used by the GUI but is useful for command-line testing.
    if len(sys.argv) > 2:
        result = run(sys.argv[1], sys.argv[2])
        print("\n--- Analysis Result ---")
        print(result)
    else:
        print("Usage: python image_analyzer.py <path_to_image> \"<question>\"")