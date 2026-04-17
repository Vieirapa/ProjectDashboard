(function () {
  function esc(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function setInlineFeedback(el, message, tone, options) {
    if (!el) return;
    const opts = options || {};
    const safeTone = ['neutral', 'success', 'warning', 'danger'].includes(tone) ? tone : 'neutral';
    const prefix = opts.prefix || 'Status';
    const extraClass = opts.extraClass ? ` ${opts.extraClass}` : '';
    const body = opts.allowHtml ? String(message || 'Sem atualizações no momento.') : esc(message || 'Sem atualizações no momento.');
    el.className = `settings-inline-feedback status-${safeTone}${extraClass}`;
    el.innerHTML = `<strong>${esc(prefix)}</strong><span>${body}</span>`;
  }

  function bindActionDialog(config) {
    const dialog = document.getElementById(config.dialogId);
    const titleEl = document.getElementById(config.titleId);
    const messageEl = document.getElementById(config.messageId);
    const eyebrowEl = document.getElementById(config.eyebrowId);
    const cancelEl = document.getElementById(config.cancelId);
    const confirmEl = document.getElementById(config.confirmId);
    const inputWrapEl = config.inputWrapId ? document.getElementById(config.inputWrapId) : null;
    const inputLabelEl = config.inputLabelId ? document.getElementById(config.inputLabelId) : null;
    const inputEl = config.inputId ? document.getElementById(config.inputId) : null;

    return function askAction(options) {
      const opts = options || {};
      if (!dialog) return Promise.resolve({ confirmed: true, value: String(opts.inputValue || '') });
      if (titleEl) titleEl.textContent = opts.title || 'Confirmar ação';
      if (messageEl) messageEl.innerHTML = opts.message || 'Revise a ação antes de continuar.';
      if (eyebrowEl) eyebrowEl.textContent = opts.eyebrow || 'Confirmação';
      if (cancelEl) cancelEl.textContent = opts.cancelLabel || 'Cancelar';
      if (confirmEl) {
        confirmEl.textContent = opts.confirmLabel || 'Confirmar';
        confirmEl.className = opts.danger ? 'danger' : '';
      }

      const needsInput = !!String(opts.inputLabel || '').trim() && !!inputWrapEl && !!inputEl;
      if (inputWrapEl) inputWrapEl.classList.toggle('hidden', !needsInput);
      if (inputLabelEl) inputLabelEl.textContent = opts.inputLabel || 'Valor';
      if (inputEl) {
        inputEl.type = opts.inputType || 'text';
        inputEl.value = String(opts.inputValue || '');
      }

      return new Promise((resolve) => {
        const cleanup = (payload) => {
          if (confirmEl) confirmEl.onclick = null;
          if (cancelEl) cancelEl.onclick = null;
          if (inputEl) inputEl.onkeydown = null;
          dialog.oncancel = null;
          if (dialog.open) dialog.close();
          resolve(payload);
        };

        if (confirmEl) confirmEl.onclick = () => cleanup({ confirmed: true, value: inputEl ? inputEl.value : '' });
        if (cancelEl) cancelEl.onclick = () => cleanup({ confirmed: false, value: inputEl ? inputEl.value : '' });
        if (inputEl) inputEl.onkeydown = (e) => { if (e.key === 'Enter') { e.preventDefault(); cleanup({ confirmed: true, value: inputEl.value }); } };
        dialog.oncancel = () => cleanup({ confirmed: false, value: inputEl ? inputEl.value : '' });
        dialog.showModal();
        if (needsInput && inputEl) inputEl.focus();
        else if (confirmEl) confirmEl.focus();
      });
    };
  }

  window.ProjectDashboardUI = {
    esc,
    setInlineFeedback,
    bindActionDialog,
  };
})();
