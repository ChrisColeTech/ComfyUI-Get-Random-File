#!/usr/bin/env python3
"""The save nodes against a LIVE ephemeral receiver (giga-server docs/03
§Verification, R2): real uvicorn on an ephemeral port, real HTTP from
save_remote — the nodes' contract is the wire, so the test rides it.

Covers the 2026-09-10 node rulings:
  - config on the node (receiver_url/subfolder; no save_key, no config file)
  - native-parity PNG metadata embedding (prompt + workflow, nothing scrubbed)
  - FAIL LOUD ONLY: no retries, no spool, nothing written on the pod

Run with giga-server's backend venv:

  & D:\Projects\giga-server\src\backend\.venv\Scripts\python.exe tests\run_save_node_tests.py

torch is stubbed (a tiny tensor shim over numpy): the encode path only needs
shape + float numpy HWC — the shim exercises exactly that contract.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import requests

HERE = Path(__file__).resolve().parent
NODES = HERE.parent
GIGA = Path(os.environ.get("GIGA_SERVER", r"D:\Projects\giga-server")) / "src" / "backend"
sys.path.insert(0, str(NODES))
sys.path.insert(0, str(GIGA))

DATA = NODES / "tests" / "_run_data"
ART = NODES / "tests" / "_run_art"
os.environ["CMR_DATA_DIR"] = str(DATA)

import save_remote  # noqa: E402
from receiver.config import Config  # noqa: E402


class _FakeTensor:
    """The slice of torch's surface SaveImageToRemote actually uses."""

    def __init__(self, arr):
        self._arr = np.asarray(arr, dtype=np.float32)

    @property
    def shape(self):
        return self._arr.shape

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self._arr

    def __getitem__(self, i):
        return _FakeTensor(self._arr[i])


class Receiver:
    """uvicorn on an ephemeral port; nodes take its URL directly."""

    def __init__(self) -> None:
        import uvicorn
        from receiver.app import create_app

        self.cfg = Config(DATA)
        self.app = create_app(self.cfg)
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1",
                                                    port=0, log_level="error"))
        threading.Thread(target=self.server.run, daemon=True).start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)
        assert self.server.started, "receiver never came up"
        self.port = self.server.servers[0].sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.cfg.update({"base_dir": str(ART)})

    def stop(self) -> None:
        self.server.should_exit = True
        time.sleep(0.2)


def _expect_runtime_error(fn, *fragments) -> str:
    try:
        fn()
    except RuntimeError as e:
        for fragment in fragments:
            assert fragment.lower() in str(e).lower(), f"{fragment!r} not in: {e}"
        return str(e)
    raise AssertionError("expected failure did not raise")


# ---- the checks ---------------------------------------------------------------

def test_image_node_saves_batch_with_metadata(rx: Receiver):
    node = save_remote.SaveImageToRemote()
    batch = np.random.default_rng(3).uniform(0, 1, (2, 8, 10, 3))
    out = node.save(_FakeTensor(batch), rx.url, "portraits", "shot_", "flux2",
                    "studio", "a cat", "blurry", 845, format="png")
    paths = out["result"][0].splitlines()
    assert len(paths) == 2, paths
    for p in paths:
        saved = Path(p)
        assert saved.is_file() and saved.name.startswith("shot_") and saved.suffix == ".png", p
        # no sidecar, ever — metadata rides inside the file (owner 2026-09-10)
        assert not saved.with_suffix(".json").exists(), p
    assert len(out["ui"]["text"]) == 2
    hist = requests.get(f"{rx.url}/api/v1/uploads?limit=2").json()["uploads"]
    assert all(row["status"] == "success" for row in hist)


def test_image_node_embeds_prompt_and_workflow(rx: Receiver):
    """Native-parity embedding: the API prompt + the UI workflow ride in the
    PNG's text chunks, nothing scrubbed (owner 2026-09-10)."""
    from PIL import Image
    graph = {"3": {"class_type": "SaveImageToRemote",
                   "inputs": {"receiver_url": save_remote.DEFAULT_RECEIVER_URL,
                              "subfolder": "portraits"}}}
    workflow = {"nodes": [{"id": 3, "widgets_values": ["https://x.trycloudflare.com"]}]}
    node = save_remote.SaveImageToRemote()
    out = node.save(_FakeTensor(np.zeros((1, 4, 4, 3))), rx.url, "", "", "", "", "", "", 0,
                    format="png", prompt=graph, extra_pnginfo={"workflow": workflow})
    saved = Image.open(out["result"][0])
    assert json.loads(saved.text["prompt"]) == graph
    assert json.loads(saved.text["workflow"]) == workflow  # host value rides along, unscrubbed
    plain = node.save(_FakeTensor(np.zeros((1, 4, 4, 3))), rx.url, "", "", "", "", "", "", 0,
                      format="png")
    assert "prompt" not in Image.open(plain["result"][0]).text  # none passed -> none embedded


