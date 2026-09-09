#!/usr/bin/env python3
"""The save nodes against a LIVE ephemeral receiver (giga-server docs/03
§Verification, R2): real uvicorn on an ephemeral port, real HTTP from
save_remote — the nodes' contract is the wire, so the test rides it.

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
import traceback
from pathlib import Path

import numpy as np

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
    """The slice of torch's surface SaveImageToPC actually uses."""

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
    """uvicorn on an ephemeral port + a node config pointing at it."""

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
        self._profile("portraits", "Portraits", "{model}_{seed}_{timestamp}")
        save_remote.CONFIG_PATH = DATA / "receiver_config.json"
        self.config({"name": "Test PC", "url": self.url,
                     "timeout": 15, "verify_tls": True, "enabled": True})

    def _profile(self, key: str, dest: str, rule: str) -> None:
        import urllib.request
        req = urllib.request.Request(f"{self.url}/api/v1/profiles", method="POST",
                                     data=json.dumps({"save_key": key, "destination": dest,
                                                      "filename_rule": rule}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            assert r.status == 200

    def config(self, receiver: dict) -> None:
        save_remote.CONFIG_PATH.write_text(json.dumps(
            {"receivers": [receiver], "default_receiver": receiver["name"],
             "default_save_key": "portraits"}), encoding="utf-8")

    def reset(self) -> None:
        """Every test starts from the good config — order-independent."""
        self.config({"name": "Test PC", "url": self.url,
                     "timeout": 15, "verify_tls": True, "enabled": True})

    def stop(self) -> None:
        self.server.should_exit = True
        time.sleep(0.2)


# ---- the checks ---------------------------------------------------------------

def test_image_node_saves_batch_with_metadata(rx: Receiver):
    node = save_remote.SaveImageToPC()
    batch = np.random.default_rng(3).uniform(0, 1, (2, 8, 10, 3))
    out = node.save(_FakeTensor(batch), "Test PC", "portraits", "shot_", "flux2",
                    "studio", "a cat", "blurry", 845, format="png")
    paths = out["result"][0].splitlines()
    assert len(paths) == 2, paths
    for p in paths:
        saved = Path(p)
        assert saved.is_file() and saved.name.startswith("flux2_845_") and saved.suffix == ".png"
        sidecar = json.loads(saved.with_suffix(".json").read_text(encoding="utf-8"))
        assert sidecar["prompt"] == "a cat" and str(sidecar["width"]) == "10"
    assert len(out["ui"]["text"]) == 2


def test_video_node_streams_and_deletes_after_success(rx: Receiver, tmp: Path):
    src = tmp / "wan_00213.mp4"
    payload = b"\x00\x00\x00\x18ftypmp42" + os.urandom(2048)
    src.write_bytes(payload)
    out = save_remote.SaveVideoToPC().save(str(src), "Test PC", "portraits",
                                           model_name="wan", workflow_name="video",
                                           seed=213, delete_after_success=True)
    saved = Path(out["result"][0])
    assert saved.is_file() and saved.read_bytes() == payload
    assert not src.exists(), "source deleted only AFTER confirmed success"
    assert "source deleted" in out["ui"]["text"][0][3]


def test_missing_file_is_a_clear_error(rx: Receiver):
    try:
        save_remote.SaveVideoToPC().save(r"X:\nope.mp4", "Test PC", "portraits")
    except RuntimeError as e:
        assert "file not found" in str(e)
        return
    raise AssertionError("missing file did not raise")


def test_unreachable_receiver_names_the_profile(rx: Receiver):
    rx.config({"name": "Ghost PC", "url": "http://127.0.0.1:9",
               "timeout": 2, "verify_tls": True, "enabled": True})
    try:
        save_remote.SaveVideoToPC().save(__file__, "Ghost PC", "portraits")
    except RuntimeError as e:
        assert "Ghost PC" in str(e) and "unreachable" in str(e)
        return
    raise AssertionError("unreachable receiver did not raise")


def test_extra_metadata_must_be_json(rx: Receiver):
    try:
        save_remote.SaveImageToPC().save(_FakeTensor(np.zeros((1, 4, 4, 3))), "Test PC",
                                         "portraits", "", "", "", "", "", 0,
                                         extra_metadata="{oops")
    except RuntimeError as e:
        assert "not valid JSON" in str(e)
        return
    raise AssertionError("bad extra_metadata did not raise")


def test_receiver_names_default_first(rx: Receiver):
    assert save_remote.receiver_names()[0] == "Test PC"


# ---- runner -------------------------------------------------------------------

def main() -> int:
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
        rx.reset()
        try:
            t(rx, tmp) if t.__code__.co_argcount > 1 else t(rx)
            print(f"  PASS {t.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL {t.__name__}")
            traceback.print_exc()
    rx.stop()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
