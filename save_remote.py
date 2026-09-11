# (c) CCTech || Apache-2.0 (apache.org/licenses/LICENSE-2.0)
"""The two SAVE nodes (giga-server docs/00 §5, docs/06):

  SaveImageToRemote  "Save Image to Remote ⚡"   image tensors -> in-memory encode -> POST
  SaveVideoToRemote  "Save Video to Remote ⚡"   a rendered video/file on disk -> streamed POST

Configuration lives ON the node as widgets — receiver_url, subfolder,
filename_prefix — and rides in the workflow JSON (owner ruling
2026-09-10: no sidecar config file, no save_key; subfolder is the single
routing mechanism). receiver_url is route-agnostic: the SSH-route default
http://127.0.0.1:8790, or a cloudflared public URL pasted from the app.

Metadata: the image node embeds the full prompt + workflow into the PNG's
text chunks exactly as ComfyUI's stock save does — NOTHING is scrubbed
(owner: "the comfy stock node doesn't scrub any data and neither will
we"), so files drag straight back into ComfyUI.

Failure policy — FAIL LOUD ONLY (owner, 2026-09-10): no retries, no
spool, nothing is written on the pod. Any failure raises immediately,
naming the URL and the receiver's own dotted code/message; a failed
unsent image is gone (re-queue the workflow). delete_after_success fires
only on confirmed success, so a video's source always survives its own
failed delivery.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

CATEGORY = "🤖 CCTech/Files"

#: The SSH-route default (the pod's end of the reverse tunnel).
DEFAULT_RECEIVER_URL = "http://127.0.0.1:8790"


def check_receiver_url(url: str) -> str:
    """The one validation the node does locally — loud, before any transfer."""
    url = (url or "").strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise RuntimeError(
            f"receiver_url must be http(s)://host:port — got {url!r}. "
            f"Use {DEFAULT_RECEIVER_URL} for the SSH-linked receiver.")
    return url.rstrip("/")


# ---------------------------------------------------------------------------
# the POST (shared)
# ---------------------------------------------------------------------------

def _post(url: str, node: str, data: dict, files: dict, timeout: float,
          verify_tls: bool = True, stream: bool = False) -> dict:
    url = check_receiver_url(url) + "/api/v1/upload"
    started = time.monotonic()
    try:
        r = requests.post(url, data=data, files=files, timeout=timeout,
                          verify=verify_tls, stream=stream)
    except requests.RequestException as e:
        raise RuntimeError(f"{node}: receiver at {url} unreachable ({e})") from e
    finally:
        if not stream:
            for _, f in files.items():
                getattr(f, "close", lambda: None)()
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code != 200 or not body.get("ok"):
        err = body.get("error", {})
        code = err.get("code", f"http.{r.status_code}")
        message = err.get("message", r.text[:200])
        raise RuntimeError(f"{node}: receiver at {url} refused the save [{code}]: {message}")
    body["_duration_ms"] = int((time.monotonic() - started) * 1000)
    return body


def _metadata_fields(**kw) -> dict:
    """Form fields: identity only — the receiver decides where it goes."""
    out = {}
    for key in ("media_type", "filename_prefix", "model_name", "workflow_name",
                "prompt", "negative_prompt", "seed", "width", "height", "steps", "cfg",
                "sampler", "scheduler", "subfolder", "job_id", "generation_id",
                "source_filename", "index"):
        v = kw.get(key)
        if v not in (None, "", 0, 0.0):
            out[key] = str(v)
    extra = kw.get("extra_metadata")
    if extra:
        try:
            json.loads(extra)  # invalid JSON is a hard input error (docs/03)
        except ValueError as e:
            raise RuntimeError(f"extra_metadata is not valid JSON: {e}") from e
        out["metadata"] = extra
    return out


# ---------------------------------------------------------------------------
# Save Image to Remote
# ---------------------------------------------------------------------------

class SaveImageToRemote:
    SEARCH_ALIASES = ["save image", "save image remote", "upload image", "send image", "remote save"]
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "receiver_url": ("STRING", {"default": DEFAULT_RECEIVER_URL}),
                "subfolder": ("STRING", {"default": ""}),
                "filename_prefix": ("STRING", {"default": ""}),
                "model_name": ("STRING", {"default": ""}),
                "workflow_name": ("STRING", {"default": ""}),
                "positive_prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**63 - 1}),
            },
            "optional": {
                "format": (["png", "jpeg", "webp"],),
                "jpeg_quality": ("INT", {"default": 92, "min": 1, "max": 100}),
                "webp_quality": ("INT", {"default": 92, "min": 1, "max": 100}),
                "timeout": ("INT", {"default": 120, "min": 5, "max": 3600}),
                "verify_tls": ("BOOLEAN", {"default": True}),
                "job_id": ("STRING", {"default": ""}),
                "generation_id": ("STRING", {"default": ""}),
                "width": ("INT", {"default": 0, "min": 0}),
                "height": ("INT", {"default": 0, "min": 0}),
                "steps": ("INT", {"default": 0, "min": 0}),
                "cfg": ("FLOAT", {"default": 0.0}),
                "sampler": ("STRING", {"default": ""}),
                "scheduler": ("STRING", {"default": ""}),
                "extra_metadata": ("STRING", {"multiline": True, "default": ""}),
            },
            "hidden": {"unique_id": "UNIQUE_ID", "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_paths",)
    FUNCTION = "save"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Encode each image in memory and send it to the remote receiver — "
                   "nothing is written on this machine. The full prompt + workflow "
                   "embed into the PNG exactly like the stock save, so the file drags "
                   "straight back into ComfyUI. receiver_url is the route: the SSH "
                   "default 127.0.0.1:8790, or the public URL the receiver app shows "
                   "for the cloudflared route. Failures are loud — re-queue the workflow.")

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def save(self, images, receiver_url, subfolder, filename_prefix, model_name,
             workflow_name, positive_prompt, negative_prompt, seed, format="png",
             jpeg_quality=92, webp_quality=90, timeout=120, verify_tls=True,
             job_id="", generation_id="", width=0, height=0,
             steps=0, cfg=0.0, sampler="", scheduler="", extra_metadata="",
             unique_id=None, prompt=None, extra_pnginfo=None):
        from PIL import Image  # ComfyUI's stack; encode is in-memory (docs/03)

        check_receiver_url(receiver_url)
        batch, h, w = images.shape[0], int(images.shape[1]), int(images.shape[2])
        ext = {"jpeg": "jpg"}.get(format, format)
        quality = {"jpeg": jpeg_quality, "webp": webp_quality}.get(format)
        saved, ui_rows = [], []
        for i in range(batch):
            arr = (images[i].detach().cpu().numpy() * 255.0).clip(0, 255).astype("uint8")
            img = Image.fromarray(arr)
            buf = io.BytesIO()
            if format == "png":
                # Native-parity embedding: the API prompt + every extra_pnginfo
                # key (the UI's "workflow") as PNG text chunks. Nothing scrubbed.
                pnginfo = None
                if prompt is not None or extra_pnginfo:
                    from PIL.PngImagePlugin import PngInfo
                    pnginfo = PngInfo()
                    if prompt is not None:
                        pnginfo.add_text("prompt", json.dumps(prompt))
                    if extra_pnginfo:
                        for k, v in extra_pnginfo.items():
                            pnginfo.add_text(str(k), json.dumps(v))
                img.save(buf, format="PNG", pnginfo=pnginfo)
            elif format == "jpeg":
                img.convert("RGB").save(buf, format="JPEG", quality=quality)
            else:
                img.save(buf, format="WEBP", quality=quality)
            payload = buf.getvalue()
            name = f"{filename_prefix}{i:05}.{ext}" if filename_prefix else f"image_{i:05}.{ext}"
            fields = _metadata_fields(
                media_type="image", filename_prefix=filename_prefix,
                model_name=model_name, workflow_name=workflow_name, prompt=positive_prompt,
                negative_prompt=negative_prompt, seed=seed, width=width or w, height=height or h,
                steps=steps, cfg=cfg, sampler=sampler, scheduler=scheduler, subfolder=subfolder,
                job_id=job_id, generation_id=generation_id, source_filename=name, index=i,
                extra_metadata=extra_metadata)
            body = _post(receiver_url, "Save Image to Remote", fields,
                         {"file": (name, payload, "application/octet-stream")},
                         timeout=timeout, verify_tls=verify_tls)
            saved.append(body["saved_to"])
            ui_rows.append(["image", body["saved_to"], body["filename"],
                            f"{body['size_bytes'] / 1024:.0f} KB in {body['_duration_ms']} ms"])
        return {"ui": {"text": ui_rows}, "result": ("\n".join(saved),)}


# ---------------------------------------------------------------------------
# Save Video to Remote
# ---------------------------------------------------------------------------

_MEDIA_BY_EXT = {"mp4": "video", "webm": "video", "mkv": "video", "mov": "video",
                 "gif": "video", "png": "image", "jpg": "image", "jpeg": "image",
                 "webp": "image", "mp3": "audio", "wav": "audio", "flac": "audio",
                 "ogg": "audio", "m4a": "audio"}


class SaveVideoToRemote:
    SEARCH_ALIASES = ["save video", "save video remote", "upload video", "save file", "send to remote"]
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "file_path": ("STRING", {"default": ""}),
                "receiver_url": ("STRING", {"default": DEFAULT_RECEIVER_URL}),
                "subfolder": ("STRING", {"default": ""}),
            },
            "optional": {
                "filename": ("STRING", {"default": ""}),
                "timeout": ("INT", {"default": 300, "min": 5, "max": 3600}),
                "verify_tls": ("BOOLEAN", {"default": True}),
                "model_name": ("STRING", {"default": ""}),
                "workflow_name": ("STRING", {"default": ""}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**63 - 1}),
                "job_id": ("STRING", {"default": ""}),
                "extra_metadata": ("STRING", {"multiline": True, "default": ""}),
                "delete_after_success": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "save"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Stream a finished video (or any completed file) to the remote "
                   "receiver and wait for the write confirmation. receiver_url is the "
                   "route (SSH default 127.0.0.1:8790 or the cloudflared public URL). "
                   "delete_after_success removes the source only AFTER the receiver "
                   "confirms; a failed delivery never deletes it.")

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def save(self, file_path, receiver_url, subfolder, filename="", timeout=300,
             verify_tls=True, model_name="", workflow_name="", prompt="", seed=0,
             job_id="", extra_metadata="", delete_after_success=False, unique_id=None):
        source = Path(file_path)
        if not source.is_file():
            raise RuntimeError(f"Save Video to Remote: file not found: {file_path}")
        ext = source.suffix.lstrip(".") or "bin"
        name = (filename or source.name)
        fields = _metadata_fields(
            media_type=_MEDIA_BY_EXT.get(ext.lower(), "file"),
            model_name=model_name, workflow_name=workflow_name, prompt=prompt,
            seed=seed, job_id=job_id, subfolder=subfolder, source_filename=name,
            extra_metadata=extra_metadata)
        with open(source, "rb") as fh:
            body = _post(receiver_url, "Save Video to Remote", fields,
                         {"file": (name, fh, "application/octet-stream")},
                         timeout=timeout, verify_tls=verify_tls)
        detail = (f"{body['size_bytes'] / 1024 / 1024:.1f} MB in "
                  f"{body['_duration_ms']} ms -> {body['saved_to']}")
        if delete_after_success:
            source.unlink()  # only after ok: true (docs — never before)
            detail += f" (source deleted: {source})"
        return {"ui": {"text": [["video", body["saved_to"], body["filename"], detail]]},
                "result": (body["saved_to"],)}


NODE_CLASS_MAPPINGS = {"SaveImageToRemote": SaveImageToRemote, "SaveVideoToRemote": SaveVideoToRemote}
NODE_DISPLAY_NAME_MAPPINGS = {"SaveImageToRemote": "Save Image to Remote ⚡",
                              "SaveVideoToRemote": "Save Video to Remote ⚡"}
