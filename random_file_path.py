import os
import random
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps
from torchvision import models, transforms
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

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    RETURN_TYPES = ("STRING",)
    FUNCTION = "get_random_file_path"
    CATEGORY = "Utility/Files"

    def get_random_file_path(self, directory_path: str) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"'{directory_path}' is not a valid directory path.")
        
        files = []
        
        # Walk through the directory tree
        for root, dirs, files_in_dir in os.walk(directory_path):
            for file_name in files_in_dir:
                # Build full path to the file
                full_file_path = os.path.join(root, file_name)
                # Check if the file has a valid extension
                files.append(full_file_path)

        if not files:
            raise FileNotFoundError(f"No files found in directory: {directory_path}")

        path = random.choice(files)
        return (path,)

class RandomImagePathNode:
    def __init__(self):
        # Load a pre-trained ResNet model
        self.model = models.resnet50(pretrained=True)
        self.model.eval()  # Set the model to evaluation mode

        # Define the image transformation
        self.preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "directory_path": ("STRING", {"default": ""}),
            },
        }
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    RETURN_TYPES = ("IMAGE", "STRING")
    FUNCTION = "get_random_image_path"
    CATEGORY = "Utility/Files"



    def get_random_image_path(self, directory_path) -> tuple:
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

        # Select a random image path
        path = random.choice(files)
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
       
        latents = image.permute(0, 3, 1, 2)
        latents = F.interpolate(latents, size=((image.shape[1] // 8), (image.shape[2] // 8)))
        

        return (image, path)
        



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
    CATEGORY = "Utility/Files"

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
