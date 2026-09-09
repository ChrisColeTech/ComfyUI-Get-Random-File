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
// ui.text schema from the backend: [kind, path, title, info, paths?]
//   kind  - "video" | "image"
//   path  - absolute file path for /cctech_random_file/view
//   title - filename
//   info  - resolution / frames / fps / duration / index line
//   paths - optional: every file of a batch (save nodes) - enables gallery nav

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

  // gallery nav - only drawn when the backend sends a multi-file batch
  const navBar = $el('div', {
    style: {
      display: 'none',
      justifyContent: 'center',
      alignItems: 'center',
      gap: '8px',
      marginTop: '5px',
    },
  })
  const navButtonStyle = {
    background: 'transparent',
    color: '#aaa',
    border: '1px solid #555',
    borderRadius: '4px',
    padding: '2px 12px',
    fontSize: '14px',
    cursor: 'pointer',
    lineHeight: '1.2',
  }
  const prevButton = $el('button', { textContent: '‹', style: navButtonStyle })
  const posText = $el('span', {
    style: { color: '#888', fontSize: '12px', minWidth: '44px', textAlign: 'center' },
  })
  const nextButton = $el('button', { textContent: '›', style: navButtonStyle })
  navBar.appendChild(prevButton)
  navBar.appendChild(posText)
  navBar.appendChild(nextButton)

  mediaWrapper.appendChild(videoElement)
  mediaWrapper.appendChild(imgElement)
  container.appendChild(mediaWrapper)
  container.appendChild(placeholder)
  container.appendChild(titleText)
  container.appendChild(infoText)
  container.appendChild(navBar)

  let gallery = []
  let galleryIndex = 0
  let mediaKind = 'image'

  const baseName = (p) => {
    const parts = String(p).split(/[\\/]/)
    return parts[parts.length - 1] || p
  }

  function showGalleryItem(i) {
    const path = gallery[i]
    const url = api.apiURL(
      `/cctech_random_file/view?path=${encodeURIComponent(path)}`,
    )
    if (mediaKind === 'video') {
      imgElement.style.display = 'none'
      videoElement.src = url
      videoElement.style.display = 'block'
    } else {
      videoElement.pause?.()
      videoElement.style.display = 'none'
      imgElement.src = url
      imgElement.style.display = 'block'
    }
    titleText.textContent = baseName(path)
    titleText.style.display = 'block'
    posText.textContent = `${i + 1} / ${gallery.length}`
    navBar.style.display = gallery.length > 1 ? 'flex' : 'none'
  }

  function shiftGallery(delta) {
    if (!gallery.length) return
    galleryIndex = (galleryIndex + delta + gallery.length) % gallery.length
    showGalleryItem(galleryIndex)
  }
  prevButton.onclick = () => shiftGallery(-1)
  nextButton.onclick = () => shiftGallery(1)

  const widget = node.addDOMWidget('mediaPreview', 'custom', container)

  node.updateMediaPreview = function (textInfo) {
    if (!textInfo || textInfo.length < 4 || !textInfo[1]) {
      videoElement.style.display = 'none'
      imgElement.style.display = 'none'
      navBar.style.display = 'none'
      gallery = []
      placeholder.style.display = 'block'
      titleText.style.display = 'none'
      infoText.style.display = 'none'
      return
    }
    const [kind, path, title, info, allPaths] = textInfo
    mediaKind = kind
    gallery = Array.isArray(allPaths) && allPaths.length ? allPaths : [path]
    galleryIndex = 0
    placeholder.style.display = 'none'
    infoText.textContent = info || ''
    infoText.style.display = info ? 'block' : 'none'
    showGalleryItem(0)
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
