import { api } from '../../../scripts/api.js'
import { app } from '../../../scripts/app.js'
import { $el } from '../../../scripts/ui.js'
import { addStylesheet } from '../../../scripts/utils.js'

// Add custom styles
addStylesheet('css/styles.css', import.meta.url)

// Helper function to create image preview widget
function createImagePreviewWidget(node, nodeName) {
  // Create a wrapper div for our image display
  const container = $el('div', {
    style: {
      width: '100%',
      maxHeight: '600px',
    },
  })

  const imageWrapper = $el('div', {
    style: {
      width: '100%',
      maxHeight: '400px',
    },
  })

  const textWrapper = $el('div', {
    style: {
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
    },
  })

  // Create an img element
  const imgElement = $el('img', {
    style: {
      maxWidth: '100%',
      objectFit: 'contain',
      borderRadius: '4px',
      display: 'none',
    },
  })

  // Create a placeholder text
  const placeholder = $el('div', {
    style: {
      color: '#666',
      fontSize: '14px',
      textAlign: 'center',
    },
    textContent: nodeName === 'Get Video File By Index' ? 'No video selected' : 'No image selected',
  })

  // Create info text for filename
  const filenameText = $el('div', {
    style: {
      color: '#999',
      fontSize: '12px',
      textAlign: 'center',
      marginTop: '5px',
      display: 'none',
    },
  })

  // Create index display
  const indexText = $el('div', {
    style: {
      color: '#aaa',
      fontSize: '14px',
      fontWeight: 'bold',
      textAlign: 'center',
      marginTop: '8px',
      display: 'none',
    },
  })

  // Create extra info display (for video info)
  const extraInfoText = $el('div', {
    style: {
      color: '#888',
      fontSize: '12px',
      textAlign: 'center',
      marginTop: '5px',
      display: 'none',
    },
  })

  imageWrapper.appendChild(imgElement)
  textWrapper.appendChild(placeholder)
  textWrapper.appendChild(filenameText)
  textWrapper.appendChild(indexText)
  textWrapper.appendChild(extraInfoText)

  container.appendChild(imageWrapper)
  container.appendChild(textWrapper)

  // Add the DOM widget to the node
  const widget = node.addDOMWidget('imagePreview', 'custom', container)

  // Store references
  node.imageElement = imgElement
  node.placeholderElement = placeholder
  node.filenameElement = filenameText
  node.indexElement = indexText
  node.extraInfoElement = extraInfoText

  // Function to update the displayed image
  node.updateImage = function (images, textInfo) {
    if (textInfo && textInfo.length > 0) {
      const imageData = images[0]

      imgElement.style.display = 'block'
      placeholder.style.display = 'none'

      // Show text info if available
      if (textInfo && textInfo.length > 0) {
        // First text element is index info
        indexText.textContent = textInfo[0]
        indexText.style.display = 'block'

        // Second text element is video info (if available)
        if (textInfo.length > 1) {
          extraInfoText.textContent = textInfo[1]
          const url = api.apiURL(
            `/view?filename=${encodeURIComponent(textInfo[2])}&type=${
              imageData.type || 'temp'
            }&subfolder=${imageData.subfolder || ''}`,
          )
          imgElement.src = url
          extraInfoText.style.display = 'block'
        }
      }
    } else {
      imgElement.style.display = 'none'
      placeholder.style.display = 'block'
      filenameText.style.display = 'none'
      indexText.style.display = 'none'
      extraInfoText.style.display = 'none'
    }
  }

  // Handle widget height
  widget.computeSize = function (width) {
    return [width, 200]
  }

  return widget
}

// Helper function to hide default image widgets
function hideDefaultImageWidgets(node) {
  // Find all widgets that might display images
  const imageWidgets = node.widgets?.filter((w) => {
    return (
      w.type === 'image' ||
      w.name === 'image' ||
      w.name === 'images' ||
      (w.element && w.element.tagName === 'IMG')
    )
  })

  imageWidgets?.forEach((widget) => {
    widget.type = 'hidden'
    widget.computeSize = () => [0, -4]

    // Hide the widget's DOM element
    if (widget.element) {
      widget.element.style.display = 'none'
    }

    // Hide the wrapper if it exists
    if (widget.wrapper) {
      widget.wrapper.style.display = 'none'
    }

    // Hide parent container if it exists
    if (widget.container) {
      widget.container.style.display = 'none'
    }
  })
}

