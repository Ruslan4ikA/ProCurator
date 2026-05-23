
# Запусти этот скрипт из папки проекта:
# python patch_settings.py

import re, os

path = os.path.join("templates", "settings.html")
with open(path, "r", encoding="utf-8") as f:
    html = f.read()

# Добавляем новый блок после секции "<!-- РАССЫЛКА -->"
# Ищем место после блока "email_recipients"
new_section = """
      <div class="field">
        <label>Excel-файл получателей (ФИО родителя / ФИО ученика / Почта)</label>
        <div style="display:flex;gap:8px;align-items:center;">
          <input type="text" id="recipients_excel_path"
                 placeholder="D:\\путь\\к\\получатели.xlsx" style="flex:1;">
          <button class="btn-secondary" onclick="browseFile()">📂</button>
          <button class="btn-secondary" onclick="testRecipients()">Проверить</button>
        </div>
        <small style="color:var(--text-dim);font-size:11px;margin-top:4px;display:block;">
          Колонки: <b>ФИО родителя</b> | <b>ФИО ученика</b> | <b>Почта родителя</b>.
          Если файл задан — рассылка идёт по нему (персонально каждому родителю).
          Если не задан — по списку адресов ниже.
        </small>
      </div>"""

# Вставляем перед полем email_recipients
old_marker = '<label>Адреса получателей'
if old_marker in html:
    idx = html.index(old_marker)
    # Находим начало div.field перед этой меткой
    insert_at = html.rfind('<div class="field">', 0, idx)
    html = html[:insert_at] + new_section + "\n      " + html[insert_at:]
    print("✓ Блок Excel-получателей добавлен")
else:
    print("! Метка 'Адреса получателей' не найдена — добавьте блок вручную")

# Добавляем поле в loadSettings
old_load = "portal_login','portal_password','group_id'"
new_load  = "portal_login','portal_password','group_id','recipients_excel_path'"
if old_load in html:
    html = html.replace(old_load, new_load)
    print("✓ recipients_excel_path добавлен в loadSettings")

# Добавляем поле в saveSettings
old_save = "group_id: v('group_id'),"
new_save = "group_id: v('group_id'),\n    recipients_excel_path: v('recipients_excel_path'),"
if old_save in html:
    html = html.replace(old_save, new_save, 1)
    print("✓ recipients_excel_path добавлен в saveSettings")

# Добавляем JS-функцию testRecipients перед закрывающим </script>
test_func = """
async function testRecipients() {
  const path = document.getElementById('recipients_excel_path').value;
  if (!path) { showToast('Укажите путь к Excel-файлу', 'warn'); return; }
  const r = await fetch('/api/test/recipients', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({path})
  });
  const d = await r.json();
  showToast(d.message, d.success ? 'ok' : 'err');
}
"""
if test_func.strip() not in html:
    html = html.replace("</script>", test_func + "\n</script>", 1)
    print("✓ testRecipients() добавлен")

with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print("\nGotovo! Перезапусти приложение.")
