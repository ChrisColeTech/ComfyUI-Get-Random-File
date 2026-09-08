"""Positive/negative prompt extraction from ComfyUI's embedded image metadata.

ComfyUI saves the generating workflow into PNG text chunks; PIL surfaces them
as ``Image.info``. The ``prompt`` chunk holds the API-format graph
(``{"node_id": {"class_type", "inputs", "_meta": {"title"}}}``). The
extraction strategy is a Python port of the one in the
load-image-and-display-prompt-metadata pack (which does the same thing
client-side in JS), in the same priority order:

1. nodes explicitly TITLED "Positive/Negative Prompt" win outright;
2. otherwise the positive/negative inputs of sampler/guider-shaped nodes
   are followed back to their text sources;
3. otherwise CLIPTextEncode-family nodes are scanned and classified by
   title.

One deliberate extension over the reference: it also knows the core
``TextEncode*``/``CLIPTextEncode*`` encoder classes that carry their text in
an input named ``prompt`` (TextEncodeQwenImageEdit, TextEncodeZImageOmni,
CLIPTextEncodeSDXL, ...) rather than ``text`` - verified against the
comfy_extras of a current ComfyUI. Nodes that expose BOTH ``prompt`` and
``negative_prompt`` (TextEncodeBooguEdit, TextEncodeMageFlowEdit) pick the
one matching the conditioning stream being resolved.
"""

import json

from PIL import Image

_POSITIVE_INPUT_KEYS = ("positive", "conditioning_positive", "pos", "guider")
_NEGATIVE_INPUT_KEYS = ("nag_negative", "negative", "conditioning_negative", "neg")
_POSITIVE_TITLES = ("positive prompt", "pos prompt", "prompt")
_NEGATIVE_TITLES = ("negative prompt", "neg prompt")
_PASSTHROUGH_TYPES = (
    "ConditioningSetTimestepRange",
    "ConditioningAverage",
    "ConditioningSetArea",
    "ConditioningSetMask",
    "ChromaPaddingRemoval",
)
_ENCODE_TEXT_KEYS = {
    "CLIPTextEncode": ("text",),
    "CLIPTextEncodePixArtAlpha": ("text",),
    "CLIPTextEncodeSDXLRefiner": ("text",),
    "CLIPTextEncodeFlux": ("clip_l", "t5xxl"),
    "CLIPTextEncodeSD3": ("clip_l", "clip_g", "t5xxl"),
    "CLIPTextEncodeHiDream": ("clip_l", "clip_g", "t5xxl", "llama"),
    "CLIPTextEncodeKandinsky5": ("clip_l", "qwen25_7b"),
    "CLIPTextEncodeSDXL": ("text_g", "text_l"),
    "CLIPTextEncodeHunyuanDiT": ("mt5xl", "bert"),
    "TextEncodeQwenImageEdit": ("prompt",),
    "TextEncodeQwenImageEditPlus": ("prompt",),
    "TextEncodeJoyImageEdit": ("prompt",),
    "TextEncodeZImageOmni": ("prompt",),
    "TextEncodeHunyuanVideo_ImageToVideo": ("prompt",),
    "TextEncodeBooguEdit": ("prompt", "negative_prompt"),
    "TextEncodeMageFlowEdit": ("prompt", "negative_prompt"),
    "PCLazyTextEncode": ("text",),
    "PCLazyTextEncodeAdvanced": ("text",),
}


def _echoed_text(inputs):
    """Text a display/echo node recorded back into indexed widgets, or "".

    ComfyUI display nodes (ShowText, Preview Text, Display Any, ... - every
    pack ships one) take the string on a link and write the *executed* value
    back into ``text_0``/``text_1``/... output widgets, which is how it ends
    up in the saved metadata. Matching on that widget shape rather than on a
    list of class names covers packs this module has never heard of.

    That written-back value is often the ONLY copy of the prompt in the
    graph: when the text comes from a file reader or a wildcard node, the
    upstream inputs hold a path or a template, and following the link
    resolves to nothing.
    """
    indexed = sorted(
        (int(key.partition("_")[2]), key)
        for key in inputs
        if key.startswith("text_") and key.partition("_")[2].isdigit()
    )
    parts = [
        inputs[key] for _, key in indexed
        if isinstance(inputs[key], str) and inputs[key].strip()
    ]
    return "\n".join(parts)


def prompts_from_image_file(path):
    """(positive_prompt, negative_prompt) embedded in an image file's ComfyUI
    metadata; ("", "") when the file has none (or can't be read)."""
    try:
        with Image.open(path) as image:
            raw = image.info.get("prompt")
        if not raw:
            return "", ""
        return extract_prompts(json.loads(raw))
    except Exception:
        return "", ""


