"""
Image Generation Tool for ARIA
Uses Google's Gemini 3 Pro Image (Nano Banana Pro) for image generation.
"""
import os
import base64
from io import BytesIO

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyC6Af7kdCVMkPA09MruQ_s5sn067oWOB_s")
MODEL = "gemini-3-pro-image-preview"
OUTPUT_DIR = os.path.expanduser("~/Pictures/aria_generated")


def generate_image(prompt: str, filename: str = None, resolution: str = "1K") -> dict:
    """
    Generate an image from a text prompt using Gemini's native image generation.

    Args:
        prompt: Description of the image to generate
        filename: Output filename (auto-generated if not provided)
        resolution: Output resolution - 1K, 2K, or 4K

    Returns:
        dict with success, path, and message
    """
    try:
        from google import genai
        from google.genai import types
        from PIL import Image as PILImage
    except ImportError:
        return {
            "success": False,
            "error": "Missing dependencies. Run: pip install google-genai pillow"
        }

    if not GEMINI_API_KEY:
        return {
            "success": False,
            "error": "GEMINI_API_KEY not set. Please set it in environment."
        }

    # Auto-generate filename if not provided
    if not filename:
        import re
        import time
        # Create clean filename from prompt
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', prompt)[:40].strip().replace(' ', '_').lower()
        filename = f"{clean}_{int(time.time())}.png"

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, filename)

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    image_size=resolution
                )
            )
        )

        # Process response
        image_saved = False
        model_text = ""

        for part in response.parts:
            if part.text is not None:
                model_text = part.text
            elif part.inline_data is not None:
                image_data = part.inline_data.data
                if isinstance(image_data, str):
                    image_data = base64.b64decode(image_data)

                image = PILImage.open(BytesIO(image_data))

                # Ensure RGB mode for PNG
                if image.mode == 'RGBA':
                    rgb_image = PILImage.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[3])
                    rgb_image.save(output_path, 'PNG')
                elif image.mode == 'RGB':
                    image.save(output_path, 'PNG')
                else:
                    image.convert('RGB').save(output_path, 'PNG')
                image_saved = True

        if image_saved:
            return {
                "success": True,
                "path": output_path,
                "message": f"Image generated: {output_path}",
                "model_response": model_text
            }
        else:
            return {
                "success": False,
                "error": f"No image generated. Model said: {model_text}" if model_text else "No image in response"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Generation failed: {e}"
        }


if __name__ == "__main__":
    import sys
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "A futuristic AI robot named ARIA"
    print(f"Generating: {prompt}")
    result = generate_image(prompt)
    if result["success"]:
        print(f"✅ {result['message']}")
    else:
        print(f"❌ {result['error']}")