// Register extension for Get Image File By Index
app.registerExtension({
  name: 'CCTech.GetImageFileByIndex',
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === 'Get Image File By Index') {
      const onNodeCreated = nodeType.prototype.onNodeCreated

      nodeType.prototype.onNodeCreated = async function () {
        const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined

        // Create the preview widget
        const widget = createImagePreviewWidget(this, nodeData.name)

        // Override onExecuted to handle the image display
        const originalOnExecuted = this.onExecuted
        this.onExecuted = function (message) {
          originalOnExecuted?.apply(this, arguments)

          // Debug the message structure
          console.log('Image node message:', message)

          // Check if we have images in the output
          if (message.text.length > 0) {
            this.updateImage(message.images, message.text)
          }
        }

        // Hide default image widgets after a delay
        setTimeout(() => {
          hideDefaultImageWidgets(this)
          this.setSize(this.computeSize())
        }, 10)

        return r
      }

      // Handle serialization/deserialization
      const onConfigure = nodeType.prototype.onConfigure
      nodeType.prototype.onConfigure = function (info) {
        onConfigure?.apply(this, arguments)

        // Re-hide widgets and restore state after loading
        setTimeout(() => {
          hideDefaultImageWidgets(this)

          if (this.imgs && this.imgs.length > 0) {
            const img = this.imgs[0]
            if (img && img.src) {
              this.imageElement.src = img.src
              this.imageElement.style.display = 'block'
              this.placeholderElement.style.display = 'none'
            }
          }
        }, 100)
      }
    }
  },
})

app.registerExtension({
  name: 'CCTech.RandomImagePath',
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === 'Random Image Path') {
      const onNodeCreated = nodeType.prototype.onNodeCreated

      nodeType.prototype.onNodeCreated = async function () {
        const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined

        // Create the preview widget
        const widget = createImagePreviewWidget(this, nodeData.name)

        // Override onExecuted to handle the image display
        const originalOnExecuted = this.onExecuted
        this.onExecuted = function (message) {
          originalOnExecuted?.apply(this, arguments)

          // Debug the message structure
          console.log('Image node message:', message)

          // Check if we have images in the output
          if (message.text.length > 0) {
            this.updateImage(message.images, message.text)
          }
        }

        // Hide default image widgets after a delay
        setTimeout(() => {
          hideDefaultImageWidgets(this)
          this.setSize(this.computeSize())
        }, 10)

        return r
      }

      // Handle serialization/deserialization
      const onConfigure = nodeType.prototype.onConfigure
      nodeType.prototype.onConfigure = function (info) {
        onConfigure?.apply(this, arguments)

        // Re-hide widgets and restore state after loading
        setTimeout(() => {
          hideDefaultImageWidgets(this)

          if (this.imgs && this.imgs.length > 0) {
            const img = this.imgs[0]
            if (img && img.src) {
              this.imageElement.src = img.src
              this.imageElement.style.display = 'block'
              this.placeholderElement.style.display = 'none'
            }
          }
        }, 100)
      }
    }
  },
})

// Register extension for Get Video File By Index
app.registerExtension({
  name: 'CCTech.GetVideoFileByIndex',
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === 'Get Video File By Index') {
      const onNodeCreated = nodeType.prototype.onNodeCreated

      nodeType.prototype.onNodeCreated = async function () {
        const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined

        // Create the preview widget
        const widget = createImagePreviewWidget(this, nodeData.name)

        // Override onExecuted to handle the video preview display
        const originalOnExecuted = this.onExecuted
        this.onExecuted = function (message) {
          originalOnExecuted?.apply(this, arguments)

          // Debug the message structure
          console.log('Video node message:', message)

          // Check if we have images in the output
          if (message.text.length > 0) {
            this.updateImage(message.images, message.text)
          }
        }

        // Hide default image widgets after a delay
        setTimeout(() => {
          hideDefaultImageWidgets(this)
          this.setSize(this.computeSize())
        }, 10)

        return r
      }

      // Handle serialization/deserialization
      const onConfigure = nodeType.prototype.onConfigure
      nodeType.prototype.onConfigure = function (info) {
        onConfigure?.apply(this, arguments)

        // Re-hide widgets after loading
        setTimeout(() => {
          hideDefaultImageWidgets(this)
        }, 100)
      }
    }
  },
})

app.registerExtension({
  name: 'CCTech.RandomVideoPath',
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === 'Random Video Path') {
      const onNodeCreated = nodeType.prototype.onNodeCreated

      nodeType.prototype.onNodeCreated = async function () {
        const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined

        // Create the preview widget
        const widget = createImagePreviewWidget(this, nodeData.name)

        // Override onExecuted to handle the video preview display
        const originalOnExecuted = this.onExecuted
        this.onExecuted = function (message) {
          originalOnExecuted?.apply(this, arguments)

          // Debug the message structure
          console.log('Video node message:', message)

          // Check if we have images in the output
          if (message.text.length > 0) {
            this.updateImage(message.images, message.text)
          }
        }

        // Hide default image widgets after a delay
        setTimeout(() => {
          hideDefaultImageWidgets(this)
          this.setSize(this.computeSize())
        }, 10)

        return r
      }

      // Handle serialization/deserialization
      const onConfigure = nodeType.prototype.onConfigure
      nodeType.prototype.onConfigure = function (info) {
        onConfigure?.apply(this, arguments)

        // Re-hide widgets after loading
        setTimeout(() => {
          hideDefaultImageWidgets(this)
        }, 100)
      }
    }
  },
})
