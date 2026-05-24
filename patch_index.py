"""
Запусти из корня проекта:  python patch_index.py
Добавляет модальное окно подтверждения перед отправкой отчётов.
"""
import os, re

path = os.path.join("templates", "index.html")
with open(path, "r", encoding="utf-8") as f:
    html = f.read()

# ── 1. Добавляем CSS стили модала ─────────────────────────────────────────
modal_css = """
  /* ── Модальное окно подтверждения рассылки ── */
  .modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.55);
    z-index: 1000;
    align-items: center;
    justify-content: center;
  }
  .modal-overlay.open { display: flex; }
  .modal {
    background: var(--bg, #1e1e2e);
    border: 1px solid var(--border, #333);
    border-radius: 12px;
    padding: 28px 32px;
    max-width: 600px;
    width: 95%;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,.5);
  }
  .modal h3 { margin: 0 0 16px; font-size: 17px; color: var(--accent, #7aa2f7); }
  .modal-files { font-size: 12px; color: var(--text-dim, #888); margin-bottom: 14px; }
  .modal-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--border, #333);
    font-size: 13px;
  }
  .modal-row:last-of-type { border-bottom: none; }
  .modal-row .label { color: var(--text-dim, #888); font-size: 11px; margin-bottom: 2px; }
  .modal-row .value { font-weight: 600; }
  .modal-row .files-list { font-size: 11px; color: var(--text-dim, #888); }
  .modal-row .warn  { color: #f7a84a; font-size: 12px; }
  .modal-actions { display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end; }
  .btn-confirm { background: #2ecc71; color: #000; border: none;
                 padding: 9px 22px; border-radius: 8px;
                 font-weight: 700; cursor: pointer; font-size: 14px; }
  .btn-cancel  { background: transparent; color: var(--text, #ccc);
                 border: 1px solid var(--border, #555);
                 padding: 9px 18px; border-radius: 8px; cursor: pointer; font-size: 14px; }
  .btn-confirm:hover { background: #27ae60; }
  .modal-empty { color: #f7768e; text-align: center; padding: 20px 0; }
"""

# Вставляем стили перед закрывающим </style>
if "modal-overlay" not in html:
    html = html.replace("</style>", modal_css + "\n</style>", 1)
    print("✓ CSS модала добавлен")
else:
    print("— CSS модала уже есть")

# ── 2. Добавляем HTML модала перед закрывающим </body> ────────────────────
modal_html = """
<!-- Модальное окно подтверждения рассылки -->
<div class="modal-overlay" id="sendModal">
  <div class="modal">
    <h3>📬 Подтверждение рассылки</h3>
    <div class="modal-files" id="modalFiles"></div>
    <div id="modalRows"></div>
    <div class="modal-actions">
      <button class="btn-cancel"  onclick="closeSendModal()">Отмена</button>
      <button class="btn-confirm" onclick="confirmSend()" id="btnConfirm">✉️ Отправить</button>
    </div>
  </div>
</div>
"""

if "sendModal" not in html:
    html = html.replace("</body>", modal_html + "\n</body>", 1)
    print("✓ HTML модала добавлен")
else:
    print("— HTML модала уже есть")

# ── 3. Добавляем JS функции ────────────────────────────────────────────────
modal_js = """
// ── Модальное окно отправки ──────────────────────────────────────────
async function openSendModal() {
  const res = await fetch('/api/preview_send', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:'{}'});
  const d = await res.json();

  if (!d.success || !d.preview || d.preview.length === 0) {
    showMsg('⚠️ Нет данных для предпросмотра рассылки', 'warn');
    return;
  }

  // Файлы
  document.getElementById('modalFiles').textContent =
    '📎 Файлы: ' + (d.files.length ? d.files.join(', ') : 'нет');

  // Строки получателей
  const container = document.getElementById('modalRows');
  container.innerHTML = '';

  let hasFiles = false;

  d.preview.forEach(item => {
    const row = document.createElement('div');
    row.className = 'modal-row';

    const filesStr = item.files.length
      ? item.files.join(', ')
      : '—';
    if (item.files.length) hasFiles = true;

    row.innerHTML = `
      <div>
        <div class="label">Родитель</div>
        <div class="value">${item.parent}</div>
        <div class="label" style="margin-top:4px">Email</div>
        <div style="font-size:12px">${item.email}</div>
      </div>
      <div>
        <div class="label">Ребёнок</div>
        <div class="value">${item.student || '(все)'}</div>
        <div class="label" style="margin-top:4px">Файл(ы)</div>
        <div class="files-list">${filesStr}</div>
        ${item.warning ? '<div class="warn">' + item.warning + '</div>' : ''}
      </div>`;
    container.appendChild(row);
  });

  // Блокируем кнопку если нет ни одного файла
  document.getElementById('btnConfirm').disabled = !hasFiles;

  document.getElementById('sendModal').classList.add('open');
}

function closeSendModal() {
  document.getElementById('sendModal').classList.remove('open');
}

async function confirmSend() {
  closeSendModal();
  const res = await fetch('/api/send', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:'{}'});
  const d = await res.json();
  showMsg(d.success ? '✅ ' + d.message : '❌ ' + d.message,
          d.success ? 'ok' : 'err');
}
"""

if "openSendModal" not in html:
    html = html.replace("</script>", modal_js + "\n</script>", 1)
    print("✓ JS функции добавлены")
else:
    print("— JS функции уже есть")

# ── 4. Заменяем вызов отправки — кнопка «Отправить» теперь открывает модал
# Ищем onclick который вызывает sendReports / api/send
old_calls = [
    "onclick=\"sendReports()\"",
    "onclick='sendReports()'",
    "onclick=\"fetch('/api/send'",
]
replaced = False
for old in old_calls:
    if old in html:
        html = html.replace(old, "onclick=\"openSendModal()\"", 1)
        print(f"✓ Кнопка отправки → openSendModal()")
        replaced = True
        break

if not replaced:
    print("⚠️  Кнопка 'Отправить' не найдена автоматически.")
    print("   Найди кнопку отправки в index.html и замени её onclick на: openSendModal()")

with open(path, "w", encoding="utf-8") as f:
    f.write(html)

print("\nGotovo! Перезапусти приложение.")