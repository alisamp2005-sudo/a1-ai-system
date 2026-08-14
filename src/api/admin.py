"""
Admin Panel — manage users, projects, departments, routing rules.
Accessible at /admin
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)
admin_router = APIRouter(prefix="/admin")

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>А1 — Админ-панель</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            color: #1a1a2e;
        }
        .sidebar {
            position: fixed;
            left: 0; top: 0; bottom: 0;
            width: 240px;
            background: #1a1a2e;
            color: white;
            padding: 24px 0;
            overflow-y: auto;
        }
        .sidebar h2 {
            padding: 0 20px;
            font-size: 18px;
            margin-bottom: 24px;
        }
        .sidebar a {
            display: block;
            padding: 12px 20px;
            color: #aaa;
            text-decoration: none;
            font-size: 14px;
            transition: all 0.2s;
        }
        .sidebar a:hover, .sidebar a.active {
            background: rgba(255,255,255,0.1);
            color: white;
        }
        .sidebar a .icon { margin-right: 10px; }
        .main {
            margin-left: 240px;
            padding: 24px;
        }
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }
        .page-header h1 { font-size: 24px; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.85; }
        .btn-primary { background: #2196f3; color: white; }
        .btn-danger { background: #f44336; color: white; }
        .btn-success { background: #4caf50; color: white; }
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 24px;
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
        .badge-admin { background: #e3f2fd; color: #1565c0; }
        .badge-manager { background: #fff3e0; color: #e65100; }
        .badge-top { background: #fce4ec; color: #c62828; }
        .badge-worker { background: #e8f5e9; color: #2e7d32; }
        .badge-active { background: #e8f5e9; color: #2e7d32; }
        .badge-inactive { background: #fafafa; color: #999; }
        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 24px;
            background: #e8e8e8;
            padding: 4px;
            border-radius: 10px;
        }
        .tab {
            padding: 10px 20px;
            border: none;
            background: transparent;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
            font-weight: 500;
            color: #666;
        }
        .tab.active {
            background: white;
            color: #1a1a2e;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal {
            background: white;
            border-radius: 12px;
            padding: 32px;
            width: 480px;
            max-width: 90%;
        }
        .modal h3 { margin-bottom: 20px; }
        .form-group {
            margin-bottom: 16px;
        }
        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: #666;
            margin-bottom: 6px;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .stat-card .value { font-size: 28px; font-weight: 700; }
        .stat-card .label { font-size: 12px; color: #999; margin-top: 4px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>⚙️ А1 Админ</h2>
        <a href="#" class="active" onclick="showTab('users')"><span class="icon">👥</span>Пользователи</a>
        <a href="#" onclick="showTab('projects')"><span class="icon">🏗</span>Объекты</a>
        <a href="#" onclick="showTab('departments')"><span class="icon">🏢</span>Отделы</a>
        <a href="#" onclick="showTab('routing')"><span class="icon">🔀</span>Маршрутизация</a>
        <a href="#" onclick="showTab('system')"><span class="icon">⚙️</span>Система</a>
        <a href="/dashboard"><span class="icon">📊</span>Дашборд</a>
    </div>

    <div class="main">
        <div class="stats-grid">
            <div class="stat-card"><div class="value">5</div><div class="label">Пользователей</div></div>
            <div class="stat-card"><div class="value">5</div><div class="label">Объектов</div></div>
            <div class="stat-card"><div class="value">7</div><div class="label">Отделов</div></div>
            <div class="stat-card"><div class="value">8</div><div class="label">Правил маршрутизации</div></div>
        </div>

        <!-- USERS TAB -->
        <div class="tab-content active" id="tab-users">
            <div class="page-header">
                <h1>👥 Пользователи</h1>
                <button class="btn btn-primary" onclick="showModal('add-user')">+ Добавить</button>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr><th>ФИО</th><th>Роль</th><th>Telegram ID</th><th>Статус</th><th>Действия</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><b>Алимов З.Т.</b></td>
                            <td><span class="badge badge-top">top_manager</span></td>
                            <td>—</td>
                            <td><span class="badge badge-active">Активен</span></td>
                            <td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td>
                        </tr>
                        <tr>
                            <td><b>Зиновьева А.</b></td>
                            <td><span class="badge badge-top">top_manager</span></td>
                            <td>—</td>
                            <td><span class="badge badge-active">Активен</span></td>
                            <td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td>
                        </tr>
                        <tr>
                            <td><b>Лыков М.А.</b></td>
                            <td><span class="badge badge-top">top_manager</span></td>
                            <td>—</td>
                            <td><span class="badge badge-active">Активен</span></td>
                            <td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td>
                        </tr>
                        <tr>
                            <td><b>Поляков С.Б.</b></td>
                            <td><span class="badge badge-manager">manager</span></td>
                            <td>—</td>
                            <td><span class="badge badge-active">Активен</span></td>
                            <td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td>
                        </tr>
                        <tr>
                            <td><b>Администратор (Тест)</b></td>
                            <td><span class="badge badge-admin">admin</span></td>
                            <td>5867249984</td>
                            <td><span class="badge badge-active">Активен</span></td>
                            <td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- PROJECTS TAB -->
        <div class="tab-content" id="tab-projects">
            <div class="page-header">
                <h1>🏗 Объекты</h1>
                <button class="btn btn-primary" onclick="showModal('add-project')">+ Добавить</button>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr><th>Название</th><th>Адрес</th><th>Статус</th><th>Действия</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Михалковская</td><td>г. Москва, ул. Михалковская</td><td><span class="badge badge-active">Активен</span></td><td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td></tr>
                        <tr><td>Хорошевское шоссе</td><td>г. Москва, Хорошевское шоссе</td><td><span class="badge badge-active">Активен</span></td><td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td></tr>
                        <tr><td>Варшавское шоссе</td><td>г. Москва, Варшавское шоссе</td><td><span class="badge badge-active">Активен</span></td><td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td></tr>
                        <tr><td>Ленинградский проспект</td><td>г. Москва, Ленинградский проспект</td><td><span class="badge badge-active">Активен</span></td><td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td></tr>
                        <tr><td>Рязанский проспект</td><td>г. Москва, Рязанский проспект</td><td><span class="badge badge-active">Активен</span></td><td><button class="btn btn-primary" style="padding:4px 12px;font-size:12px;">✏️</button></td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- DEPARTMENTS TAB -->
        <div class="tab-content" id="tab-departments">
            <div class="page-header">
                <h1>🏢 Отделы</h1>
            </div>
            <div class="card">
                <table>
                    <thead><tr><th>Отдел</th><th>Руководитель</th><th>Сотрудников</th></tr></thead>
                    <tbody>
                        <tr><td>Руководство</td><td>Алимов З.Т.</td><td>3</td></tr>
                        <tr><td>Служба ТБ</td><td>Поляков С.Б.</td><td>1</td></tr>
                        <tr><td>Производство</td><td>Лыков М.А.</td><td>1</td></tr>
                        <tr><td>Снабжение</td><td>—</td><td>0</td></tr>
                        <tr><td>Финансы</td><td>—</td><td>0</td></tr>
                        <tr><td>Юридический</td><td>—</td><td>0</td></tr>
                        <tr><td>HR</td><td>—</td><td>0</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- ROUTING TAB -->
        <div class="tab-content" id="tab-routing">
            <div class="page-header">
                <h1>🔀 Правила маршрутизации</h1>
            </div>
            <div class="card">
                <table>
                    <thead><tr><th>Тип задачи</th><th>Отдел</th><th>Приоритет</th></tr></thead>
                    <tbody>
                        <tr><td>🦺 Безопасность (ТБ)</td><td>Служба ТБ</td><td>P1</td></tr>
                        <tr><td>📦 Снабжение</td><td>Снабжение</td><td>P2</td></tr>
                        <tr><td>👥 Кадры</td><td>HR</td><td>P2</td></tr>
                        <tr><td>💰 Финансы</td><td>Финансы</td><td>P2</td></tr>
                        <tr><td>📜 Юридический</td><td>Юридический</td><td>P2</td></tr>
                        <tr><td>🏗 Управление проектом</td><td>Производство</td><td>P2</td></tr>
                        <tr><td>📊 Отчетность</td><td>Производство</td><td>P3</td></tr>
                        <tr><td>📌 Общее</td><td>Руководство</td><td>P3</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- SYSTEM TAB -->
        <div class="tab-content" id="tab-system">
            <div class="page-header">
                <h1>⚙️ Система</h1>
            </div>
            <div class="card">
                <h3 style="margin-bottom:16px;">Статус компонентов</h3>
                <table>
                    <thead><tr><th>Компонент</th><th>Статус</th><th>Версия</th></tr></thead>
                    <tbody>
                        <tr><td>PostgreSQL</td><td><span class="badge badge-active">Работает</span></td><td>16</td></tr>
                        <tr><td>Redis</td><td><span class="badge badge-active">Работает</span></td><td>7</td></tr>
                        <tr><td>ChromaDB</td><td><span class="badge badge-active">Работает</span></td><td>0.5</td></tr>
                        <tr><td>Ollama</td><td><span class="badge badge-active">Работает</span></td><td>latest</td></tr>
                        <tr><td>Telegram Bot</td><td><span class="badge badge-active">Работает</span></td><td>aiogram 3.13</td></tr>
                        <tr><td>Celery Worker</td><td><span class="badge badge-active">Работает</span></td><td>5.4</td></tr>
                        <tr><td>Celery Beat (SLA)</td><td><span class="badge badge-active">Работает</span></td><td>5.4</td></tr>
                    </tbody>
                </table>
            </div>
            <div class="card">
                <h3 style="margin-bottom:16px;">AI Модели (Ollama)</h3>
                <table>
                    <thead><tr><th>Модель</th><th>Размер</th><th>Назначение</th></tr></thead>
                    <tbody>
                        <tr><td>qwen2.5:32b</td><td>19 ГБ</td><td>Юрист, Финансист, QA, Секретарь</td></tr>
                        <tr><td>llama3.1:8b</td><td>4.9 ГБ</td><td>Router, SLA, HR, Снабженец, Аналитик, Сводчик</td></tr>
                        <tr><td>nomic-embed-text</td><td>0.3 ГБ</td><td>Векторизация (RAG)</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- ADD USER MODAL -->
    <div class="modal-overlay" id="modal-add-user">
        <div class="modal">
            <h3>Добавить пользователя</h3>
            <div class="form-group"><label>ФИО</label><input type="text" placeholder="Иванов И.И." /></div>
            <div class="form-group"><label>Telegram ID</label><input type="text" placeholder="123456789" /></div>
            <div class="form-group"><label>Роль</label>
                <select>
                    <option value="worker">Рабочий</option>
                    <option value="manager">Руководитель</option>
                    <option value="top_manager">ТОП-менеджмент</option>
                    <option value="admin">Администратор</option>
                </select>
            </div>
            <div class="form-group"><label>Отдел</label>
                <select>
                    <option value="">Выберите...</option>
                    <option>Руководство</option>
                    <option>Служба ТБ</option>
                    <option>Производство</option>
                    <option>Снабжение</option>
                    <option>Финансы</option>
                    <option>Юридический</option>
                    <option>HR</option>
                </select>
            </div>
            <div style="display:flex;gap:12px;margin-top:20px;">
                <button class="btn btn-primary" onclick="hideModal('add-user')">💾 Сохранить</button>
                <button class="btn" style="background:#eee;" onclick="hideModal('add-user')">Отмена</button>
            </div>
        </div>
    </div>

    <script>
        function showTab(name) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.sidebar a').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + name).classList.add('active');
            event.target.closest('a').classList.add('active');
        }
        function showModal(name) {
            document.getElementById('modal-' + name).style.display = 'flex';
        }
        function hideModal(name) {
            document.getElementById('modal-' + name).style.display = 'none';
        }
    </script>
</body>
</html>
"""


@admin_router.get("", response_class=HTMLResponse)
async def get_admin_panel():
    """Serve the admin panel."""
    return HTMLResponse(content=ADMIN_HTML)
