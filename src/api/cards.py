"""
Entity Cards — Mini App pages for objects, employees, tasks.
Accessible at /miniapp/object/<name>, /miniapp/user/<id>
"""

import logging
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.db.models import Project, User, Department, UserDepartment

logger = logging.getLogger(__name__)
cards_router = APIRouter(prefix="/miniapp")


# ================================================================
# OBJECT CARD
# ================================================================

OBJECT_CARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>А1 — {name}</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--tg-theme-bg-color, #ffffff);
            color: var(--tg-theme-text-color, #1a1a2e);
            padding: 16px;
        }}
        .card {{
            background: var(--tg-theme-secondary-bg-color, #f5f5f5);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
        }}
        .card-header .icon {{
            font-size: 32px;
        }}
        .card-header h1 {{
            font-size: 20px;
            font-weight: 700;
        }}
        .card-header .status {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            background: #e8f5e9;
            color: #2e7d32;
        }}
        .field {{
            margin-bottom: 12px;
        }}
        .field .label {{
            font-size: 12px;
            color: var(--tg-theme-hint-color, #999);
            margin-bottom: 4px;
            text-transform: uppercase;
        }}
        .field .value {{
            font-size: 15px;
            font-weight: 500;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 600;
            margin: 20px 0 12px;
            color: var(--tg-theme-hint-color, #666);
        }}
        .empty {{
            text-align: center;
            padding: 40px;
            color: var(--tg-theme-hint-color, #999);
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="icon">🏗</span>
            <h1>{name}</h1>
            <span class="status">{status}</span>
        </div>
        <div class="field">
            <div class="label">Адрес</div>
            <div class="value">{address}</div>
        </div>
        <div class="field">
            <div class="label">Статус</div>
            <div class="value">{status_ru}</div>
        </div>
    </div>

    <div class="section-title">📊 Информация</div>
    <div class="card">
        <div class="field">
            <div class="label">Данные объекта</div>
            <div class="value">Будет доступно после загрузки реальных данных</div>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        tg.BackButton.show();
        tg.BackButton.onClick(() => tg.close());
    </script>
</body>
</html>
"""

OBJECT_NOT_FOUND_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>А1 — Объект не найден</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh; text-align: center;
            background: var(--tg-theme-bg-color, #fff);
            color: var(--tg-theme-text-color, #333);
        }}
        .msg {{ font-size: 16px; }}
    </style>
</head>
<body>
    <div class="msg">🏗 Объект «{name}» не найден в базе данных.</div>
    <script>
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.BackButton.show();
        tg.BackButton.onClick(() => tg.close());
    </script>
</body>
</html>
"""


# ================================================================
# USER CARD
# ================================================================

USER_CARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>А1 — {full_name}</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--tg-theme-bg-color, #ffffff);
            color: var(--tg-theme-text-color, #1a1a2e);
            padding: 16px;
        }}
        .card {{
            background: var(--tg-theme-secondary-bg-color, #f5f5f5);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
        }}
        .card-header .icon {{ font-size: 32px; }}
        .card-header h1 {{ font-size: 20px; font-weight: 700; }}
        .badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            background: #e3f2fd;
            color: #1565c0;
        }}
        .field {{
            margin-bottom: 12px;
        }}
        .field .label {{
            font-size: 12px;
            color: var(--tg-theme-hint-color, #999);
            margin-bottom: 4px;
            text-transform: uppercase;
        }}
        .field .value {{
            font-size: 15px;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="icon">👤</span>
            <h1>{full_name}</h1>
        </div>
        <div class="field">
            <div class="label">Роль</div>
            <div class="value"><span class="badge">{role_ru}</span></div>
        </div>
        <div class="field">
            <div class="label">Отдел</div>
            <div class="value">{department}</div>
        </div>
        <div class="field">
            <div class="label">Telegram</div>
            <div class="value">{telegram_id}</div>
        </div>
        <div class="field">
            <div class="label">Статус</div>
            <div class="value">{status}</div>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        tg.BackButton.show();
        tg.BackButton.onClick(() => tg.close());
    </script>
</body>
</html>
"""


# ================================================================
# ROUTES
# ================================================================

@cards_router.get("/object/{name}", response_class=HTMLResponse)
async def get_object_card(name: str, tg_id: str = "", session: AsyncSession = Depends(get_session)):
    """Show object (project) card. Pass ?tg_id=123 to check role for documents."""
    import json as json_lib
    import os

    # Search by name (case-insensitive)
    result = await session.execute(
        select(Project).where(Project.name.ilike(f"%{name}%"))
    )
    project = result.scalar_one_or_none()

    if not project:
        return HTMLResponse(content=OBJECT_NOT_FOUND_HTML.format(name=name))

    status_map = {"active": "Активен", "completed": "Завершён", "paused": "Приостановлен"}

    # Check user role for document access
    show_documents = False
    if tg_id:
        user_result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        user = user_result.scalar_one_or_none()
        if user and user.role in ('admin', 'top_manager'):
            show_documents = True

    # Get documents for this project
    documents_html = ""
    if show_documents:
        docs = []
        registry_path = "/app/data/loaded_documents.json"
        if os.path.exists(registry_path):
            try:
                with open(registry_path, "r") as f:
                    registry = json_lib.load(f)
                for doc in registry.get("documents", []):
                    if doc.get("project_name", "").lower() in project.name.lower() or \
                       project.name.lower() in doc.get("project_name", "").lower():
                        docs.append(doc)
            except Exception:
                pass

        if docs:
            documents_html = '<div class="section-title">📂 Документы</div><div class="card">'
            for doc in docs:
                cat_icons = {
                    'contract': '📄', 'act': '📋', 'estimate': '💰',
                    'regulation': '📖', 'safety': '🦺', 'other': '📁'
                }
                icon = cat_icons.get(doc.get('category', ''), '📁')
                date = (doc.get('loaded_at', '') or '')[:10]
                documents_html += f'<div class="field"><div class="label">{icon} {doc.get("category", "").upper()} • {date}</div>'
                documents_html += f'<div class="value">{doc.get("title", doc.get("filename", ""))}</div></div>'
            documents_html += '</div>'
        else:
            documents_html = '<div class="section-title">📂 Документы</div><div class="card"><div class="field"><div class="value">Нет загруженных документов</div></div></div>'

    html = OBJECT_CARD_HTML.format(
        name=project.name,
        address=project.address or "Адрес не указан",
        status=project.status,
        status_ru=status_map.get(project.status, project.status),
    )

    # Inject documents section before closing script
    if documents_html:
        html = html.replace('</body>', documents_html + '</body>')

    return HTMLResponse(content=html)


@cards_router.get("/user/{user_id}", response_class=HTMLResponse)
async def get_user_card(user_id: str, session: AsyncSession = Depends(get_session)):
    """Show user profile card."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        # Try to find by telegram_id
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return HTMLResponse(content="<h1>Пользователь не найден</h1>")
    else:
        result = await session.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()

    if not user:
        return HTMLResponse(content="<h1>Пользователь не найден</h1>")

    # Get department
    dept_result = await session.execute(
        select(Department.name)
        .join(UserDepartment, UserDepartment.department_id == Department.id)
        .where(UserDepartment.user_id == user.id)
    )
    dept_name = dept_result.scalar_one_or_none() or "Не назначен"

    role_map = {
        "admin": "Администратор",
        "top_manager": "ТОП-менеджмент",
        "manager": "Руководитель",
        "worker": "Сотрудник",
    }

    html = USER_CARD_HTML.format(
        full_name=user.full_name,
        role_ru=role_map.get(user.role, user.role),
        department=dept_name,
        telegram_id=user.telegram_id or "Не привязан",
        status="✅ Активен" if user.is_active else "❌ Неактивен",
    )
    return HTMLResponse(content=html)
