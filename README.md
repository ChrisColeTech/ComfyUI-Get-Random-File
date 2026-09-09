# 🎉 ComfyUI-Get-Random-File 🎉

![Build Status](https://img.shields.io/github/actions/workflow/status/ChrisColeTech/ComfyUI-Get-Random-File/publish_action.yml?branch=main&label=Build%20Status)

Welcome to **ComfyUI-Get-Random-File**! 🚀 This awesome tool brings a touch of randomness to your files and images, making your file management tasks a breeze. Whether you're wor king on a creative project or just want some fun, our tool is here to help you get random files and images effortlessly. Use these nodes for a variety of applications where you need a random file!

## Included Nodes 🌟


- 🎲 **Random File Path**  
  Chooses a random file from a directory and returns the filepath as a STRING. 

- 🖼️ **Get Image File By Index**  
  Retrieves a IMAGE from a specified directory by index and returns both the IMAGE and its filepath as a STRING. 

- 🎲 **Random Image Path**  
  Picks a random IMAGE file from a directory and provides you with the IMAGE and its filepath as a STRING. 

- ⚡ **Save Image to Folder**  
  Saves images to ANY folder on your computer (not just ComfyUI's output directory). Creates the folder if missing, never overwrites (stock-style `_00001_` counter), embeds the workflow metadata in PNGs, and supports the stock `%width%`/`%date`-style prefix variables. 

- ⚡ **Save Video to Folder**  
  Saves a VIDEO input to ANY folder on your computer using ComfyUI's own writer — streams are copied when compatible and re-encoded only when the format/codec/CRF require it. 

## 📝 Prompt Metadata Outputs

Both image nodes (**Random Image Path** and **Get Image File By Index**) also output `positive_prompt` and `negative_prompt` STRINGs extracted from the picked image's embedded ComfyUI workflow metadata — so you can wire the prompts that originally generated an image straight into whatever consumes it. Works with titled prompt nodes, sampler/guider link traversal (including parallel chains, Anything-Everywhere-injected graphs, and combined prep nodes like this family's own img2img nodes that carry `prompt` widgets), CLIPTextEncode/CLIPTextEncodeFlux, the core `TextEncode*` encoders (QwenImageEdit, ZImageOmni, SDXL, SD3, HunyuanDiT, ...), text concatenation and wildcard nodes. Images without embedded prompts (or non-PNG files) simply return empty strings.

## 📸 Preview

🎲 **Random File Path**  
 ![Preview Image](https://github.com/ChrisColeTech/ComfyUI-Get-Random-File/blob/main/img/preview3.jpg)

🎲 **Random Image Path**  
![Preview Image](https://github.com/ChrisColeTech/ComfyUI-Get-Random-File/blob/main/img/preview2.jpg)

🖼️ **Get Video By Index**  
![Preview Image](https://github.com/ChrisColeTech/ComfyUI-Get-Random-File/blob/main/img/preview1.jpg)

📸 **Get Image By Index**  
![Preview Image](https://github.com/ChrisColeTech/ComfyUI-Get-Random-File/blob/main/img/preview4.jpg)

## Installation 🛠️

### Method 1: Clone Repository into `custom_nodes` Folder

1.  **Clone the Repository:**
    
    Open Command Prompt or PowerShell and run the following command to clone the repository into the \`custom\_nodes\` directory of your ComfyUI setup:
    
    `git clone https://github.com/ChrisColeTech/ComfyUI-Get-Random-File.git <path/to/comfyui/custom_nodes>`
    
    Replace `path/to/comfyui` with the actual path to your ComfyUI installation.
    
2.  **Restart ComfyUI:**
    
    Restart your ComfyUI server to load the new node.
    

### Method 2: Install via ComfyUI Manager

1.  **Open ComfyUI Manager:**
    
    Launch the ComfyUI Manager.
    
2.  **Search for** `ComfyUI-Get-Random-File`**:**
    
    In the ComfyUI Manager, go to the **Node Manager** and search for `ComfyUI-Get-Random-File`.
    
3.  **Install the Node:**
    
    Click on the `Install` button next to `ComfyUI-Get-Random-File`. The manager will handle the installation and setup process for you.
    
4.  **Restart ComfyUI:**
    
    After installation, restart your ComfyUI server to ensure that the new node is properly integrated.
