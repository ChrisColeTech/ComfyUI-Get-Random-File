import os
import random
import torch
from PIL import Image, ImageOps
import numpy as np
import folder_paths

import hashlib

from comfy_api.input_impl import VideoFromFile


video_extensions = ('webm', 'mp4', 'mkv', 'gif')
image_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")


def _walk_files(directory_path, extensions=None):
    if not os.path.isdir(directory_path):
        raise NotADirectoryError(
            f"'{directory_path}' is not a valid directory path.")
    files = []
    for root, dirs, files_in_dir in os.walk(directory_path):
        for file_name in files_in_dir:
            if extensions is None or file_name.lower().endswith(extensions):
                files.append(os.path.join(root, file_name))
    if not files:
        kind = "files" if extensions is None else f"{extensions[0].lstrip('.')}-type files"
        raise FileNotFoundError(
            f"No {kind} found in directory: {directory_path}")
    return files


def _load_image_outputs(path):
    """(IMAGE [1,H,W,C], MASK [1,H,W]) from a file - core LoadImage's
    conventions: EXIF transpose, RGB float 0..1, mask from the alpha channel
    (1-alpha) when present, else a zero 64x64 placeholder mask."""
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    if "A" in image.getbands():
        alpha = np.array(image.getchannel("A")).astype(np.float32) / 255.0
        mask = 1.0 - torch.from_numpy(alpha)
        mask = mask[None,]
    else:
        mask = torch.zeros((1, 64, 64), dtype=torch.float32)
    image = image.convert("RGB")
    image_np = np.array(image).astype(np.float32) / 255.0
    return torch.from_numpy(image_np)[None,], mask


def _load_video_outputs(path):
    """(VIDEO, IMAGE [T,H,W,C], AUDIO, fps, frame_count) via comfy-core's own
    VideoFromFile - the SAME object core LoadVideo outputs, so everything
    downstream of a LoadVideo works identically downstream of these nodes.
    The old homemade cv2 FrameGenerator (a python list of per-frame tensors,
    not a valid IMAGE batch, with no audio and no timing) is gone."""
    video = VideoFromFile(path)
    components = video.get_components()
    images = components.images
    audio = components.audio  # None when the file has no audio track
    fps = float(components.frame_rate)
    frame_count = int(images.shape[0])
    return video, images, audio, fps, frame_count


# ── Preview serving ─────────────────────────────────────────────────────────
# The picked file is streamed to the node's single DOM preview widget (a real
# playable <video> for videos, an <img> for images - the VHS pattern) through
# this pack's own /cctech_random_file/view endpoint. Only files a node
# actually picked are servable: each pick registers the path under a random
# token, and the endpoint refuses anything else - it can never be used to
# read arbitrary paths. No temp-file copies, and nothing is sent as
# ui.images (that made comfy draw a second copy of the preview on the node
# canvas on top of the DOM widget - the reported duplication).

_PREVIEW_REGISTRY = {}
_PREVIEW_REGISTRY_LIMIT = 256


def _register_preview(path):
    token = hashlib.sha256(os.urandom(16) + path.encode()).hexdigest()[:24]
    _PREVIEW_REGISTRY[token] = path
    while len(_PREVIEW_REGISTRY) > _PREVIEW_REGISTRY_LIMIT:
        _PREVIEW_REGISTRY.pop(next(iter(_PREVIEW_REGISTRY)))
    return token


def register_preview_route():
    """Mount /cctech_random_file/view on comfy's server (called from
    __init__.py; a no-op outside a running ComfyUI)."""
    try:
        import server
        from aiohttp import web
    except Exception:
        return

    @server.PromptServer.instance.routes.get("/cctech_random_file/view")
    async def _view_random_file(request):
        token = request.query.get("token", "")
        path = _PREVIEW_REGISTRY.get(token)
        if path is None or not os.path.isfile(path):
            return web.Response(status=404)
        # FileResponse handles Range requests, so <video> seeking works.
        return web.FileResponse(path)


class RandomFilePathNode:
    SEARCH_ALIASES = ['random file', 'pick random file', 'file path']

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
    RETURN_NAMES = ("filename",)
    FUNCTION = "get_random_file_path"
    CATEGORY = "🤖 CCTech/Files"

    def get_random_file_path(self, directory_path: str):
        files = _walk_files(directory_path)
        return (random.choice(files),)


