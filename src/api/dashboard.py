"""
Web Dashboard — real-time overview for management.
Accessible at /dashboard
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)
dashboard_router = APIRouter()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>А1 — Панель управления</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            color: #1a1a2e;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 24px 32px;
            border-radius: 12px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 24px; font-weight: 600; }
        .header .status { 
            background: #00c853;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .card h3 {
            font-size: 14px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }
        .card .value {
            font-size: 36px;
            font-weight: 700;
            color: #1a1a2e;
        }
        .card .subtitle {
            font-size: 13px;
            color: #999;
            margin-top: 4px;
        }
        .card.alert { border-left: 4px solid #ff5252; }
        .card.warning { border-left: 4px solid #ffc107; }
        .card.success { border-left: 4px solid #00c853; }
        .card.info { border-left: 4px solid #2196f3; }

        .table-card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 24px;
        }
        .table-card h3 {
            font-size: 16px;
            margin-bottom: 16px;
            color: #1a1a2e;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #f0f0f0;
        }
        th {
            font-size: 12px;
            text-transform: uppercase;
            color: #999;
            font-weight: 600;
        }
        td { font-size: 14px; }
        .badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        .badge-red { background: #ffebee; color: #c62828; }
        .badge-orange { background: #fff3e0; color: #e65100; }
        .badge-yellow { background: #fffde7; color: #f57f17; }
        .badge-green { background: #e8f5e9; color: #2e7d32; }
        .badge-blue { background: #e3f2fd; color: #1565c0; }

        .refresh-note {
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>А1 — Панель управления</h1>
        <div class="status">● Система работает</div>
    </div>

    <div class="grid">
        <div class="card info">
            <h3>Всего задач</h3>
            <div class="value">{total_tasks}</div>
            <div class="subtitle">за все время</div>
        </div>
        <div class="card success">
            <h3>Выполнено</h3>
            <div class="value">{done_tasks}</div>
            <div class="subtitle">закрытые задачи</div>
        </div>
        <div class="card warning">
            <h3>В работе</h3>
            <div class="value">{active_tasks}</div>
            <div class="subtitle">активные задачи</div>
        </div>
        <div class="card alert">
            <h3>Просрочено</h3>
            <div class="value">{overdue_tasks}</div>
            <div class="subtitle">требуют внимания</div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Активные объекты</h3>
            <div class="value">{active_projects}</div>
            <div class="subtitle">строительных площадок</div>
        </div>
        <div class="card">
            <h3>Сотрудников в системе</h3>
            <div class="value">{total_users}</div>
            <div class="subtitle">зарегистрировано</div>
        </div>
        <div class="card">
            <h3>Запросов сегодня</h3>
            <div class="value">{today_requests}</div>
            <div class="subtitle">обработано ботом</div>
        </div>
        <div class="card">
            <h3>Модели AI</h3>
            <div class="value">{ai_models}</div>
            <div class="subtitle">загружено в Ollama</div>
        </div>
    </div>

    <div class="table-card">
        <h3>Последние задачи</h3>
        <table>
            <thead>
                <tr>
                    <th>Задача</th>
                    <th>Тип</th>
                    <th>Приоритет</th>
                    <th>Статус</th>
                    <th>Создана</th>
                </tr>
            </thead>
            <tbody>
                {tasks_rows}
            </tbody>
        </table>
    </div>

    <div class="table-card">
        <h3>Объекты</h3>
        <table>
            <thead>
                <tr>
                    <th>Название</th>
                    <th>Адрес</th>
                    <th>Статус</th>
                </tr>
            </thead>
            <tbody>
                {projects_rows}
            </tbody>
        </table>
    </div>

    <div class="refresh-note">
        Данные обновляются при каждой загрузке страницы. 
        <a href="/dashboard" style="color: #2196f3;">Обновить</a>
    </div>

    <script>
        // Auto-refresh every 60 seconds
        setTimeout(() => location.reload(), 60000);
    </script>
</body>
</html>
"""


@dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Render the management dashboard."""
    # TODO: Pull real data from database
    # For now, show demo data

    # Demo task rows
    tasks_rows = """
        <tr>
            <td>Проверить огнетушители на объекте Михалковская</td>
            <td>🦺 Безопасность</td>
            <td><span class="badge badge-orange">P1</span></td>
            <td><span class="badge badge-blue">В работе</span></td>
            <td>14.08.2026</td>
        </tr>
        <tr>
            <td>Закупка бетона М300 — 50 м³</td>
            <td>📦 Снабжение</td>
            <td><span class="badge badge-yellow">P2</span></td>
            <td><span class="badge badge-green">Новая</span></td>
            <td>14.08.2026</td>
        </tr>
        <tr>
            <td>Продление допуска по электробезопасности</td>
            <td>👥 Кадры</td>
            <td><span class="badge badge-yellow">P2</span></td>
            <td><span class="badge badge-green">Новая</span></td>
            <td>14.08.2026</td>
        </tr>
    """

    # Demo project rows
    projects_rows = """
        <tr><td>Михалковская</td><td>г. Москва, ул. Михалковская</td><td><span class="badge badge-green">Активен</span></td></tr>
        <tr><td>Хорошевское шоссе</td><td>г. Москва, Хорошевское шоссе</td><td><span class="badge badge-green">Активен</span></td></tr>
        <tr><td>Варшавское шоссе</td><td>г. Москва, Варшавское шоссе</td><td><span class="badge badge-green">Активен</span></td></tr>
        <tr><td>Ленинградский проспект</td><td>г. Москва, Ленинградский проспект</td><td><span class="badge badge-green">Активен</span></td></tr>
        <tr><td>Рязанский проспект</td><td>г. Москва, Рязанский проспект</td><td><span class="badge badge-green">Активен</span></td></tr>
    """

    html = DASHBOARD_HTML.format(
        total_tasks=3,
        done_tasks=0,
        active_tasks=2,
        overdue_tasks=0,
        active_projects=5,
        total_users=5,
        today_requests=12,
        ai_models=3,
        tasks_rows=tasks_rows,
        projects_rows=projects_rows,
    )

    return HTMLResponse(content=html)
