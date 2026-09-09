from .random_file_path import (NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS,
                               register_preview_route)
from .save_remote import (NODE_CLASS_MAPPINGS as _SAVE_MAPPINGS,
                          NODE_DISPLAY_NAME_MAPPINGS as _SAVE_DISPLAY,
                          register_config_routes)
from .save_anywhere import (NODE_CLASS_MAPPINGS as _ANYWHERE_MAPPINGS,
                            NODE_DISPLAY_NAME_MAPPINGS as _ANYWHERE_DISPLAY)
import random

register_preview_route()
register_config_routes()
NODE_CLASS_MAPPINGS.update(_SAVE_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(_SAVE_DISPLAY)
NODE_CLASS_MAPPINGS.update(_ANYWHERE_MAPPINGS)
NODE_DISPLAY_NAME_MAPPINGS.update(_ANYWHERE_DISPLAY)

tech_rambling = [
    "Zap zap zoom!", "Sproing-a-ling!", "Flux capacitor charged!", "Circuit party started!",
    "Electrons dancing!", "Voltage va-va-voom!", "Capacitor doing the cha-cha!", "Resistor raving!"
]

print(f"\033[1;34m[CCTech Suite]: 🤖🤖🤖 \033[96m\033[3m{random.choice(tech_rambling)}\033[0m 🤖🤖🤖")
print(f"\033[1;34m[CCTech Suite]:\033[0m Activated \033[96m{len(NODE_CLASS_MAPPINGS)}\033[0m file nodes.")

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']


WEB_DIRECTORY = "./web"