class RandomImagePathNode:
    SEARCH_ALIASES = ['random image', 'pick random image', 'load random image']

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

    # image/filename keep their original slots so existing workflows keep
    # working; mask is appended (core LoadImage parity).
    RETURN_TYPES = ("IMAGE", "STRING", "MASK")
    RETURN_NAMES = ("image", "filename", "mask")
    FUNCTION = "get_random_image_path"
    CATEGORY = "🤖 CCTech/Files"

    def get_random_image_path(self, directory_path, unique_id):
        files = _walk_files(directory_path, image_extensions)
        path = random.choice(files)
        image_tensor, mask = _load_image_outputs(path)
        token = _register_preview(path)
        h, w = image_tensor.shape[1], image_tensor.shape[2]
        return {
            "ui": {
                "text": ["image", token, os.path.basename(path), f"{w}x{h}"],
            },
            "result": (image_tensor, path, mask),
        }


class GetImageFileByIndexNode:
    SEARCH_ALIASES = ['image by index', 'indexed image', 'load image sequence', 'image counter']

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

    RETURN_TYPES = ("IMAGE", "STRING", "NUMBER", "INT", "MASK")
    RETURN_NAMES = ("image", "filename", "index", "int", "mask")
    FUNCTION = "get_image_path_by_index"
    CATEGORY = "🤖 CCTech/Files"
    OUTPUT_NODE = True

    def _advance(self, unique_id, mode, start, stop, step, reset_bool, n_files):
        counter = self.counters.get(unique_id, int(start))
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
        result = int(counter) % n_files
        return counter, result

    def get_image_path_by_index(self, directory_path, mode, start, stop, step, unique_id, reset_bool):
        files = _walk_files(directory_path, image_extensions)
        counter, result = self._advance(unique_id, mode, start, stop, step, reset_bool, len(files))
        path = files[result]
        image_tensor, mask = _load_image_outputs(path)
        token = _register_preview(path)
        h, w = image_tensor.shape[1], image_tensor.shape[2]
        info = f"{w}x{h} | Index: {result} / {len(files) - 1}"
        return {
            "ui": {
                "text": ["image", token, os.path.basename(path), info],
            },
            "result": (image_tensor, path, float(counter), int(counter), mask),
        }


class RandomVideoPathNode:
    SEARCH_ALIASES = ['random video', 'pick random video', 'load random video']

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

    # images/filename keep their original slots so existing workflows keep
    # working; the REAL outputs are appended: the same VIDEO object core
    # LoadVideo emits (wire it anywhere a LoadVideo output goes), the audio
    # track, fps, and frame count.
    RETURN_TYPES = ("IMAGE", "STRING", "VIDEO", "AUDIO", "FLOAT", "INT")
    RETURN_NAMES = ("images", "filename", "video", "audio", "fps", "frame_count")
    FUNCTION = "get_random_video_path"
    CATEGORY = "🤖 CCTech/Files"

    def get_random_video_path(self, directory_path, unique_id):
        files = _walk_files(directory_path, video_extensions)
        path = random.choice(files)
        video, images, audio, fps, frame_count = _load_video_outputs(path)
        token = _register_preview(path)

        duration = frame_count / fps if fps > 0 else 0
        h, w = images.shape[1], images.shape[2]
        video_info_text = (f"{w}x{h} • {frame_count} frames • {fps:.2f} fps • "
                           f"{duration:.2f}s" + ("" if audio is not None else " • no audio"))
        return {
            "ui": {
                "text": ["video", token, os.path.basename(path), video_info_text],
            },
            "result": (images, path, video, audio, fps, frame_count),
        }


class GetVideoFileByIndexNode:
    SEARCH_ALIASES = ['video by index', 'indexed video', 'load video sequence', 'video counter']

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

    RETURN_TYPES = ("IMAGE", "STRING", "NUMBER", "INT", "VIDEO", "AUDIO", "FLOAT", "INT")
    RETURN_NAMES = ("images", "filename", "index", "int", "video", "audio", "fps", "frame_count")
    FUNCTION = "get_video_path_by_index"
    CATEGORY = "🤖 CCTech/Files"
    OUTPUT_NODE = True

    _advance = GetImageFileByIndexNode._advance

    def get_video_path_by_index(self, directory_path, mode, start, stop, step, unique_id, reset_bool):
        files = _walk_files(directory_path, video_extensions)
        counter, result = self._advance(unique_id, mode, start, stop, step, reset_bool, len(files))
        path = files[result]
        video, images, audio, fps, frame_count = _load_video_outputs(path)
        token = _register_preview(path)

        duration = frame_count / fps if fps > 0 else 0
        h, w = images.shape[1], images.shape[2]
        video_info_text = (f"{w}x{h} • {frame_count} frames • {fps:.2f} fps • "
                           f"{duration:.2f}s • Index: {result} / {len(files) - 1}"
                           + ("" if audio is not None else " • no audio"))
        return {
            "ui": {
                "text": ["video", token, os.path.basename(path), video_info_text],
            },
            "result": (images, path, float(counter), int(counter),
                       video, audio, fps, frame_count),
        }


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