def extract_prompts(workflow):
    """(positive, negative) prompt strings from an API-format workflow dict."""
    positive = ""
    negative = ""
    if not isinstance(workflow, dict):
        return positive, negative

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        title = _title_of(node)
        if title in _POSITIVE_TITLES or title in _NEGATIVE_TITLES:
            wants_negative = title in _NEGATIVE_TITLES
            text = _text_from_node_id(node_id, set(), workflow, wants_negative)
            if not text:
                continue
            if wants_negative:
                negative = text
            else:
                positive = text
    if positive and negative:
        return positive, negative

    candidates = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = _inputs_of(node)
        has_pos = any(_is_link(inputs.get(k)) for k in _POSITIVE_INPUT_KEYS)
        has_neg = any(_is_link(inputs.get(k)) for k in _NEGATIVE_INPUT_KEYS)
        if has_pos or has_neg:
            candidates.append((int(has_pos) + int(has_neg), node_id))
    candidates.sort(key=lambda c: c[0], reverse=True)

    pos_tried = set()
    neg_tried = set()
    for _, node_id in candidates:
        inputs = _inputs_of(workflow[node_id])
        if not positive:
            for key in _POSITIVE_INPUT_KEYS:
                if _is_link(inputs.get(key)):
                    source = str(inputs[key][0])
                    pos_tried.add(source)
                    text = _text_from_node_id(source, set(), workflow, False)
                    if text:
                        positive = text
                    break
        if not negative:
            for key in _NEGATIVE_INPUT_KEYS:
                if _is_link(inputs.get(key)):
                    source = str(inputs[key][0])
                    neg_tried.add(source)
                    text = _text_from_node_id(source, set(), workflow, True)
                    if text:
                        negative = text
                    break
        if positive and negative:
            break

    if not positive or not negative:
        for node_id, node in workflow.items():
            if node.get("class_type") not in ("CLIPTextEncode", "CLIPTextEncodeFlux"):
                continue
            text = _inputs_of(node).get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            title = _title_of(node)
            if "negative" in title or "nag" in title:
                if not negative:
                    negative = text
            elif not positive and node_id not in pos_tried and node_id not in neg_tried:
                positive = text

    return positive.strip(), negative.strip()


def _text_from_node_id(node_id, visited, workflow, negative=False):
    if not node_id or str(node_id) in visited:
        return ""
    node_id = str(node_id)
    visited.add(node_id)
    node = workflow.get(node_id)
    if not isinstance(node, dict):
        return ""
    cls = node.get("class_type", "")
    inputs = _inputs_of(node)

    if cls == "BasicGuider":
        if _is_link(inputs.get("conditioning")):
            return _text_from_node_id(inputs["conditioning"][0], visited, workflow,
                                      negative)

    if cls == "ConditioningCombine":
        parts = []
        for key in ("conditioning_1", "conditioning_2"):
            if _is_link(inputs.get(key)):
                text = _text_from_node_id(inputs[key][0], visited, workflow, negative)
                if text:
                    parts.append(text)
        return "\n".join(parts)

    if cls == "ConditioningZeroOut":
        return ""

    if cls in _PASSTHROUGH_TYPES:
        for key in ("conditioning", "conditioning_to"):
            if _is_link(inputs.get(key)):
                return _text_from_node_id(inputs[key][0], visited, workflow, negative)

    if cls in ("Text Concatenate", "StringConcatenate"):
        delimiter = inputs.get("delimiter")
        delimiter = delimiter if isinstance(delimiter, str) else ""
        parts = []
        for key in ("text_a", "text_b", "text_c", "text_d",
                    "string_a", "string_b", "string_c", "string_d"):
            value = inputs.get(key)
            if _is_link(value):
                text = _text_from_node_id(value[0], visited, workflow, negative)
                if text:
                    parts.append(text)
            elif isinstance(value, str) and value.strip():
                # Whitespace-only widget parts (a bare "\n\n" separator box)
                # are spacing, not content - dropping them keeps the joined
                # result from starting/ending with blank lines.
                parts.append(value)
        return delimiter.join(parts)

    if cls in ("StringReplace", "String Replace"):
        # find/replace are configuration, never the prompt - resolve only the
        # subject string, and return "" rather than let the generic scan below
        # mistake the replacement text for the prompt.
        value = inputs.get("string")
        if _is_link(value):
            value = _text_from_node_id(value[0], visited, workflow, negative)
        if not isinstance(value, str) or not value:
            return ""
        find = inputs.get("find")
        replace = inputs.get("replace")
        if isinstance(find, str) and find and isinstance(replace, str):
            value = value.replace(find, replace)
        return value

    if cls == "Text Multiline":
        value = inputs.get("text")
        if _is_link(value):
            return _text_from_node_id(value[0], visited, workflow, negative)
        return value if isinstance(value, str) else ""

    if cls in _ENCODE_TEXT_KEYS:
        keys = _ENCODE_TEXT_KEYS[cls]
        if negative and "negative_prompt" in keys:
            keys = ("negative_prompt",) + tuple(k for k in keys if k != "negative_prompt")
        for key in keys:
            if key in inputs:
                value = inputs.get(key)
                if _is_link(value):
                    return _text_from_node_id(value[0], visited, workflow, negative)
                if isinstance(value, str) and value:
                    return value

    if cls == "ImpactWildcardProcessor":
        for key in ("populated_text", "wildcard_text"):
            value = inputs.get(key)
            if isinstance(value, str) and value:
                return value

    if cls == "String Literal":
        value = inputs.get("string")
        if isinstance(value, str):
            return value

    if cls == "PrimitiveNode":
        values = node.get("widgets_values")
        if (isinstance(values, (list, tuple)) and values
                and isinstance(values[0], str)):
            return values[0]

    echoed = _echoed_text(inputs)
    if echoed:
        return echoed

    for key in (("negative_prompt", "prompt", "text") if negative
                else ("prompt", "text")):
        if key in inputs:
            value = inputs[key]
            if _is_link(value):
                # A link that resolves to nothing (a runtime-only source) is
                # not an answer - keep trying the node's other keys.
                text = _text_from_node_id(value[0], visited, workflow, negative)
                if text:
                    return text
            elif isinstance(value, str):
                return value
    if _is_link(inputs.get("conditioning")):
        return _text_from_node_id(inputs["conditioning"][0], visited, workflow, negative)

    return _text_from_unknown_node(inputs, visited, workflow, negative)


