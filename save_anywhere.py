# (c) CCTech || Apache-2.0 (apache.org/licenses/LICENSE-2.0)
"""The two LOCAL save-anywhere nodes:

  SaveImageToFolder  "Save Image to Folder ⚡"  image tensors -> encoded straight to disk
  SaveVideoToFolder  "Save Video to Folder ⚡"  a VIDEO input -> comfy's own save_to() writer

Stock Save Image / Save Video deliberately refuse to write outside ComfyUI's
output directory (folder_paths.get_save_image_path's is_within_directory
guard). These nodes drop that guard: "folder_path" is any absolute path on
this machine, created if missing. Everything else is stock behavior - the
same filename counter (prefix_00001_.ext, never overwriting), the same
%width%/%height%/%year%... prefix vars, and the same embedded workflow
metadata (PROMPT + EXTRA_PNGINFO in PNG text chunks / container metadata).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

CATEGORY = "🤖 CCTech/Files"

# auto follows the source container; everything lands as mp4 (comfy parity)
_CONTAINER_EXTENSIONS = {"auto": "mp4", "mp4": "mp4"}


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

def _resolve_folder(path_str: str, node: str) -> Path:
    """Any absolute folder on this machine; created when missing. Surrounding
    quotes (from copy-pasted paths) are stripped, VideoPathLoader-style."""
    raw = (path_str or "").strip().strip('"')
    if not raw:
        raise RuntimeError(f"{node}: no destination folder set - put any absolute path "
                           f"in 'folder_path' (e.g. D:\\Pictures\\Renders)")
    folder = Path(raw)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(f"{node}: cannot use destination folder '{folder}' ({e})") from e
    return folder


def _expand_vars(text: str, width: int = 0, height: int = 0) -> str:
    """The prefix variables stock's get_save_image_path supports."""
    if "%" not in text:
        return text
    now = time.localtime()
    for var, val in (("%width%", str(width)), ("%height%", str(height)),
                     ("%year%", str(now.tm_year)), ("%month%", f"{now.tm_mon:02d}"),
                     ("%day%", f"{now.tm_mday:02d}"), ("%hour%", f"{now.tm_hour:02d}"),
                     ("%minute%", f"{now.tm_min:02d}"), ("%second%", f"{now.tm_sec:02d}")):
        text = text.replace(var, val)
    return text


def _next_counter(folder: Path, filename: str) -> int:
    """Stock counter logic: highest existing '<filename>_<digits>_' + 1."""
    stem = filename + "_"
    best = 0
    try:
        entries = os.listdir(folder)
    except OSError:
        return 1
    for entry in entries:
        if os.path.normcase(entry[:len(stem)]) != os.path.normcase(stem):
            continue
        try:
            best = max(best, int(entry[len(stem):].split(".")[0].split("_")[0]))
        except ValueError:
            continue
    return best + 1


def _metadata_disabled() -> bool:
    try:
        from comfy.cli_args import args
        return bool(args.disable_metadata)
    except Exception:
        return False


def _as_container(format_name: str):
    try:
        from comfy_api.latest import Types
        return Types.VideoContainer(format_name)
    except Exception:
        return format_name


def _as_codec(codec_name: str):
    try:
        from comfy_api.latest import Types
        return Types.VideoCodec(codec_name)
    except Exception:
        return codec_name


def _format_options() -> list[str]:
    try:
        from comfy_api.latest import Types
        return Types.VideoContainer.as_input()
    except Exception:
        return ["auto", "mp4"]


def _codec_options() -> list[str]:
    try:
        from comfy_api.latest import Types
        return Types.VideoCodec.as_input()
    except Exception:
        return ["auto", "h264"]


# ---------------------------------------------------------------------------
# Save Image to Folder
# ---------------------------------------------------------------------------

