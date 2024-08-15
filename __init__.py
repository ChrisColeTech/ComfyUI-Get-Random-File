from .random_file_path import *


NODE_CLASS_MAPPINGS = {
    "RandomImagePathNode": RandomImagePathNode,
    "RandomFilePathNode": RandomFilePathNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RandomImagePathNode": "🎲 Random Image Path",
    "RandomFilePathNode": "🎲 Random File Path",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']