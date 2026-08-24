import os
import random
import torch
from PIL import Image, ImageOps
import numpy as np
import cv2
import folder_paths
import shutil
import hashlib


class RandomFilePathNode:
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

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filename")
    FUNCTION = "get_random_file_path"
    CATEGORY = "🤖 CCTech/Files"

    def get_random_file_path(self, directory_path: str) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(
                f"'{directory_path}' is not a valid directory path.")

        files = []

        # Walk through the directory tree
        for root, dirs, files_in_dir in os.walk(directory_path):
            for file_name in files_in_dir:
                # Build full path to the file
                full_file_path = os.path.join(root, file_name)
                # Check if the file has a valid extension
                files.append(full_file_path)

        if not files:
            raise FileNotFoundError(
                f"No files found in directory: {directory_path}")

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
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "filename")
    FUNCTION = "get_random_image_path"
    CATEGORY = "🤖 CCTech/Files"

    def get_random_image_path(self, directory_path, unique_id) -> tuple:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(
                f"'{directory_path}' is not a valid directory path.")

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
            raise FileNotFoundError(
                f"No image files found in directory: {directory_path}")

        # Select a random image path
        path = random.choice(files)
        
        # Load the image
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image_np = np.array(image).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_np)[None,]
        
        # Copy image to ComfyUI's temp folder for preview
        temp_dir = folder_paths.get_temp_directory()
        
        # Generate a unique filename based on the original path
        file_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        file_ext = os.path.splitext(path)[1]
        temp_filename = f"preview_{unique_id}_{file_hash}{file_ext}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # Copy the file to temp directory
        shutil.copy2(path, temp_path)
        
        index_text = f"" 
        info_text =  os.path.basename(path)

        # Return results including UI update
        results = {
            "ui": {
                "images": [{
                    "filename": temp_filename,
                    "subfolder": "",
                    "type": "temp"
                }],
                    "text": [index_text, info_text, temp_filename]
            },
            "result": (image_tensor, path)
        }
        
        return results


