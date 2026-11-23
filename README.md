# Agent Statusline

Одна строка состояния для Codex CLI и Claude Code. В первой строке видны проект, ветка Git, модель с уровнем рассуждения, занятый контекст и остатки лимитов. В скобках после лимита указано время до сброса. Ниже выводится содержимое `.agent-status` из каталога проекта. Нужны Python 3.10+ и Git для отображения ветки.

```text
[main] example|dev|AST6.2:M  ctx:12%  5h:81%(2h5m) 7d:79%(6d)
Собираю приложение
Проверяю миграцию
```

Каждая непустая строка файла — отдельное сообщение. Через 15 минут после изменения файла сообщения получают отметку ⏸. Рендерер берёт первые четыре сообщения и указывает число остальных. Проверенный Codex CLI 0.171.0 вмещает три строки футера вместе с заголовком. Для полного отображения в нём оставляйте до двух коротких сообщений.

## Своя компоновка

Оба клиента вызывают `render` из `layout.py`. Сегмент — обычная функция, которая принимает `Snapshot` из `core.py` и возвращает текст. Пустая строка скрывает сегмент. `row` соединяет сегменты по горизонтали, `lines` — по вертикали. Например, чтобы показать название клиента перед моделью и проектом, замените содержимое `layout.py`:

```python
from core import Snapshot, agent_status, context, identity, limits, lines, row

def client_name(state: Snapshot) -> str:
    return state.client.upper()

render = lines(row(client_name, identity, context, limits), agent_status)
```

`Snapshot` содержит клиент (`codex` или `claude`), рабочий каталог `cwd`, каталог файла статуса `project_dir`, имя экземпляра `instance`, модель `model`, effort `effort`, процент занятого контекста `context_used` и окна лимитов `limits`. У каждого окна есть подпись `label`, процент расхода `used` и необязательное время сброса `resets_at` в секундах Unix. Компоновка преобразует расход в остаток. Адаптеры отвечают за чтение данных клиента и сокращение имён моделей. После изменения кода перезапустите процесс провайдера Codex.

## Подключение

Из корня репозитория выполните:

```sh
codex features enable tui_extensions_statusline
codex mcp add claude-footer -- "$(command -v python3)" -B -u "$PWD/codex.py"
```

В новой сессии Codex откройте `/statusline` → **Choose a status line provider** → **Claude Code style**. Название сервера `claude-footer` используется в сохранённом выборе провайдера.

Для Claude Code добавьте в `~/.claude/settings.json` поле `statusLine`, подставив абсолютные пути к интерпретатору и файлу:

```json
{
  "statusLine": {
    "type": "command",
    "command": "/path/to/python3 -B /path/to/agent-statusline/claude.py",
    "refreshInterval": 5
  }
}
```