class SaveImageToFolder:
    SEARCH_ALIASES = ["save image", "save image to folder", "save image anywhere",
                      "export image", "write image"]
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "The images to save."}),
                "folder_path": ("STRING", {"default": "",
                    "tooltip": "Absolute destination folder - ANY folder on this computer, "
                               "created if it does not exist."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI",
                    "tooltip": "The prefix for the file to save. Supports %width% %height% "
                               "%year% %month% %day% %hour% %minute% %second%, like the "
                               "stock Save Image. A _00001_ counter is appended so files "
                               "are never overwritten."}),
            },
            "optional": {
                "format": (["png", "jpeg", "webp"],
                           {"tooltip": "png embeds the workflow metadata; jpeg/webp do not."}),
                "jpeg_quality": ("INT", {"default": 92, "min": 1, "max": 100}),
                "webp_quality": ("INT", {"default": 92, "min": 1, "max": 100}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO",
                       "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "saved_paths")
    FUNCTION = "save"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Saves the input images to ANY folder on this computer (not just "
                   "ComfyUI's output directory). The folder is created if missing; a "
                   "stock-style counter keeps files from being overwritten; PNGs embed "
                   "the workflow metadata just like the stock Save Image.")

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def save(self, images, folder_path, filename_prefix, format="png", jpeg_quality=92,
             webp_quality=92, prompt=None, extra_pnginfo=None, unique_id=None):
        import numpy as np
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo

        node = "Save Image to Folder"
        folder = _resolve_folder(folder_path, node)
        h, w = int(images.shape[1]), int(images.shape[2])
        prefix = _expand_vars(filename_prefix, w, h)
        counter = _next_counter(folder, prefix)
        ext = {"jpeg": "jpg"}.get(format, format)

        metadata = None
        if format == "png" and not _metadata_disabled() and (prompt is not None or extra_pnginfo):
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo:
                for key in extra_pnginfo:
                    metadata.add_text(key, json.dumps(extra_pnginfo[key]))

        saved = []
        for image in images:
            arr = (255.0 * image.cpu().numpy())
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
            file = f"{prefix}_{counter:05}_.{ext}"
            target = folder / file
            if format == "png":
                img.save(target, pnginfo=metadata, compress_level=4)
            elif format == "jpeg":
                img.convert("RGB").save(target, format="JPEG", quality=jpeg_quality)
            else:
                img.save(target, format="WEBP", quality=webp_quality)
            saved.append(str(target))
            counter += 1

        info = f"{w}x{h} • {len(saved)} file{'' if len(saved) == 1 else 's'} • {folder}"
        return {"ui": {"text": ["image", saved[0], os.path.basename(saved[0]), info,
                                saved]},
                "result": (images, "\n".join(saved))}


# ---------------------------------------------------------------------------
# Save Video to Folder
# ---------------------------------------------------------------------------

class SaveVideoToFolder:
    SEARCH_ALIASES = ["save video", "save video to folder", "save video anywhere",
                      "export video", "write video"]
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("VIDEO", {"tooltip": "The video to save (any LoadVideo-style "
                                               "VIDEO output)."}),
                "folder_path": ("STRING", {"default": "",
                    "tooltip": "Absolute destination folder - ANY folder on this computer, "
                               "created if it does not exist."}),
                "filename_prefix": ("STRING", {"default": "ComfyUI",
                    "tooltip": "The prefix for the file to save. Supports %width% %height% "
                               "%year% %month% %day% %hour% %minute% %second%. A _00001_ "
                               "counter is appended so files are never overwritten."}),
            },
            "optional": {
                "format": (_format_options(),
                           {"tooltip": "auto keeps the source container (saved as .mp4)."}),
                "codec": (_codec_options(),
                          {"tooltip": "h264 re-encodes; auto copies the stream when "
                                      "compatible."}),
                "crf": ("INT", {"default": -1, "min": -1, "max": 51,
                    "tooltip": "Quality for re-encoding (lower = better/bigger). -1 leaves "
                               "it to ComfyUI; setting it forces a re-encode, like the "
                               "stock Save Video."}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO",
                       "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("video", "saved_path")
    FUNCTION = "save"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Saves the input video to ANY folder on this computer (not just "
                   "ComfyUI's output directory), using ComfyUI's own writer - streams are "
                   "copied when compatible, re-encoded only when the format/codec/crf "
                   "require it. The folder is created if missing; a stock-style counter "
                   "keeps files from being overwritten.")

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def save(self, video, folder_path, filename_prefix, format="auto", codec="auto",
             crf=-1, prompt=None, extra_pnginfo=None, unique_id=None):
        node = "Save Video to Folder"
        folder = _resolve_folder(folder_path, node)
        try:
            width, height = video.get_dimensions()
        except Exception:
            width = height = 0
        prefix = _expand_vars(filename_prefix, width, height)
        counter = _next_counter(folder, prefix)
        ext = _CONTAINER_EXTENSIONS.get(format, "mp4")
        target = folder / f"{prefix}_{counter:05}_.{ext}"

        metadata = None
        if not _metadata_disabled():
            metadata = dict(extra_pnginfo) if extra_pnginfo else {}
            if prompt is not None:
                metadata["prompt"] = prompt
            metadata = metadata or None

        video.save_to(str(target), format=_as_container(format), codec=_as_codec(codec),
                      metadata=metadata, crf=None if crf is None or crf < 0 else crf)

        size_mb = os.path.getsize(target) / 1024 / 1024
        info = (f"{width}x{height} • {size_mb:.1f} MB • {folder}")
        return {"ui": {"text": ["video", str(target), target.name, info]},
                "result": (video, str(target))}


NODE_CLASS_MAPPINGS = {"SaveImageToFolder": SaveImageToFolder,
                       "SaveVideoToFolder": SaveVideoToFolder}
NODE_DISPLAY_NAME_MAPPINGS = {"SaveImageToFolder": "Save Image to Folder ⚡",
                              "SaveVideoToFolder": "Save Video to Folder ⚡"}
