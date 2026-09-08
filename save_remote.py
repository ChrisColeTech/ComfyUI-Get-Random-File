# (c) CCTech || Apache-2.0 (apache.org/licenses/LICENSE-2.0)
"""The two SAVE nodes (giga-server docs/03 § The Save Nodes):

  SaveImageToPC  "Save Image to PC ⚡"   image tensors -> in-memory encode -> POST
  SaveVideoToPC  "Save Video to PC ⚡"   a rendered video/file on disk -> streamed POST

Both send to a receiver profile from receiver_config.json beside this module
(auto-created as a template on first import) — never hardcoded URLs. The
receiver owns all routing (save_key -> local folder); this side only sends
identity: model, workflow, seed, prompt. Success means the receiver confirmed
the write; failure is a loud RuntimeError naming the profile and URL.
"""
from __future__ import annotations

import io
import json
import os
import re
import time
from pathlib import Path

import requests

CATEGORY = "🤖 CCTech/Files"
HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "receiver_config.json"

# The template written on first import — token empty until the user fills it
# from the receiver's Dashboard token block (docs/03 § Node Config).
CONFIG_TEMPLATE = {
    "receivers": [
        {"name": "Home PC", "url": "http://100.81.23.51:8790", "token": "",
         "timeout": 120, "verify_tls": True, "enabled": True},
    ],
    "default_receiver": "Home PC",
    "default_save_key": "default",
}


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        CONFIG_PATH.write_text(json.dumps(CONFIG_TEMPLATE, indent=2), encoding="utf-8")
        print(f"[CCTech Save] created receiver config template: {CONFIG_PATH} — "
              "fill in the token (the receiver UI generates it)")
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except ValueError:
        print(f"[CCTech Save] WARNING: {CONFIG_PATH.name} is not valid JSON — using defaults")
        return json.loads(json.dumps(CONFIG_TEMPLATE))
    cfg.setdefault("receivers", [])
    cfg.setdefault("default_receiver", "")
    cfg.setdefault("default_save_key", "default")
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def receiver_names() -> list[str]:
    cfg = load_config()
    enabled = [r["name"] for r in cfg["receivers"] if r.get("enabled")]
    default = cfg.get("default_receiver")
    if default in enabled:
        enabled.remove(default)
        enabled.insert(0, default)
    return enabled or ["<configure receiver_config.json>"]


def _resolve_receiver(name: str) -> dict:
    cfg = load_config()
    for r in cfg["receivers"]:
        if r["name"] == name and r.get("enabled", True):
            return r
    choices = ", ".join(receiver_names()) or "none configured"
    raise RuntimeError(f"receiver profile '{name}' not found or disabled ({choices})")


# ---------------------------------------------------------------------------
# the POST (shared)
# ---------------------------------------------------------------------------

def _post(receiver: dict, node: str, data: dict, files: dict, stream: bool = False) -> dict:
    url = receiver["url"].rstrip("/") + "/api/v1/upload"
    timeout = float(receiver.get("timeout", 120))
    started = time.monotonic()
    try:
        r = requests.post(url, data=data, files=files, timeout=timeout,
                          verify=receiver.get("verify_tls", True), stream=stream,
                          headers={"Authorization": f"Bearer {receiver.get('token', '')}"})
    except requests.RequestException as e:
        raise RuntimeError(f"{node}: receiver '{receiver['name']}' at {url} unreachable ({e})") from e
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
        raise RuntimeError(f"{node}: receiver '{receiver['name']}' refused the save "
                           f"[{code}]: {message}")
    body["_duration_ms"] = int((time.monotonic() - started) * 1000)
    return body


def _metadata_fields(**kw) -> dict:
    """Form fields: identity only — the receiver decides where it goes."""
    out = {}
    for key in ("save_key", "media_type", "filename_prefix", "model_name", "workflow_name",
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
# Save Image to PC
# ---------------------------------------------------------------------------

class SaveImageToPC:
    SEARCH_ALIASES = ["save image", "upload image", "save to pc", "remote save"]
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "receiver_profile": (receiver_names(),),
                "save_key": ("STRING", {"default": load_config()["default_save_key"]}),
                "filename_prefix": ("STRING", {"default": ""}),
                "model_name": ("STRING", {"default": ""}),
                "workflow_name": ("STRING", {"default": ""}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2**63 - 1}),
            },
            "optional": {
                "format": (["png", "jpeg", "webp"],),
                "jpeg_quality": ("INT", {"default": 92, "min": 1, "max": 100}),
                "webp_quality": ("INT", {"default": 92, "min": 1, "max": 100}),
                "subfolder": ("STRING", {"default": ""}),
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
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_paths",)
    FUNCTION = "save"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Encode each image in memory and save it directly to the local-PC "
                   "receiver — no copy in ComfyUI's output folder. The receiver's save "
                   "profile decides the destination folder and filename.")

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def save(self, images, receiver_profile, save_key, filename_prefix, model_name,
             workflow_name, prompt, negative_prompt, seed, format="png",
             jpeg_quality=92, webp_quality=90, subfolder="", job_id="",
             generation_id="", width=0, height=0, steps=0, cfg=0.0, sampler="",
             scheduler="", extra_metadata="", unique_id=None):
        from PIL import Image  # ComfyUI's stack; encode is in-memory (docs/03)

        receiver = _resolve_receiver(receiver_profile)
        batch, h, w = images.shape[0], int(images.shape[1]), int(images.shape[2])
        ext = {"jpeg": "jpg"}.get(format, format)
        quality = {"jpeg": jpeg_quality, "webp": webp_quality}.get(format)
        saved, ui_rows = [], []
        for i in range(batch):
            arr = (images[i].detach().cpu().numpy() * 255.0).clip(0, 255).astype("uint8")
            img = Image.fromarray(arr)
            buf = io.BytesIO()
            if format == "png":
                img.save(buf, format="PNG")
            elif format == "jpeg":
                img.convert("RGB").save(buf, format="JPEG", quality=quality)
            else:
                img.save(buf, format="WEBP", quality=quality)
            payload = buf.getvalue()
            name = f"{filename_prefix}{i:05}.{ext}" if filename_prefix else f"image_{i:05}.{ext}"
            fields = _metadata_fields(
                save_key=save_key, media_type="image", filename_prefix=filename_prefix,
                model_name=model_name, workflow_name=workflow_name, prompt=prompt,
                negative_prompt=negative_prompt, seed=seed, width=width or w, height=height or h,
                steps=steps, cfg=cfg, sampler=sampler, scheduler=scheduler, subfolder=subfolder,
                job_id=job_id, generation_id=generation_id, source_filename=name, index=i,
                extra_metadata=extra_metadata)
            body = _post(receiver, "Save Image to PC", fields,
                         {"file": (name, payload, "application/octet-stream")})
            saved.append(body["saved_to"])
            ui_rows.append(["image", body["saved_to"], body["filename"],
                            f"{body['size_bytes'] / 1024:.0f} KB in {body['_duration_ms']} ms"])
        return {"ui": {"text": ui_rows}, "result": ("\n".join(saved),)}


