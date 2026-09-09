#!/usr/bin/env python3
"""The save-anywhere nodes (save_anywhere.py), no server needed: they write
straight to disk, so the contract is the filesystem.

Run with giga-server's backend venv (numpy/PIL, torch stubbed):

  & D:\Projects\giga-server\src\backend\.venv\Scripts\python.exe tests\run_save_anywhere_tests.py

torch is stubbed with the same tensor shim the PC-save tests use; the video
node gets a fake VIDEO that records save_to() calls - the encode itself is
comfy-core's job, already tested upstream.
"""
from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
NODES = HERE.parent
sys.path.insert(0, str(NODES))

ART = NODES / "tests" / "_anywhere_art"


class _FakeTensor:
    """The slice of torch's surface SaveImageToFolder actually uses."""

    def __init__(self, arr):
        self._arr = np.asarray(arr, dtype=np.float32)

    @property
    def shape(self):
        return self._arr.shape

    def cpu(self):
        return self

    def numpy(self):
        return self._arr

    def __iter__(self):
        return iter(_FakeTensor(f) for f in self._arr)


class _FakeVideo:
    """Records what SaveVideoToFolder hands to comfy's writer."""

    def __init__(self):
        self.calls = []

    def get_dimensions(self):
        return (4, 4)

    def save_to(self, path, format=None, codec=None, metadata=None,
                bit_depth=None, crf=None):
        self.calls.append({"path": path, "format": str(format), "codec": str(codec),
                           "metadata": metadata, "bit_depth": bit_depth, "crf": crf})
        Path(path).write_bytes(b"fakevideo")


import save_anywhere  # noqa: E402


# ---- the checks ---------------------------------------------------------------

def test_image_node():
    from PIL import Image
    node = save_anywhere.SaveImageToFolder()
    folder = ART / "img"
    batch = _FakeTensor(np.zeros((2, 4, 4, 3), dtype=np.float32))

    out = node.save(batch, str(folder), "ComfyUI", prompt={"3": {"class_type": "KSampler"}},
                    extra_pnginfo={"workflow": {"nodes": []}})
    names = sorted(p.name for p in folder.glob("*.png"))
    assert names == ["ComfyUI_00001_.png", "ComfyUI_00002_.png"], names
    assert out["result"][0] is batch  # passthrough, stock-style
    assert len(out["result"][1].splitlines()) == 2
    # ui.previews is the gallery contract: one dict per saved file. ComfyUI
    # flattens ui[k] across executions, so a list of dicts is what the widget
    # actually sees for a batch of 2 (nested lists inside ui.text do not survive).
    previews = out["ui"]["previews"]
    assert [p["title"] for p in previews] == names, previews
    assert all(p["kind"] == "image" and p["path"].endswith(p["title"]) for p in previews)

    # counter never overwrites: second run continues the sequence
    node.save(batch, str(folder), "ComfyUI")
    names = sorted(p.name for p in folder.glob("*.png"))
    assert names == [f"ComfyUI_{i:05}_.png" for i in range(1, 5)], names

    # workflow metadata embedded like stock SaveImage
    img = Image.open(folder / "ComfyUI_00001_.png")
    assert json.loads(img.info["prompt"])["3"]["class_type"] == "KSampler"
    assert json.loads(img.info["workflow"])["nodes"] == []

    # a fresh prefix starts at 1; pre-existing counters are respected
    (folder / "Other_00042_.png").write_bytes(b"x")
    node.save(_FakeTensor(np.zeros((1, 4, 4, 3))), str(folder), "Other")
    assert (folder / "Other_00043_.png").is_file()
    node.save(_FakeTensor(np.zeros((1, 4, 4, 3))), str(folder), "Fresh")
    assert (folder / "Fresh_00001_.png").is_file()

    # jpeg path (RGB conversion + .jpg ext), quoted folder tolerated
    jfolder = ART / "quoted dir"
    node.save(_FakeTensor(np.zeros((1, 4, 4, 3))), f'"{jfolder}"', "shot", format="jpeg")
    assert (jfolder / "shot_00001_.jpg").is_file()

    # missing nested folders are created
    node.save(_FakeTensor(np.zeros((1, 4, 4, 3))), str(ART / "deep" / "nested" / "dir"), "n")
    assert (ART / "deep" / "nested" / "dir" / "n_00001_.png").is_file()

    # prefix vars expand
    node.save(_FakeTensor(np.zeros((1, 4, 4, 3))), str(ART / "vars"), "%width%x%height%")
    assert (ART / "vars" / "4x4_00001_.png").is_file()

    # empty path is a loud error, not a mystery write
    try:
        node.save(batch, "", "ComfyUI")
        raise AssertionError("empty folder_path should raise")
    except RuntimeError as e:
        assert "destination folder" in str(e)


def test_video_node():
    node = save_anywhere.SaveVideoToFolder()
    folder = ART / "vid"
    video = _FakeVideo()

    out = node.save(video, str(folder), "clip", prompt={"1": {"class_type": "CreateVideo"}})
    call = video.calls[-1]
    assert call["path"].endswith("clip_00001_.mp4"), call["path"]
    assert call["codec"] == "auto"
    assert call["crf"] is None
    assert call["metadata"]["prompt"] == {"1": {"class_type": "CreateVideo"}}
    assert len(out["ui"]["previews"]) == 1
    assert out["ui"]["previews"][0]["kind"] == "video"
    assert out["ui"]["previews"][0]["title"] == "clip_00001_.mp4"

    # counter advances, crf >= 0 forces the value through
    node.save(video, str(folder), "clip", codec="h264", crf=20)
    assert video.calls[-1]["path"].endswith("clip_00002_.mp4")
    assert video.calls[-1]["crf"] == 20

    # quoted path tolerated, empty path loud
    node.save(video, f'"{ART / "q vid"}"', "v")
    assert (ART / "q vid" / "v_00001_.mp4").is_file()
    try:
        node.save(video, "  ", "v")
        raise AssertionError("empty folder_path should raise")
    except RuntimeError as e:
        assert "destination folder" in str(e)


def test_comfy_flattens_preview_cells_across_executions():
    """ComfyUI's get_output_from_returns concatenates ui[k]. Two video
    executions (a batch of 2) must yield TWO preview cells, not a smashed
    text tuple that only shows the first file."""
    node = save_anywhere.SaveVideoToFolder()
    folder = ART / "vid_batch"
    ua = node.save(_FakeVideo(), str(folder), "pair")["ui"]
    ub = node.save(_FakeVideo(), str(folder), "pair")["ui"]
    merged = {k: [y for x in (ua, ub) for y in x[k]] for k in ua}
    assert [p["title"] for p in merged["previews"]] == [
        "pair_00001_.mp4", "pair_00002_.mp4"
    ], merged["previews"]


def test_counter_helper():
    folder = ART / "counter"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("pre_00007_.png", "pre_00003_.png", "pre.txt", "pre_abc_.png",
                 "different_00099_.png"):
        (folder / name).write_bytes(b"x")
    assert save_anywhere._next_counter(folder, "pre") == 8
    assert save_anywhere._next_counter(folder, "missing") == 1
    assert save_anywhere._expand_vars("w%width% h%height%", 64, 32) == "w64 h32"


# ---- runner -------------------------------------------------------------------

def main() -> int:
    if ART.exists():
        shutil.rmtree(ART)
    tests = [test_image_node, test_video_node,
             test_comfy_flattens_preview_cells_across_executions, test_counter_helper]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL {test.__name__}")
            traceback.print_exc()
    if not failed:
        print(f"save-anywhere: all {len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
