from .random_file_path import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
import random

tech_rambling = [
    "Zap zap zoom!", "Sproing-a-ling!", "Flux capacitor charged!", "Circuit party started!",
    "Electrons dancing!", "Voltage va-va-voom!", "Capacitor doing the cha-cha!", "Resistor raving!"
]

print(f"\033[1;34m[CCTech Suite]: 🤖🤖🤖 \033[96m\033[3m{random.choice(tech_rambling)}\033[0m 🤖🤖🤖")
print(f"\033[1;34m[CCTech Suite]:\033[0m Activated \033[96m{len(NODE_CLASS_MAPPINGS)}\033[0m file nodes.")

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']


WEB_DIRECTORY = "./web"
