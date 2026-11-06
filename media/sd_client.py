import requests
import base64
import os
import logging
import random
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

# Default A1111 API URL (ensure A1111 is started with --api)
SD_API_URL = "http://127.0.0.1:7860"

class StableDiffusionClient:
    def __init__(self, output_dir="media/outputs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_image(
        self,
        prompt,
        negative_prompt="",
        steps=20,
        width=512,
        height=768,
        filename="output.png",
        timeout=600,
        cfg_scale=7.0,
        sampler_name="Euler a",
        seed=None,
        clip_skip=2,
    ):
        """Calls the local Automatic1111 API to generate an image."""
        url = f"{SD_API_URL}/sdapi/v1/txt2img"
        if seed is None:
            seed = random.randint(1, 2_147_483_647)

        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": steps,
            "width": width,
            "height": height,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
            "seed": seed,
            "override_settings": {"CLIP_stop_at_last_layers": clip_skip},
        }
        logger.info("A1111 seed=%s", seed)
        
        logger.info(f"Sending prompt to A1111 API: {prompt[:50]}...")
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            if "images" in data and len(data["images"]) > 0:
                base64_img = data["images"][0]
                
                # RE-ACTOR DEDICATED API POST-PROCESSING
                reference_img_path = "media/references/master_face.jpg"
                if os.path.exists(reference_img_path):
                    logger.info("Reference face found! Calling ReActor API for face swap...")
                    with open(reference_img_path, "rb") as f:
                        ref_base64 = base64.b64encode(f.read()).decode('utf-8')
                        
                    reactor_payload = {
                        "source_image": ref_base64,
                        "target_image": base64_img,
                        "source_faces_index": [0],
                        "face_faces_index": [0],
                        "upscaler": "None",
                        "scale": 1,
                        "upscale_visibility": 1,
                        "face_restorer": "CodeFormer",
                        "restorer_visibility": 1,
                        "restore_first": 1,
                        "model": "inswapper_128.onnx",
                        "blend_percentage": 100
                    }
                    
                    reactor_response = requests.post(f"{SD_API_URL}/reactor/image", json=reactor_payload, timeout=120)
                    if reactor_response.status_code == 200:
                        reactor_data = reactor_response.json()
                        if "image" in reactor_data:
                            base64_img = reactor_data["image"]
                            logger.info("ReActor face swap successful!")
                    else:
                        logger.error(f"ReActor API failed: {reactor_response.text}")
                
                # Save Final Image
                image_data = base64.b64decode(base64_img)
                image = Image.open(BytesIO(image_data))
                
                output_path = os.path.join(self.output_dir, filename)
                image.save(output_path)
                logger.info(f"Image successfully saved to {output_path}")
                return output_path
            else:
                logger.error("No image returned by API.")
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate image via A1111: {str(e)}")
            return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = StableDiffusionClient(output_dir="outputs")
    # Uncomment to test if A1111 is running:
    # client.generate_image("a beautiful landscape painting, trending on artstation", filename="test_landscape.png")

