import os
import random
import torch
from PIL import Image, ImageOps
import numpy as np
import cv2

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
        pass

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
    
video_extensions = ('webm', 'mp4', 'mkv', 'gif')
        
class RandomVideoPathNode:
    def __init__(self):
        pass

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
    RETURN_NAMES = ("images", "STRING")

    FUNCTION = "get_random_video_path"
    CATEGORY = "Utility/Files"



    def get_random_video_path(self, directory_path) -> tuple:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"'{directory_path}' is not a valid directory path.")

        # Filter only video files
        
      
        files = []

        # Walk through the directory tree
        for root, dirs, files_in_dir in os.walk(directory_path):
            for file_name in files_in_dir:
                # Build full path to the file
                full_file_path = os.path.join(root, file_name)
                # Check if the file has a valid extension
                if file_name.lower().endswith(video_extensions):
                    files.append(full_file_path)

        if not files:
            raise FileNotFoundError(f"No image files found in directory: {directory_path}")

        # Select a random image path
        path = random.choice(files)
        images = FrameGenerator(path)
      
        return (images, path)
    
def get_video_frames(video_path):
    video_cap = cv2.VideoCapture(video_path)
    
    if not video_cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
    
    frames = []
    while True:
        ret, frame = video_cap.read()
        if not ret:
            break
        frames.append(frame)
    
    video_cap.release()
    return frames

class FrameGenerator:
    def __init__(self, video_path):
        self.video_path = video_path
        self.frames = self._load_frames()

    def _load_frames(self):
        video_cap = cv2.VideoCapture(self.video_path)
        if not video_cap.isOpened():
            raise ValueError(f"Could not open video file: {self.video_path}")
        
        frames = []
        while True:
            ret, frame = video_cap.read()
            if not ret:
                break
            
            # Convert frame from BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Convert frame to a torch tensor and normalize it
            frame_tensor = torch.from_numpy(frame).float() / 255.0

            frames.append(frame_tensor)
        
        video_cap.release()
        return frames

    def __len__(self):
        return len(self.frames)

    def __getitem__(self, index):
        return self.frames[index]

    def __iter__(self):
        return iter(self.frames)

class GetVideoFileByIndexNode:
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

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "STRING")
    FUNCTION = "get_video_path_by_index"
    CATEGORY = "Utility/Files"

    def get_video_path_by_index(self, directory_path, index) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"'{directory_path}' is not a valid directory path.")

        # Filter only image files
        files = []
        
        # Walk through the directory tree
        for root, dirs, files_in_dir in os.walk(directory_path):
            for file_name in files_in_dir:
                # Build full path to the file
                full_file_path = os.path.join(root, file_name)
                # Check if the file has a valid extension
                if file_name.lower().endswith(video_extensions):
                    files.append(full_file_path)

        if not files:
            raise FileNotFoundError(f"No video files found in directory: {directory_path}")

        path = files[index]
        images = FrameGenerator(path)

        return ( images, path)
        


NODE_CLASS_MAPPINGS = {
    "RandomVideoPathNode": RandomVideoPathNode,
    "RandomImagePathNode": RandomImagePathNode,
    "RandomFilePathNode": RandomFilePathNode,
    "GetImageFileByIndexNode": GetImageFileByIndexNode,
    "GetVideoFileByIndexNode": GetVideoFileByIndexNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomVideoPathNode": "🎲 Random Video Path",
    "RandomImagePathNode": "🎲 Random Image Path",
    "RandomFilePathNode": "🎲 Random File Path",
    "GetImageFileByIndexNode": "🖼️ Get Image File By Index",
    "GetVideoFileByIndexNode": "▶️ Get Video File By Index",
}
