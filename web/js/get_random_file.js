import { api } from '../../../scripts/api.js'
import { app } from '../../../scripts/app.js'
import { $el } from '../../../scripts/ui.js'
import { addStylesheet } from '../../../scripts/utils.js'

addStylesheet('css/styles.css', import.meta.url)

// Preview widget for the random-file + save-anywhere nodes.
//
// ComfyUI flattens every ui[k] across executions:
//   {k: [y for x in uis for y in x[k]]}
// so a LIST OF DICTS (`ui.previews`) is the only shape that survives both
// a batched IMAGE (one execution, N dicts) and a list-wrapped VIDEO
// (N executions, one dict each). Nested path lists inside `ui.text` get
// smashed — that's why a batch of 2 only showed the first file.
//
// All items render in a grid (stock Save Image behaviour), not a 1-up carousel.

function viewUrl(path) {
  return api.apiURL(`/cctech_random_file/view?path=${encodeURIComponent(path)}`)
}

function baseName(p) {
  const parts = String(p).split(/[\\/]/)
  return parts[parts.length - 1] || p
}

function parsePreviewMessage(message) {
  if (Array.isArray(message?.previews) && message.previews.length) {
    return message.previews.filter((p) => p && p.path)
  }
  const text = message?.text
  if (!text || !text.length) return []

  // save-remote / list-of-rows: [["image", path, title, info], ...]
  if (Array.isArray(text[0])) {
    return text
      .map((row) => ({
        kind: row[0],
        path: row[1],
        title: row[2] || baseName(row[1]),
        info: row[3],
      }))
      .filter((p) => p.path)
  }

  // 1.7.1 save-anywhere: 5th element is the path list
  if (Array.isArray(text[4]) && text[4].length) {
    const kind = text[0]
    const info = text[3]
    return text[4].map((path) => ({
      kind,
      path,
      title: baseName(path),
      info,
    }))
  }

  // flattened repeating 4-tuples from N executions of the old 4-tuple schema
  if (
    text.length >= 8 &&
    (text[0] === 'image' || text[0] === 'video') &&
    (text[4] === 'image' || text[4] === 'video')
  ) {
    const items = []
    for (let i = 0; i + 3 < text.length; i += 4) {
      if (text[i] !== 'image' && text[i] !== 'video') break
      items.push({
        kind: text[i],
        path: text[i + 1],
        title: text[i + 2] || baseName(text[i + 1]),
        info: text[i + 3],
      })
    }
    return items.filter((p) => p.path)
  }

  if (text.length >= 4 && text[1]) {
    return [
      {
        kind: text[0],
        path: text[1],
        title: text[2] || baseName(text[1]),
        info: text[3],
      },
    ]
  }
  return []
}

function createMediaPreviewWidget(node) {
  const container = $el('div', {
    style: { width: '100%' },
  })

  const mediaWrapper = $el('div', {
    style: { width: '100%' },
  })

  const placeholder = $el('div', {
    style: { color: '#666', fontSize: '14px', textAlign: 'center' },
    textContent: 'Nothing selected yet - run the workflow',
  })

  const infoText = $el('div', {
    style: {
      color: '#888',
      fontSize: '12px',
      textAlign: 'center',
      marginTop: '6px',
      display: 'none',
    },
  })

  container.appendChild(mediaWrapper)
  container.appendChild(placeholder)
  container.appendChild(infoText)

  let lastCount = 0

  function renderItems(items) {
    lastCount = items.length
    mediaWrapper.replaceChildren()

    if (!items.length) {
      placeholder.style.display = 'block'
      infoText.style.display = 'none'
      return
    }

    placeholder.style.display = 'none'
    const many = items.length > 1
    mediaWrapper.style.display = 'grid'
    mediaWrapper.style.gridTemplateColumns = many
      ? 'repeat(auto-fit, minmax(140px, 1fr))'
      : '1fr'
    mediaWrapper.style.gap = '6px'
    mediaWrapper.style.maxHeight = '560px'
    mediaWrapper.style.overflow = 'auto'

    for (const item of items) {
      const cell = $el('div', { style: { textAlign: 'center', minWidth: 0 } })
      const url = viewUrl(item.path)
      const mediaStyle = {
        maxWidth: '100%',
        maxHeight: many ? '220px' : '360px',
        objectFit: 'contain',
        borderRadius: '4px',
        display: 'block',
        margin: '0 auto',
      }
      if (item.kind === 'video') {
        cell.appendChild(
          $el('video', {
            src: url,
            controls: true,
            muted: true,
            loop: true,
            autoplay: true,
            style: mediaStyle,
          }),
        )
      } else {
        cell.appendChild($el('img', { src: url, style: mediaStyle }))
      }
      cell.appendChild(
        $el('div', {
          textContent: item.title || '',
          style: {
            color: '#aaa',
            fontSize: '12px',
            marginTop: '4px',
            wordBreak: 'break-all',
          },
        }),
      )
      mediaWrapper.appendChild(cell)
    }

    const info = items[0]?.info || ''
    const countNote =
      items.length > 1 && info && !/\d+\s+files?/.test(info)
        ? `${info} • ${items.length} files`
        : info
    infoText.textContent = countNote
    infoText.style.display = countNote ? 'block' : 'none'
  }

  const widget = node.addDOMWidget('mediaPreview', 'custom', container)

  node.updateMediaPreview = function (message) {
    renderItems(parsePreviewMessage(message || {}))
    const size = this.computeSize?.()
    if (size) this.setSize(size)
    this.setDirtyCanvas?.(true, true)
  }

  widget.computeSize = function (width) {
    const n = Math.max(1, lastCount)
    const cols = n === 1 ? 1 : 2
    const rows = Math.ceil(n / cols)
    const rowH = n === 1 ? 300 : 200
    return [width, Math.min(640, 56 + rows * rowH)]
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
        // Pass the whole ui payload so we can read `previews` (and fall back
        // to `text` for the random-file nodes).
        this.updateMediaPreview(message)
      }

      setTimeout(() => this.setSize(this.computeSize()), 10)
      return r
    }
  },
})
