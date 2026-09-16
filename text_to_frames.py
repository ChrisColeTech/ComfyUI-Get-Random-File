import math


CATEGORY = "🤖 CCTech/Files"

def _clean_text(text: str) -> str:
    """
    Remove invisible formatting that should not affect the estimate:
    - trailing spaces/tabs on each line
    - leading/trailing whitespace around the whole block

    Internal spaces and line breaks are preserved and still count.
    """
    if not text:
        return ""

    cleaned_lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(cleaned_lines).strip()


class TextToFrames:
    """
    Estimate the number of video frames needed for a block of spoken text.

    Default calibration:
        156 characters = 9 seconds
        25 FPS
        9 seconds * 25 FPS = 225 frames

    This gives:
        17.333333 characters / second
        1.4423077 frames / character at 25 FPS
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
                "fps": (
                    "INT",
                    {
                        "default": 25,
                        "min": 1,
                        "max": 240,
                        "step": 1,
                    },
                ),
                "chars_per_second": (
                    "FLOAT",
                    {
                        "default": 17.333333,
                        "min": 1.0,
                        "max": 100.0,
                        "step": 0.01,
                    },
                ),
                "padding_seconds": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 60.0,
                        "step": 0.1,
                    },
                ),
            }
        }

    RETURN_TYPES = ("INT", "FLOAT", "INT")
    RETURN_NAMES = ("frames", "seconds", "characters")
    FUNCTION = "calculate"
    CATEGORY = CATEGORY

    def calculate(
        self,
        text,
        fps=25,
        chars_per_second=17.333333,
        padding_seconds=0.0,
    ):
        cleaned_text = _clean_text(text)
        character_count = len(cleaned_text)

        if character_count == 0:
            return (0, 0.0, 0)

        speech_seconds = character_count / float(chars_per_second)
        total_seconds = speech_seconds + float(padding_seconds)

        # Always round UP so the generated video is never shorter
        # than the estimated speech duration.
        frames = math.ceil(total_seconds * int(fps))

        return (
            int(frames),
            round(total_seconds, 3),
            int(character_count),
        )


NODE_CLASS_MAPPINGS = {
    "TextToFrames": TextToFrames,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextToFrames": "Text → Frames (Speech Estimate)⚡",
}
