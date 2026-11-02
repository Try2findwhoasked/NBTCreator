// Move the original content, including live statistics and advanced path inputs,
// into a native dialog so sidebar scrolling cannot clip long explanations.
export function initHelpDialogs() {
    const dialog = document.createElement('dialog')
    dialog.id = 'inline-help-dialog'
    dialog.className = 'review-help-dialog'
    dialog.setAttribute('aria-labelledby', 'inline-help-title')
    const header = document.createElement('div')
    header.className = 'review-help-heading'
    const title = document.createElement('h2')
    title.id = 'inline-help-title'
    const close = document.createElement('button')
    close.type = 'button'
    close.textContent = '关闭'
    header.append(title, close)
    dialog.append(header)
    document.body.append(dialog)
    let current
    close.addEventListener('click', () => dialog.close())
    dialog.addEventListener('close', () => {
        if (!current) return
        current.details.append(current.content)
        current.summary.focus({preventScroll: true})
        current = undefined
    })
    for (const details of document.querySelectorAll('.inline-info')) {
        const summary = details.querySelector(':scope > summary')
        const content = details.querySelector(':scope > .info-popover')
        if (!summary || !content) continue
        summary.setAttribute('aria-haspopup', 'dialog')
        summary.setAttribute('aria-controls', dialog.id)
        summary.addEventListener('click', event => {
            event.preventDefault()
            if (dialog.open) return
            current = {details, summary, content}
            title.textContent = summary.getAttribute('aria-label') || '使用说明'
            dialog.append(content)
            dialog.showModal()
            dialog.scrollTop = 0
        })
    }
}
