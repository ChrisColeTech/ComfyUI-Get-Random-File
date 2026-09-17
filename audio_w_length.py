\
from __future__ import annotations

import os
import random
from io import BytesIO

import av
import torch
import folder_paths

try:
    import torchaudio
except ImportError:
    torchaudio = None

CATEGORY = "🤖 CCTech/Files"
OPUS_SAMPLE_RATES = (8000, 12000, 16000, 24000, 48000)


def _validate_audio(audio):
    if audio is None:
        raise ValueError("Audio input is None.")

    if not isinstance(audio, dict):
        raise TypeError("Expected ComfyUI AUDIO input to be a dict.")

    if "waveform" not in audio or "sample_rate" not in audio:
        raise ValueError("AUDIO input must contain 'waveform' and 'sample_rate'.")

    waveform = audio["waveform"]
    sample_rate = int(audio["sample_rate"])

    if not isinstance(waveform, torch.Tensor):
        raise TypeError("audio['waveform'] must be a torch.Tensor.")

    if waveform.ndim < 2:
        raise ValueError(
            f"Unexpected waveform shape {tuple(waveform.shape)}. "
            "Expected [..., channels, samples]."
        )

    if sample_rate <= 0:
        raise ValueError(f"Invalid sample rate: {sample_rate}")

    return waveform, sample_rate


def _audio_length_seconds(audio) -> float:
    waveform, sample_rate = _validate_audio(audio)
    samples = int(waveform.shape[-1])
    return float(samples / sample_rate)


def _next_supported_opus_rate(sample_rate: int) -> int:
    if sample_rate >= 48000:
        return 48000

    for rate in OPUS_SAMPLE_RATES:
        if rate >= sample_rate:
            return rate

    return 48000


def _prepare_waveform_for_format(waveform, original_rate: int, file_format: str):
    sample_rate = original_rate

    if file_format == "opus":
        sample_rate = _next_supported_opus_rate(original_rate)

        if sample_rate != original_rate:
            if torchaudio is None:
                raise RuntimeError(
                    "Saving Opus at this sample rate requires torchaudio for resampling."
                )
            waveform = torchaudio.functional.resample(
                waveform, original_rate, sample_rate
            )

    return waveform, sample_rate


def _encode_audio_bytes(
    waveform: torch.Tensor,
    sample_rate: int,
    file_format: str,
    quality: str,
) -> bytes:
    waveform = waveform.detach().cpu()

    if waveform.ndim != 2:
        raise ValueError(
            f"Expected a single audio item shaped [channels, samples], "
            f"got {tuple(waveform.shape)}."
        )

    channels = int(waveform.shape[0])
    if channels not in (1, 2):
        raise ValueError(
            f"Only mono or stereo audio is currently supported; got {channels} channels."
        )

    waveform, sample_rate = _prepare_waveform_for_format(
        waveform, sample_rate, file_format
    )

    layout = "mono" if waveform.shape[0] == 1 else "stereo"

    output_buffer = BytesIO()
    container = av.open(output_buffer, mode="w", format=file_format)

    if file_format == "flac":
        stream = container.add_stream("flac", rate=sample_rate, layout=layout)

    elif file_format == "mp3":
        stream = container.add_stream("libmp3lame", rate=sample_rate, layout=layout)
        if quality == "V0":
            stream.codec_context.qscale = 1
        elif quality == "128k":
            stream.bit_rate = 128000
        elif quality == "320k":
            stream.bit_rate = 320000
        else:
            raise ValueError(f"Unsupported MP3 quality: {quality}")

    elif file_format == "opus":
        stream = container.add_stream("libopus", rate=sample_rate, layout=layout)
        bitrates = {
            "64k": 64000,
            "96k": 96000,
            "128k": 128000,
            "192k": 192000,
            "320k": 320000,
        }
        if quality not in bitrates:
            raise ValueError(f"Unsupported Opus quality: {quality}")
        stream.bit_rate = bitrates[quality]

    else:
        raise ValueError(f"Unsupported audio format: {file_format}")

    # Mirrors ComfyUI core's audio encoding layout.
    frame_array = (
        waveform.movedim(0, 1)
        .reshape(1, -1)
        .float()
        .numpy()
    )

    frame = av.AudioFrame.from_ndarray(
        frame_array,
        format="flt",
        layout=layout,
    )
    frame.sample_rate = sample_rate
    frame.pts = 0

    for packet in stream.encode(frame):
        container.mux(packet)

    for packet in stream.encode(None):
        container.mux(packet)

    container.close()
    output_buffer.seek(0)
    return output_buffer.read()


def _safe_prefix(prefix: str) -> str:
    prefix = (prefix or "ComfyUI").strip()
    prefix = prefix.replace("\\", "/")
    prefix = prefix.split("/")[-1]
    return prefix or "ComfyUI"


