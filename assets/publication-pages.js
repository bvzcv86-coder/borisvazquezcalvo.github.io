'use strict';
document.querySelectorAll('.copy-citation').forEach(button => {
  button.hidden = false;
  button.addEventListener('click', async () => {
    const textarea = document.getElementById(button.dataset.citation);
    const section = button.closest('.citation-section');
    const status = section.querySelector('.copy-status');
    try {
      await navigator.clipboard.writeText(textarea.value);
      status.textContent = 'Citation copied.';
    } catch (_) {
      section.querySelectorAll('.citation-fallback').forEach(element => { element.hidden = false; });
      textarea.focus();
      textarea.select();
      status.textContent = 'Use your keyboard or device menu to copy the selected citation.';
    }
  });
});
document.querySelectorAll('.pdf-preview').forEach(preview => {
  preview.addEventListener('toggle', () => {
    const frame = preview.querySelector('[data-pdf-src]');
    if (!preview.open || !frame || frame.querySelector('iframe')) return;
    const iframe = document.createElement('iframe');
    iframe.title = 'PDF preview: ' + frame.dataset.pdfTitle;
    iframe.src = frame.dataset.pdfSrc + '#view=FitH';
    iframe.loading = 'lazy';
    frame.appendChild(iframe);
  });
});