def test_video_node_streams_and_deletes_after_success(rx: Receiver, tmp: Path):
    src = tmp / "wan_00213.mp4"
    payload = b"\x00\x00\x00\x18ftypmp42" + os.urandom(2048)
    src.write_bytes(payload)
    out = save_remote.SaveVideoToRemote().save(str(src), rx.url, "portraits",
                                               model_name="wan", workflow_name="video",
                                               seed=213, delete_after_success=True)
    saved = Path(out["result"][0])
    assert saved.is_file() and saved.read_bytes() == payload
    assert not src.exists(), "source deleted only AFTER confirmed success"
    assert "source deleted" in out["ui"]["text"][0][3]


def test_failure_is_loud_and_writes_nothing(rx: Receiver, tmp: Path):
    """FAIL LOUD ONLY (owner 2026-09-10): one attempt, immediate error naming
    the URL; no spool, no retry, nothing written here."""
    src = tmp / "wan_keep.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42" + os.urandom(512))
    _expect_runtime_error(
        lambda: save_remote.SaveVideoToRemote().save(str(src), "http://127.0.0.1:9", "",
                                                     timeout=2),
        "http://127.0.0.1:9", "unreachable")
    assert src.exists(), "the pod file is never touched by a failed delivery"


def test_missing_file_is_a_clear_error(rx: Receiver):
    _expect_runtime_error(
        lambda: save_remote.SaveVideoToRemote().save(r"X:\nope.mp4", rx.url, ""),
        "file not found")


def test_extra_metadata_must_be_json(rx: Receiver):
    _expect_runtime_error(
        lambda: save_remote.SaveImageToRemote().save(
            _FakeTensor(np.zeros((1, 4, 4, 3))), rx.url, "", "", "", "", "", "", 0,
            extra_metadata="{oops"),
        "not valid JSON")


def test_config_lives_on_the_node_not_on_disk(rx: Receiver):
    """Widgets carry the config; defaults point at the SSH route; no config file exists."""
    for cls in (save_remote.SaveImageToRemote, save_remote.SaveVideoToRemote):
        spec = cls.INPUT_TYPES()["required"]
        assert "receiver_profile" not in spec and "save_key" not in spec
        assert spec["receiver_url"][1]["default"] == save_remote.DEFAULT_RECEIVER_URL
    assert save_remote.DEFAULT_RECEIVER_URL == "http://127.0.0.1:8790"
    assert not (NODES / "receiver_config.json").exists(), "no sidecar config may exist"
    for gone in ("RETRY_ATTEMPTS", "SPOOL_DIR", "_spool_file", "TRANSIENT_ERRORS"):
        assert not hasattr(save_remote, gone), f"fail-loud-only: {gone} must not exist"


def test_bad_url_is_a_loud_input_error(rx: Receiver):
    for bad in ("", "localhost:8790", "ftp://x", "runpod"):
        try:
            save_remote.check_receiver_url(bad)
        except RuntimeError as e:
            assert "receiver_url" in str(e) and save_remote.DEFAULT_RECEIVER_URL in str(e)
            continue
        raise AssertionError(f"bad url accepted: {bad!r}")


# ---- runner -------------------------------------------------------------------

def main() -> int:
    import json  # noqa: F401  (used by the embedding test above)
    import shutil
    shutil.rmtree(DATA, ignore_errors=True)
    shutil.rmtree(ART, ignore_errors=True)
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DATA / "tmp"
    tmp.mkdir(exist_ok=True)
    rx = Receiver()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t(rx, tmp) if t.__code__.co_argcount > 1 else t(rx)
            print(f"  PASS {t.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL {t.__name__}")
            import traceback
            traceback.print_exc()
    rx.stop()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