def _next_filename(directory: str, prefix: str, extension: str) -> str:
    os.makedirs(directory, exist_ok=True)

    prefix = _safe_prefix(prefix)
    counter = 1

    while True:
        filename = f"{prefix}_{counter:05d}.{extension}"
        full_path = os.path.join(directory, filename)
        if not os.path.exists(full_path):
            return filename
        counter += 1


def _resolve_save_directory(save_location: str) -> str:
    """
    Empty => ComfyUI/output
    Absolute path => used as-is
    Relative path => resolved beneath ComfyUI/output
    """
    output_root = folder_paths.get_output_directory()
    raw = (save_location or "").strip()

    if not raw:
        directory = output_root
    elif os.path.isabs(os.path.expanduser(raw)):
        directory = os.path.abspath(os.path.expanduser(raw))
    else:
        directory = os.path.abspath(os.path.join(output_root, raw))

    os.makedirs(directory, exist_ok=True)
    return directory


def _save_preview_flac(audio):
    waveform, sample_rate = _validate_audio(audio)

    temp_dir = folder_paths.get_temp_directory()
    os.makedirs(temp_dir, exist_ok=True)

    results = []

    for batch_index, item in enumerate(waveform):
        random_id = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8))
        filename = f"audio_length_preview_{random_id}_{batch_index:03d}.flac"
        full_path = os.path.join(temp_dir, filename)

        encoded = _encode_audio_bytes(
            item,
            sample_rate,
            file_format="flac",
            quality="128k",
        )

        with open(full_path, "wb") as f:
            f.write(encoded)

        results.append(
            {
                "filename": filename,
                "subfolder": "",
                "type": "temp",
            }
        )

    return results


class PreviewAudioWithLength:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
            }
        }

    RETURN_TYPES = ("AUDIO", "FLOAT")
    RETURN_NAMES = ("audio", "length")
    FUNCTION = "preview"
    OUTPUT_NODE = True
    CATEGORY = CATEGORY

    def preview(self, audio):
        length = _audio_length_seconds(audio)
        preview_files = _save_preview_flac(audio)

        return {
            "ui": {"audio": preview_files},
            "result": (audio, length),
        }


class SaveAudioWithLength:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "save_location": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": (
                            "Blank = ComfyUI/output. Relative paths are created under "
                            "ComfyUI/output. Absolute paths are also supported."
                        ),
                    },
                ),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "ComfyUI",
                        "multiline": False,
                    },
                ),
                "format": (
                    ["flac", "mp3", "opus"],
                    {"default": "flac"},
                ),
                "quality": (
                    ["V0", "64k", "96k", "128k", "192k", "320k"],
                    {"default": "128k"},
                ),
            }
        }

    RETURN_TYPES = ("AUDIO", "FLOAT")
    RETURN_NAMES = ("audio", "length")
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = CATEGORY

    def save(
        self,
        audio,
        save_location="",
        filename_prefix="ComfyUI",
        format="flac",
        quality="128k",
    ):
        waveform, sample_rate = _validate_audio(audio)
        length = _audio_length_seconds(audio)
        directory = _resolve_save_directory(save_location)

        # Normalize quality choices to stock ComfyUI-supported settings.
        if format == "mp3" and quality not in ("V0", "128k", "320k"):
            quality = "128k"

        if format == "opus" and quality not in (
            "64k",
            "96k",
            "128k",
            "192k",
            "320k",
        ):
            quality = "128k"

        saved_files = []

        for batch_index, item in enumerate(waveform):
            prefix = filename_prefix
            if waveform.shape[0] > 1:
                prefix = f"{filename_prefix}_{batch_index:03d}"

            filename = _next_filename(directory, prefix, format)
            full_path = os.path.join(directory, filename)

            encoded = _encode_audio_bytes(
                item,
                sample_rate,
                file_format=format,
                quality=quality,
            )

            with open(full_path, "wb") as f:
                f.write(encoded)

            saved_files.append(full_path)

        # Only expose a ComfyUI audio preview when files live under ComfyUI/output.
        output_root = os.path.abspath(folder_paths.get_output_directory())
        ui_audio = []

        for full_path in saved_files:
            absolute = os.path.abspath(full_path)
            try:
                common = os.path.commonpath([output_root, absolute])
            except ValueError:
                common = ""

            if common == output_root:
                rel = os.path.relpath(absolute, output_root)
                subfolder = os.path.dirname(rel)
                filename = os.path.basename(rel)

                ui_audio.append(
                    {
                        "filename": filename,
                        "subfolder": "" if subfolder == "." else subfolder,
                        "type": "output",
                    }
                )

        result = {
            "result": (audio, length),
        }

        if ui_audio:
            result["ui"] = {"audio": ui_audio}

        return result


NODE_CLASS_MAPPINGS = {
    "PreviewAudioWithLength": PreviewAudioWithLength,
    "SaveAudioWithLength": SaveAudioWithLength,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PreviewAudioWithLength": "Preview Audio w/ Length ⚡",
    "SaveAudioWithLength": "Save Audio w/ Length ⚡",
}
