import os
import random
import torch
from PIL import Image, ImageOps, ImageSequence
import numpy as np

class RandomFilePathNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "directory_path": ("STRING", {"default":""}),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "get_random_file_path"
    CATEGORY = "CCTech/Files"

    def get_random_file_path(self, directory_path: str) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"'{directory_path}' is not a valid directory path.")
        
        files = [os.path.join(directory_path, f) for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
        
        if not files:
            raise FileNotFoundError(f"No files found in directory: {directory_path}")

        random_file = random.choice(files)
        return (random_file,)


class RandomImagePathNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "directory_path": ("STRING", {"default":""}),
            },
        }

    RETURN_TYPES = ("IMAGE","STRING")
    FUNCTION = "get_random_image_path"
    CATEGORY = "CCTech/Files"

    def get_random_image_path(self, directory_path) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"'{directory_path}' is not a valid directory path.")

        # Filter only image files
        valid_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")
        files = []
        
        # Walk through the directory tree
        for root, dirs, files_in_dir in os.walk(directory_path):
            for file_name in files_in_dir:
                # Build full path to the file
                full_file_path = os.path.join(root, file_name)
                # Check if the file has a valid extension
                if file_name.lower().endswith(valid_extensions):
                    files.append(full_file_path)

        if not files:
            raise FileNotFoundError(f"No image files found in directory: {directory_path}")


        path = random.choice(files)
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]

        return ( image, path)
        



class GetImageFileByIndexNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "directory_path": ("STRING", {"default":""}),
                "index": ("INT", {"default":0}),
            },
        }

    RETURN_TYPES = ("IMAGE","STRING")
    FUNCTION = "get_image_path_by_index"
    CATEGORY = "CCTech/Files"

    def get_image_path_by_index(self, directory_path, index) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"'{directory_path}' is not a valid directory path.")

        # Filter only image files
        valid_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")
        files = []
        
        # Walk through the directory tree
        for root, dirs, files_in_dir in os.walk(directory_path):
            for file_name in files_in_dir:
                # Build full path to the file
                full_file_path = os.path.join(root, file_name)
                # Check if the file has a valid extension
                if file_name.lower().endswith(valid_extensions):
                    files.append(full_file_path)

        if not files:
            raise FileNotFoundError(f"No image files found in directory: {directory_path}")

        path = files[index]
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]

        return ( image, path)
        

NODE_CLASS_MAPPINGS = {
    "RandomImagePathNode": RandomImagePathNode,
    "RandomFilePathNode": RandomFilePathNode,
    "GetImageFileByIndexNode": GetImageFileByIndexNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomImagePathNode": "🎲 Random Image Path",
    "RandomFilePathNode": "🎲 Random File Path",
    "GetImageFileByIndexNode": "🖼️ Get Image File By Index",
}
