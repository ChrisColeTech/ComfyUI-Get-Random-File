import os
import random

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
    CATEGORY = "Utility/Files"

    def get_random_file_path(self, directory_path: str) -> str:
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"'{directory_path}' is not a valid directory path.")
        
        files = [os.path.join(directory_path, f) for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
        
        if not files:
            raise FileNotFoundError(f"No files found in directory: {directory_path}")

        random_file = random.choice(files)
        return (random_file,)

NODE_CLASS_MAPPINGS = {
    "RandomFilePathNode": RandomFilePathNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomFilePathNode": "🎲 Random File Path",
}
