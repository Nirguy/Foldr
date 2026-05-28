# Install required libraries
# pip install pillow numpy

import os
import glob
import numpy as np
from PIL import Image, ExifTags

AI_METADATA_KEYWORDS = [
    "stable diffusion",
    "midjourney",
    "dall-e",
    "dalle",
    "sd",
    "ai-generated",
    "generated",
    "photoshop",
    "gimp",
    "adobe",
    "openai",
    "pixray",
    "dreamstudio",
    "nightcafe",
    "image generated",
]
AI_FILENAME_KEYWORDS = [
    "ai",
    "generated",
    "gen",
    "pic",
    "sd",
    "mj",
    "midjourney",
    "dalle",
]

CAMERA_METADATA_KEYS = {
    "make",
    "model",
    "lensmodel",
    "software",
    "exif",
    "date/time",
    "datetime",
}


def extract_metadata(image):
    metadata = {}
    info = image.info or {}
    for key, value in info.items():
        metadata[str(key).lower()] = str(value).lower()

    if hasattr(image, "getexif"):
        try:
            exif = image.getexif()
            if exif:
                for tag_id, tag_value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                    metadata[str(tag_name).lower()] = str(tag_value).lower()
        except Exception:
            pass

    return metadata


def detect_ai_generated_image(image_path):
    """
    Detect if an image is likely AI-generated using metadata and image heuristics.
    """
    try:
        with Image.open(image_path) as image:
            filename = os.path.basename(image_path).lower()
            extension = os.path.splitext(filename)[1]
            metadata = extract_metadata(image)
            metadata_text = " ".join(metadata.values())
            image_np = np.asarray(image.convert("RGB"), dtype=np.float32)

        score = 0.0
        reasons = []

        if any(keyword in metadata_text for keyword in AI_METADATA_KEYWORDS):
            score += 0.6
            reasons.append("AI tool metadata")

        if any(keyword in filename for keyword in AI_FILENAME_KEYWORDS):
            score += 0.3
            reasons.append("filename suggests AI content")

        if extension in {".png", ".webp"}:
            score += 0.3
            reasons.append("non-photographic file format")
            if not any(key in metadata for key in CAMERA_METADATA_KEYS):
                score += 0.2
                reasons.append("missing camera metadata")

        if extension in {".jpg", ".jpeg"} and not any(key in metadata for key in CAMERA_METADATA_KEYS):
            score += 0.1
            reasons.append("missing photo metadata")

        gray = image_np.mean(axis=2)
        gx, gy = np.gradient(gray)
        edge_var = np.var(gx) + np.var(gy)
        color_var = np.var(image_np[:, :, 0]) + np.var(image_np[:, :, 1]) + np.var(image_np[:, :, 2])
        texture_ratio = edge_var / (color_var + 1e-6)

        if texture_ratio < 0.12:
            score += 0.1
            reasons.append("smooth synthetic texture")

        if image_np.shape[0] <= 800 and image_np.shape[1] <= 800:
            score += 0.05
            reasons.append("small image dimensions")

        ai_generated = score >= 0.55
        label = "Likely AI-generated" if ai_generated else "Likely natural"
        return f"{label} (score: {score:.2f}; reasons: {', '.join(reasons) if reasons else 'none'})"

    except Exception as e:
        return f"Error processing: {str(e)}"


if __name__ == "__main__":
    images_folder = os.path.join(os.path.dirname(__file__), "images")
    image_extensions = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.webp"]

    image_paths = []
    for ext in image_extensions:
        image_paths.extend(glob.glob(os.path.join(images_folder, ext)))

    image_paths = sorted(set(image_paths))

    if not image_paths:
        print(f"No images found in {images_folder}")
    else:
        print(f"Found {len(image_paths)} image(s) in {images_folder}\n")
        print("=" * 60)

        ai_generated = []
        natural = []

        for image_path in image_paths:
            filename = os.path.basename(image_path)
            result = detect_ai_generated_image(image_path)
            print(f"{filename}: {result}")
            if "Likely AI-generated" in result:
                ai_generated.append(filename)
            else:
                natural.append(filename)

        print("=" * 60)
        print(f"\nSummary:")
        print(f"AI-generated images ({len(ai_generated)}): {', '.join(ai_generated) if ai_generated else 'None'}")
        print(f"Natural images ({len(natural)}): {', '.join(natural) if natural else 'None'}")
