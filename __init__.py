from .random_file_path import *

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


__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']