class GetImageFileByIndexNode:
    def __init__(self):
        self.counters = {}
        self.type = "output"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "reset_bool": ("BOOLEAN", {"default": False}),
                "mode": (["increment", "decrement", "increment_to_stop", "decrement_to_stop"], {"default": "increment"}),
                "start": ("INT", {"default": 0, "min": 0, "max": 18446744073709551615, "step": 1}),
                "stop": ("INT", {"default": 1, "min": 1, "max": 18446744073709551615, "step": 1}),
                "step": ("INT", {"default": 1, "min": 1, "max": 99999, "step": 1}),
                "directory_path": ("STRING", {"default": ""})
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")
    
    RETURN_TYPES = ("IMAGE", "STRING","NUMBER", "INT")
    RETURN_NAMES = ("image", "filename","index", "int")
    FUNCTION = "get_image_path_by_index"
    CATEGORY = "🤖 CCTech/Files"
    OUTPUT_NODE = True

    def get_image_path_by_index(self, directory_path, mode, start, stop, step, unique_id, reset_bool) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(
                f"'{directory_path}' is not a valid directory path.")

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
            raise FileNotFoundError(
                f"No image files found in directory: {directory_path}")

  
        counter = int(start)
        if self.counters.__contains__(unique_id):
            counter = self.counters[unique_id]

        if reset_bool:
            counter = start

        if mode == 'increment':
            counter += step
        elif mode == 'decrement':
            counter -= step
        elif mode == 'increment_to_stop':
            counter = counter + step if counter < stop else counter
        elif mode == 'decrement_to_stop':
            counter = counter - step if counter > stop else counter

        self.counters[unique_id] = counter

        result = int(counter) 

        # Handle wrap-around
        if result >= len(files):
            result = result % len(files)
        elif result < 0:
            result = len(files) + (result % len(files))
            
        path = files[result]
        
        # Load the image
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image_np = np.array(image).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_np)[None,]
        
        # Copy image to ComfyUI's temp folder for preview
        temp_dir = folder_paths.get_temp_directory()
        
        # Generate a unique filename based on the original path
        file_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        file_ext = os.path.splitext(path)[1]
        temp_filename = f"preview_{unique_id}_{file_hash}{file_ext}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # Copy the file to temp directory
        shutil.copy2(path, temp_path)

        index_text = f"Index: {result} / {len(files) - 1}" 
        info_text =  os.path.basename(path)

        # Return results including UI update
        results = {
            "ui": {
                "images": [{
                    "filename": temp_filename,
                    "subfolder": "",
                    "type": "temp"
                }],
                "text": [index_text, info_text, temp_filename]
            },
            "result": (image_tensor, path, float(counter), int(counter))
        }
        
        return results


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
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "filename")

    FUNCTION = "get_random_video_path"
    CATEGORY = "🤖 CCTech/Files"

    def get_random_video_path(self, directory_path, unique_id) -> tuple:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(
                f"'{directory_path}' is not a valid directory path.")

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
            raise FileNotFoundError(
                f"No image files found in directory: {directory_path}")

        # Select a random image path
        path = random.choice(files)
        images = FrameGenerator(path)

        # Get video info and first frame for preview
        video_cap = cv2.VideoCapture(path)
        if not video_cap.isOpened():
            raise ValueError(f"Could not open video file: {path}")
            
        # Get video properties
        fps = video_cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        
        # Read first frame for preview
        ret, first_frame = video_cap.read()
        video_cap.release()
        
        if ret:
            # Convert first frame for preview
            first_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
            preview_image = Image.fromarray(first_frame)
            
            # Save preview to temp folder
            temp_dir = folder_paths.get_temp_directory()
            file_hash = hashlib.md5(path.encode()).hexdigest()[:8]
            temp_filename = f"video_preview_{unique_id}_{file_hash}.png"
            temp_path = os.path.join(temp_dir, temp_filename)
            preview_image.save(temp_path)
        else:
            temp_filename = None
        
        # Load all frames using FrameGenerator
        images = FrameGenerator(path)
        
        # Return results including UI update
        duration_str = f"{duration:.2f}s" if duration else "0s"
        index_text = os.path.basename(path)
        video_info_text = f"{width}x{height} • {frame_count} frames • {fps:.2f} fps • {duration_str}"
        
    
        results = {
            "ui": {
                "images": [{
                    "filename": temp_filename,
                    "subfolder": "",
                    "type": "temp"
                }] if temp_filename else [],
                "text": [index_text, video_info_text, temp_filename]
            },
            "result": (images, path)
        }
        
        return results



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
        self.counters = {}
        self.type = "output"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "reset_bool": ("BOOLEAN", {"default": False}),
                "mode": (["increment", "decrement", "increment_to_stop", "decrement_to_stop"], {"default": "increment"}),
                "start": ("INT", {"default": 0, "min": 0, "max": 18446744073709551615, "step": 1}),
                "stop": ("INT", {"default": 1, "min": 1, "max": 18446744073709551615, "step": 1}),
                "step": ("INT", {"default": 1, "min": 1, "max": 99999, "step": 1}),
                "directory_path": ("STRING", {"default": ""})
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            }
        }
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")
    
    RETURN_TYPES = ("IMAGE", "STRING","NUMBER", "INT")
    RETURN_NAMES = ("images", "filename","index", "int")
    FUNCTION = "get_video_path_by_index"
    CATEGORY = "🤖 CCTech/Files"
    OUTPUT_NODE = True

    def get_video_path_by_index(self, directory_path, mode, start, stop, step, unique_id, reset_bool) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(
                f"'{directory_path}' is not a valid directory path.")

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
            raise FileNotFoundError(
                f"No video files found in directory: {directory_path}")
        
        counter = int(start) 
        if self.counters.__contains__(unique_id):
            counter = self.counters[unique_id]

        if reset_bool:
            counter = start

        if mode == 'increment':
            counter += step
        elif mode == 'decrement':
            counter -= step
        elif mode == 'increment_to_stop':
            counter = counter + step if counter < stop else counter
        elif mode == 'decrement_to_stop':
            counter = counter - step if counter > stop else counter

        self.counters[unique_id] = counter

        result = int(counter)
        
        # Handle wrap-around
        if result >= len(files):
            result = result % len(files)
        elif result < 0:
            result = len(files) + (result % len(files))

        path = files[result]
        
        # Get video info and first frame for preview
        video_cap = cv2.VideoCapture(path)
        if not video_cap.isOpened():
            raise ValueError(f"Could not open video file: {path}")
            
        # Get video properties
        fps = video_cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        
        # Read first frame for preview
        ret, first_frame = video_cap.read()
        video_cap.release()
        
        if ret:
            # Convert first frame for preview
            first_frame = cv2.cvtColor(first_frame, cv2.COLOR_BGR2RGB)
            preview_image = Image.fromarray(first_frame)
            
            # Save preview to temp folder
            temp_dir = folder_paths.get_temp_directory()
            file_hash = hashlib.md5(path.encode()).hexdigest()[:8]
            temp_filename = f"video_preview_{unique_id}_{file_hash}.png"
            temp_path = os.path.join(temp_dir, temp_filename)
            preview_image.save(temp_path)
        else:
            temp_filename = None
        
        # Load all frames using FrameGenerator
        images = FrameGenerator(path)
        
        # Return results including UI update
        duration_str = f"{duration:.2f}s" if duration else "0s"
        video_info_text = f"{width}x{height} • {frame_count} frames • {fps:.2f} fps • {duration_str}"
        index_text = f"{os.path.basename(path)} \n\n Index: {result} / {len(files) - 1}"
        
        results = {
            "ui": {
                "images": [{
                    "filename": temp_filename,
                    "subfolder": "",
                    "type": "temp"
                }] if temp_filename else [],
                "text": [index_text, video_info_text, temp_filename]
            },
            "result": (images, path, float(counter), int(counter))
        }
        
        return results

NODE_CLASS_MAPPINGS = {
    "Random Video Path": RandomVideoPathNode,
    "Random Image Path": RandomImagePathNode,
    "Random File Path": RandomFilePathNode,
    "Get Image File By Index": GetImageFileByIndexNode,
    "Get Video File By Index": GetVideoFileByIndexNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Random Video Path": "Random Video Path 🎲",
    "Random Image Path": "Random Image Path 🎲",
    "Random File Path": "Random File Path 🎲",
    "Get Image File By Index": "Get Image File By Index 🖼️",
    "Get Video File By Index": "Get Video File By Index ▶️",
}
