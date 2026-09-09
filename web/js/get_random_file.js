import { api } from '../../../scripts/api.js'
import { app } from '../../../scripts/app.js'
import { $el } from '../../../scripts/ui.js'
import { addStylesheet } from '../../../scripts/utils.js'

// Add custom styles
addStylesheet('css/styles.css', import.meta.url)

// One preview per node: a single DOM widget holding either a playable
// <video> (VHS-style, streamed from this pack's own view endpoint with
// Range support so seeking works) or an <img>. The backend no longer sends
// ui.images at all, so comfy's built-in canvas preview never draws a second
// copy - that was the old duplication.
//
// ui.text schema from the backend: [kind, path, title, info]
//   kind  - "video" | "image"
//   path  - absolute file path for /cctech_random_file/view
//   title - filename
//   info  - resolution / frames / fps / duration / index line

function createMediaPreviewWidget(node) {
  const container = $el('div', {
    style: { width: '100%', maxHeight: '600px' },
  })

  const mediaWrapper = $el('div', {
    style: { width: '100%', maxHeight: '400px' },
  })

  const videoElement = $el('video', {
    style: {
      maxWidth: '100%',
      objectFit: 'contain',
      borderRadius: '4px',
      display: 'none',
    },
    controls: true,
    muted: true,
    loop: true,
    autoplay: true,
  })

  const imgElement = $el('img', {
    style: {
      maxWidth: '100%',
      objectFit: 'contain',
      borderRadius: '4px',
      display: 'none',
    },
  })

  const placeholder = $el('div', {
    style: { color: '#666', fontSize: '14px', textAlign: 'center' },
    textContent: 'Nothing selected yet - run the workflow',
  })

  const titleText = $el('div', {
    style: {
      color: '#aaa',
      fontSize: '14px',
      fontWeight: 'bold',
      textAlign: 'center',
      marginTop: '8px',
      display: 'none',
    },
  })

  const infoText = $el('div', {
    style: {
      color: '#888',
      fontSize: '12px',
      textAlign: 'center',
      marginTop: '5px',
      display: 'none',
    },
  })

  mediaWrapper.appendChild(videoElement)
  mediaWrapper.appendChild(imgElement)
  container.appendChild(mediaWrapper)
  container.appendChild(placeholder)
  container.appendChild(titleText)
  container.appendChild(infoText)

  const widget = node.addDOMWidget('mediaPreview', 'custom', container)

  node.updateMediaPreview = function (textInfo) {
    if (!textInfo || textInfo.length < 4 || !textInfo[1]) {
      videoElement.style.display = 'none'
      imgElement.style.display = 'none'
      placeholder.style.display = 'block'
      titleText.style.display = 'none'
      infoText.style.display = 'none'
      return
    }
    const [kind, path, title, info] = textInfo
    const url = api.apiURL(
      `/cctech_random_file/view?path=${encodeURIComponent(path)}`,
    )
    placeholder.style.display = 'none'
    if (kind === 'video') {
      imgElement.style.display = 'none'
      videoElement.src = url
      videoElement.style.display = 'block'
    } else {
      videoElement.pause?.()
      videoElement.style.display = 'none'
      imgElement.src = url
      imgElement.style.display = 'block'
    }
    titleText.textContent = title || ''
    titleText.style.display = title ? 'block' : 'none'
    infoText.textContent = info || ''
    infoText.style.display = info ? 'block' : 'none'
  }

  widget.computeSize = function (width) {
    return [width, 240]
  }

  return widget
}

const PREVIEW_NODES = [
  'Random Image Path',
  'Random Video Path',
  'Get Image File By Index',
  'Get Video File By Index',
  'VideoPathLoader',
  'RandomVideoPathLoader',
  'SaveImageToFolder',
  'SaveVideoToFolder',
]

app.registerExtension({
  name: 'CCTech.GetRandomFile.Preview',
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (!PREVIEW_NODES.includes(nodeData.name)) return

    const onNodeCreated = nodeType.prototype.onNodeCreated
    nodeType.prototype.onNodeCreated = async function () {
      const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined
      createMediaPreviewWidget(this)

      const originalOnExecuted = this.onExecuted
      this.onExecuted = function (message) {
        originalOnExecuted?.apply(this, arguments)
        this.updateMediaPreview(message?.text)
      }

      setTimeout(() => this.setSize(this.computeSize()), 10)
      return r
    }
  },
})