# Keys that never hold prompt text - loader widgets, file pickers, mode
# selectors. A wildcard "any string" scan must skip these or a filename
# like "ComfyUI_00027.png" would leak into the extracted prompt.
_BLOCKED_KEY_SUFFIXES = ("_name", "_path", "_file", "_dir")
_BLOCKED_KEYS = frozenset({
    "image", "video", "audio", "filename", "filename_prefix", "prefix",
    "delimiter", "mode", "type", "format", "extension", "device", "seed",
    "source", "destination", "category", "ckpt_name", "lora_name",
    # Find/replace and template configuration: prose-shaped, but it is the
    # rule applied to a prompt, never the prompt.
    "find", "replace", "search", "pattern", "regex", "separator", "suffix",
    "path", "directory", "directory_path", "folder",
})

# Text-carrying key prefixes, most-explicit first.
_TEXTISH_PREFIXES = ("text", "prompt", "string", "wildcard", "populated", "caption", "description")


def _key_rank(key):
    if key in ("prompt", "text", "negative_prompt"):
        return 0
    if key.startswith(_TEXTISH_PREFIXES):
        return 1
    return 2


def _is_blocked_key(key):
    return key in _BLOCKED_KEYS or key.endswith(_BLOCKED_KEY_SUFFIXES)


def _looks_like_prompt_text(value):
    text = value.strip()
    if len(text) < 12:
        return False
    return " " in text or "\n" in text


def _text_from_unknown_node(inputs, visited, workflow, negative):
    """Generic fallback for node classes this module does not know.

    Any pack can define a display/holder/wildcard/picker node; instead of
    special-casing them, scan the node's inputs: textish-named keys first
    (text*, prompt*, string*, wildcard*, populated*...), following links
    and reading strings; as a last resort take the longest prose-like
    string among unblocked keys (whitespace-containing, >= 12 chars) so
    short mode/filename widgets never win.
    """
    ranked = sorted(inputs.keys(), key=_key_rank)
    for key in ranked:
        if _key_rank(key) == 2 or _is_blocked_key(key):
            continue
        value = inputs.get(key)
        if _is_link(value):
            text = _text_from_node_id(value[0], visited, workflow, negative)
            if text:
                return text
        elif isinstance(value, str) and value.strip():
            return value
    candidates = [
        value for key, value in inputs.items()
        if isinstance(value, str) and not _is_blocked_key(key)
        and _looks_like_prompt_text(value)
    ]
    if candidates:
        return max(candidates, key=len)
    return ""


def _is_link(value):
    return isinstance(value, (list, tuple)) and len(value) == 2


def _inputs_of(node):
    inputs = node.get("inputs")
    return inputs if isinstance(inputs, dict) else {}


def _title_of(node):
    meta = node.get("_meta")
    return str(meta.get("title", "")).strip().lower() if isinstance(meta, dict) else ""