# ---------------------------------------------------------------------------
# Save Video to PC
# ---------------------------------------------------------------------------

_MEDIA_BY_EXT = {"mp4": "video", "webm": "video", "mkv": "video", "mov": "video",
                 "gif": "video", "png": "image", "jpg": "image", "jpeg": "image",
                 "webp": "image", "mp3": "audio", "wav": "audio", "flac": "audio",
                 "ogg": "audio", "m4a": "audio"}


class SaveVideoToPC:
    SEARCH_ALIASES = ["save video", "upload video", "save file", "send to pc"]
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "file_path": ("STRING", {"default": ""}),
                "receiver_profile": (receiver_names(),),
                "save_key": ("STRING", {"default": load_config()["default_save_key"]}),
            },
            "optional": {
                "filename": ("STRING", {"default": ""}),
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
    DESCRIPTION = ("Stream a finished video (or any completed file) to the local-PC "
                   "receiver and wait for the write confirmation. delete_after_success "
                   "removes the source only AFTER the receiver confirms the save.")

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def save(self, file_path, receiver_profile, save_key, filename="", model_name="",
             workflow_name="", prompt="", seed=0, job_id="", extra_metadata="",
             delete_after_success=False, unique_id=None):
        source = Path(file_path)
        if not source.is_file():
            raise RuntimeError(f"Save Video to PC: file not found: {file_path}")
        receiver = _resolve_receiver(receiver_profile)
        ext = source.suffix.lstrip(".") or "bin"
        name = (filename or source.name)
        fields = _metadata_fields(
            save_key=save_key, media_type=_MEDIA_BY_EXT.get(ext.lower(), "file"),
            model_name=model_name, workflow_name=workflow_name, prompt=prompt,
            seed=seed, job_id=job_id, source_filename=name,
            extra_metadata=extra_metadata)
        with open(source, "rb") as fh:
            body = _post(receiver, "Save Video to PC", fields,
                         {"file": (name, fh, "application/octet-stream")})
        detail = (f"{body['size_bytes'] / 1024 / 1024:.1f} MB in "
                  f"{body['_duration_ms']} ms -> {body['saved_to']}")
        if delete_after_success:
            source.unlink()  # only after ok: true (docs/03 — never before)
            detail += f" (source deleted: {source})"
        return {"ui": {"text": [["video", body["saved_to"], body["filename"], detail]]},
                "result": (body["saved_to"],)}


# ---------------------------------------------------------------------------
# PromptServer routes: config over HTTP, so a UI can manage it (docs/03)
# ---------------------------------------------------------------------------

def register_config_routes() -> None:
    try:
        from server import PromptServer
        from aiohttp import web
    except ImportError:
        return
    routes = PromptServer.instance.routes

    @routes.get("/cctech_save/config")
    async def _get_config(request):
        cfg = load_config()
        for r in cfg.get("receivers", []):
            if r.get("token"):
                r["token"] = "••••" + r["token"][-4:]
        return web.json_response(cfg)

    @routes.post("/cctech_save/config")
    async def _post_config(request):
        try:
            cfg = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "body is not JSON"}, status=400)
        names = [r.get("name") for r in cfg.get("receivers", [])]
        if len(names) != len(set(names)) or not all(names):
            return web.json_response({"ok": False, "error": "receiver names must be unique and set"}, status=400)
        save_config(cfg)
        return web.json_response({"ok": True})

    @routes.post("/cctech_save/test")
    async def _test_receiver(request):
        try:
            body = await request.json()
            receiver = _resolve_receiver(body.get("name", ""))
        except RuntimeError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        url = receiver["url"].rstrip("/") + "/api/v1/health"
        t0 = time.monotonic()
        try:
            r = requests.get(url, timeout=float(receiver.get("timeout", 120)) / 4 + 5,
                             verify=receiver.get("verify_tls", True))
            latency = int((time.monotonic() - t0) * 1000)
            ok = r.status_code == 200 and r.json().get("product") == "comfy-media-receiver"
            return web.json_response({"ok": ok, "version": r.json().get("version", ""),
                                      "latency_ms": latency})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=200)


NODE_CLASS_MAPPINGS = {"SaveImageToPC": SaveImageToPC, "SaveVideoToPC": SaveVideoToPC}
NODE_DISPLAY_NAME_MAPPINGS = {"SaveImageToPC": "Save Image to PC ⚡",
                              "SaveVideoToPC": "Save Video to PC ⚡"}
