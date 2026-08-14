"""
Admin Panel — manage users, projects, departments, routing rules.
Accessible at /admin
Now with real CRUD API connected to PostgreSQL.
"""

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.db.models import User, Department, UserDepartment, Project

logger = logging.getLogger(__name__)
admin_router = APIRouter(prefix="/admin")


# ================================================================
# API MODELS
# ================================================================

class UserCreate(BaseModel):
    full_name: str
    telegram_id: Optional[str] = None
    phone_number: Optional[str] = None
    role: str = "worker"
    department_name: Optional[str] = None
    position: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    telegram_id: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[str] = None
    department_name: Optional[str] = None
    is_active: Optional[bool] = None


class ProjectCreate(BaseModel):
    name: str
    address: Optional[str] = None
    status: str = "active"


# ================================================================
# API ENDPOINTS
# ================================================================

@admin_router.get("/api/users")
async def api_get_users(session: AsyncSession = Depends(get_session)):
    """Get all users with their departments."""
    result = await session.execute(
        select(User).order_by(User.full_name)
    )
    users = result.scalars().all()

    users_list = []
    for u in users:
        # Get department
        dept_result = await session.execute(
            select(Department.name)
            .join(UserDepartment, UserDepartment.department_id == Department.id)
            .where(UserDepartment.user_id == u.id)
        )
        dept_name = dept_result.scalar_one_or_none() or "—"

        users_list.append({
            "id": str(u.id),
            "full_name": u.full_name,
            "telegram_id": u.telegram_id or "—",
            "phone_number": u.phone_number or "—",
            "role": u.role,
            "department": dept_name,
            "is_active": u.is_active,
        })

    return {"users": users_list}


@admin_router.post("/api/users")
async def api_create_user(data: UserCreate, session: AsyncSession = Depends(get_session)):
    """Create a new user."""
    # Generate phone if not provided (required field)
    phone = data.phone_number or f"+7000{str(uuid.uuid4().int)[:7]}"

    user = User(
        full_name=data.full_name,
        telegram_id=data.telegram_id if data.telegram_id else None,
        phone_number=phone,
        role=data.role,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    # Link to department if specified
    if data.department_name:
        dept_result = await session.execute(
            select(Department).where(Department.name == data.department_name)
        )
        dept = dept_result.scalar_one_or_none()
        if dept:
            ud = UserDepartment(user_id=user.id, department_id=dept.id)
            session.add(ud)

    await session.commit()
    return {"status": "ok", "id": str(user.id), "full_name": user.full_name}


@admin_router.put("/api/users/{user_id}")
async def api_update_user(user_id: str, data: UserUpdate, session: AsyncSession = Depends(get_session)):
    """Update an existing user."""
    result = await session.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.telegram_id is not None:
        user.telegram_id = data.telegram_id if data.telegram_id else None
    if data.phone_number is not None:
        user.phone_number = data.phone_number
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    # Update department if specified
    if data.department_name is not None:
        # Remove old department links
        await session.execute(
            delete(UserDepartment).where(UserDepartment.user_id == user.id)
        )
        if data.department_name:
            dept_result = await session.execute(
                select(Department).where(Department.name == data.department_name)
            )
            dept = dept_result.scalar_one_or_none()
            if dept:
                ud = UserDepartment(user_id=user.id, department_id=dept.id)
                session.add(ud)

    await session.commit()
    return {"status": "ok", "id": str(user.id)}


@admin_router.delete("/api/users/{user_id}")
async def api_delete_user(user_id: str, session: AsyncSession = Depends(get_session)):
    """Deactivate a user (soft delete)."""
    result = await session.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    await session.commit()
    return {"status": "ok"}


@admin_router.get("/api/projects")
async def api_get_projects(session: AsyncSession = Depends(get_session)):
    """Get all projects."""
    result = await session.execute(
        select(Project).order_by(Project.name)
    )
    projects = result.scalars().all()
    return {"projects": [
        {
            "id": str(p.id),
            "name": p.name,
            "address": p.address or "—",
            "status": p.status,
        }
        for p in projects
    ]}


@admin_router.post("/api/projects")
async def api_create_project(data: ProjectCreate, session: AsyncSession = Depends(get_session)):
    """Create a new project (construction site)."""
    project = Project(
        name=data.name,
        address=data.address,
        status=data.status,
    )
    session.add(project)
    await session.commit()
    return {"status": "ok", "id": str(project.id), "name": project.name}


@admin_router.get("/api/departments")
async def api_get_departments(session: AsyncSession = Depends(get_session)):
    """Get all departments."""
    result = await session.execute(select(Department))
    departments = result.scalars().all()
    return {"departments": [
        {"id": str(d.id), "name": d.name}
        for d in departments
    ]}


# ================================================================
# ADMIN HTML (SPA with real API calls)
# ================================================================

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>А1 — Админ-панель</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            color: #1a1a2e;
        }}
        .sidebar {{
            position: fixed;
            left: 0; top: 0; bottom: 0;
            width: 240px;
            background: #1a1a2e;
            color: white;
            padding: 24px 0;
            overflow-y: auto;
        }}
        .sidebar h2 {{
            padding: 0 20px;
            font-size: 18px;
            margin-bottom: 24px;
        }}
        .sidebar a {{
            display: block;
            padding: 12px 20px;
            color: #aaa;
            text-decoration: none;
            font-size: 14px;
            transition: all 0.2s;
            cursor: pointer;
        }}
        .sidebar a:hover, .sidebar a.active {{
            background: rgba(255,255,255,0.1);
            color: white;
        }}
        .sidebar a .icon {{ margin-right: 10px; }}
        .main {{
            margin-left: 240px;
            padding: 24px;
        }}
        .page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }}
        .page-header h1 {{ font-size: 24px; }}
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .btn:hover {{ opacity: 0.85; }}
        .btn-primary {{ background: #2196f3; color: white; }}
        .btn-danger {{ background: #f44336; color: white; }}
        .btn-success {{ background: #4caf50; color: white; }}
        .btn-sm {{ padding: 6px 12px; font-size: 12px; }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #f0f0f0;
        }}
        th {{
            font-size: 12px;
            text-transform: uppercase;
            color: #999;
            font-weight: 600;
        }}
        td {{ font-size: 14px; }}
        .badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            display: inline-block;
        }}
        .badge-admin {{ background: #e3f2fd; color: #1565c0; }}
        .badge-manager {{ background: #fff3e0; color: #e65100; }}
        .badge-top_manager {{ background: #fce4ec; color: #c62828; }}
        .badge-worker {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-active {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-inactive {{ background: #fafafa; color: #999; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .modal-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .modal-overlay.show {{ display: flex; }}
        .modal {{
            background: white;
            border-radius: 12px;
            padding: 32px;
            width: 520px;
            max-width: 90%;
            max-height: 90vh;
            overflow-y: auto;
        }}
        .modal h3 {{ margin-bottom: 20px; }}
        .form-group {{
            margin-bottom: 16px;
        }}
        .form-group label {{
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: #666;
            margin-bottom: 6px;
        }}
        .form-group input, .form-group select {{
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }}
        .form-group input:focus, .form-group select:focus {{
            outline: none;
            border-color: #2196f3;
        }}
        .toast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #333;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 2000;
            display: none;
        }}
        .toast.show {{ display: block; }}
        .toast.success {{ background: #4caf50; }}
        .toast.error {{ background: #f44336; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        .stat-card .value {{ font-size: 28px; font-weight: 700; }}
        .stat-card .label {{ font-size: 12px; color: #999; margin-top: 4px; }}
        .loading {{ text-align: center; padding: 40px; color: #999; }}
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>А1 Админ</h2>
        <a class="active" onclick="showTab('users', this)"><span class="icon">👥</span>Сотрудники</a>
        <a onclick="showTab('projects', this)"><span class="icon">🏗</span>Объекты</a>
        <a onclick="showTab('departments', this)"><span class="icon">🏢</span>Отделы</a>
        <a onclick="showTab('system', this)"><span class="icon">⚙️</span>Система</a>
        <a href="/dashboard"><span class="icon">📊</span>Дашборд</a>
    </div>

    <div class="main">
        <div class="stats-grid" id="stats-grid">
            <div class="stat-card"><div class="value" id="stat-users">—</div><div class="label">Сотрудников</div></div>
            <div class="stat-card"><div class="value" id="stat-projects">—</div><div class="label">Объектов</div></div>
            <div class="stat-card"><div class="value" id="stat-departments">—</div><div class="label">Отделов</div></div>
            <div class="stat-card"><div class="value" id="stat-active">—</div><div class="label">Активных</div></div>
        </div>

        <!-- USERS TAB -->
        <div class="tab-content active" id="tab-users">
            <div class="page-header">
                <h1>👥 Сотрудники</h1>
                <button class="btn btn-primary" onclick="openAddUser()">+ Добавить сотрудника</button>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr><th>ФИО</th><th>Роль</th><th>Отдел</th><th>Telegram ID</th><th>Статус</th><th>Действия</th></tr>
                    </thead>
                    <tbody id="users-table">
                        <tr><td colspan="6" class="loading">Загрузка...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- PROJECTS TAB -->
        <div class="tab-content" id="tab-projects">
            <div class="page-header">
                <h1>🏗 Объекты</h1>
                <button class="btn btn-primary" onclick="openAddProject()">+ Добавить объект</button>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr><th>Название</th><th>Адрес</th><th>Статус</th></tr>
                    </thead>
                    <tbody id="projects-table">
                        <tr><td colspan="3" class="loading">Загрузка...</td></tr>
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
                    <thead><tr><th>Название</th></tr></thead>
                    <tbody id="departments-table">
                        <tr><td class="loading">Загрузка...</td></tr>
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
                        <tr><td>Ollama</td><td><span class="badge badge-active">Работает</span></td><td>0.32.9</td></tr>
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
                        <tr><td>llama3.1:8b</td><td>4.9 ГБ</td><td>Router, HR, Снабженец, Аналитик, Сводчик</td></tr>
                        <tr><td>llama3.2-vision:11b</td><td>7.8 ГБ</td><td>Анализ фото ТБ (через mlx-vlm)</td></tr>
                        <tr><td>nomic-embed-text</td><td>0.3 ГБ</td><td>Векторизация (RAG)</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- ADD/EDIT USER MODAL -->
    <div class="modal-overlay" id="modal-user">
        <div class="modal">
            <h3 id="modal-user-title">Добавить сотрудника</h3>
            <input type="hidden" id="edit-user-id" value="">
            <div class="form-group">
                <label>ФИО *</label>
                <input type="text" id="user-name" placeholder="Иванов Иван Иванович">
            </div>
            <div class="form-group">
                <label>Telegram ID</label>
                <input type="text" id="user-tg" placeholder="123456789">
            </div>
            <div class="form-group">
                <label>Телефон</label>
                <input type="text" id="user-phone" placeholder="+79001234567">
            </div>
            <div class="form-group">
                <label>Роль</label>
                <select id="user-role">
                    <option value="worker">Рабочий / Прораб</option>
                    <option value="manager">Руководитель отдела</option>
                    <option value="top_manager">ТОП-менеджмент</option>
                    <option value="admin">Администратор</option>
                </select>
            </div>
            <div class="form-group">
                <label>Отдел</label>
                <select id="user-dept">
                    <option value="">— Не выбран —</option>
                </select>
            </div>
            <div style="display:flex;gap:12px;margin-top:20px;">
                <button class="btn btn-primary" onclick="saveUser()">💾 Сохранить</button>
                <button class="btn" style="background:#eee;" onclick="closeModal('modal-user')">Отмена</button>
            </div>
        </div>
    </div>

    <!-- ADD PROJECT MODAL -->
    <div class="modal-overlay" id="modal-project">
        <div class="modal">
            <h3>Добавить объект</h3>
            <div class="form-group">
                <label>Название *</label>
                <input type="text" id="project-name" placeholder="Михалковская">
            </div>
            <div class="form-group">
                <label>Адрес</label>
                <input type="text" id="project-address" placeholder="г. Москва, ул. Михалковская, д. 1">
            </div>
            <div style="display:flex;gap:12px;margin-top:20px;">
                <button class="btn btn-primary" onclick="saveProject()">💾 Сохранить</button>
                <button class="btn" style="background:#eee;" onclick="closeModal('modal-project')">Отмена</button>
            </div>
        </div>
    </div>

    <!-- TOAST -->
    <div class="toast" id="toast"></div>

    <script>
        // ============ STATE ============
        let departments = [];

        // ============ INIT ============
        document.addEventListener('DOMContentLoaded', () => {{
            loadUsers();
            loadProjects();
            loadDepartments();
        }});

        // ============ TABS ============
        function showTab(name, el) {{
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.sidebar a').forEach(a => a.classList.remove('active'));
            document.getElementById('tab-' + name).classList.add('active');
            if (el) el.classList.add('active');
        }}

        // ============ LOAD DATA ============
        async function loadUsers() {{
            try {{
                const resp = await fetch('/admin/api/users');
                const data = await resp.json();
                renderUsers(data.users);
                document.getElementById('stat-users').textContent = data.users.length;
                document.getElementById('stat-active').textContent = data.users.filter(u => u.is_active).length;
            }} catch(e) {{
                document.getElementById('users-table').innerHTML = '<tr><td colspan="6">Ошибка загрузки</td></tr>';
            }}
        }}

        async function loadProjects() {{
            try {{
                const resp = await fetch('/admin/api/projects');
                const data = await resp.json();
                renderProjects(data.projects);
                document.getElementById('stat-projects').textContent = data.projects.length;
            }} catch(e) {{
                document.getElementById('projects-table').innerHTML = '<tr><td colspan="3">Ошибка загрузки</td></tr>';
            }}
        }}

        async function loadDepartments() {{
            try {{
                const resp = await fetch('/admin/api/departments');
                const data = await resp.json();
                departments = data.departments;
                renderDepartments(departments);
                document.getElementById('stat-departments').textContent = departments.length;
                // Fill department select
                const sel = document.getElementById('user-dept');
                sel.innerHTML = '<option value="">— Не выбран —</option>';
                departments.forEach(d => {{
                    sel.innerHTML += `<option value="${{d.name}}">${{d.name}}</option>`;
                }});
            }} catch(e) {{}}
        }}

        // ============ RENDER ============
        function renderUsers(users) {{
            const tbody = document.getElementById('users-table');
            if (!users.length) {{
                tbody.innerHTML = '<tr><td colspan="6">Нет сотрудников</td></tr>';
                return;
            }}
            tbody.innerHTML = users.map(u => `
                <tr>
                    <td><b>${{u.full_name}}</b></td>
                    <td><span class="badge badge-${{u.role}}">${{roleLabel(u.role)}}</span></td>
                    <td>${{u.department}}</td>
                    <td>${{u.telegram_id}}</td>
                    <td><span class="badge badge-${{u.is_active ? 'active' : 'inactive'}}">${{u.is_active ? 'Активен' : 'Неактивен'}}</span></td>
                    <td>
                        <button class="btn btn-primary btn-sm" onclick="editUser('${{u.id}}', '${{u.full_name}}', '${{u.telegram_id}}', '${{u.phone_number}}', '${{u.role}}', '${{u.department}}')">✏️</button>
                        <button class="btn btn-danger btn-sm" onclick="deactivateUser('${{u.id}}', '${{u.full_name}}')">🗑</button>
                    </td>
                </tr>
            `).join('');
        }}

        function renderProjects(projects) {{
            const tbody = document.getElementById('projects-table');
            if (!projects.length) {{
                tbody.innerHTML = '<tr><td colspan="3">Нет объектов</td></tr>';
                return;
            }}
            tbody.innerHTML = projects.map(p => `
                <tr>
                    <td><b>${{p.name}}</b></td>
                    <td>${{p.address}}</td>
                    <td><span class="badge badge-active">${{p.status}}</span></td>
                </tr>
            `).join('');
        }}

        function renderDepartments(depts) {{
            const tbody = document.getElementById('departments-table');
            tbody.innerHTML = depts.map(d => `<tr><td>${{d.name}}</td></tr>`).join('');
        }}

        function roleLabel(role) {{
            const labels = {{
                'admin': 'Админ',
                'top_manager': 'ТОП',
                'manager': 'Руководитель',
                'worker': 'Сотрудник'
            }};
            return labels[role] || role;
        }}

        // ============ MODALS ============
        function openAddUser() {{
            document.getElementById('modal-user-title').textContent = 'Добавить сотрудника';
            document.getElementById('edit-user-id').value = '';
            document.getElementById('user-name').value = '';
            document.getElementById('user-tg').value = '';
            document.getElementById('user-phone').value = '';
            document.getElementById('user-role').value = 'worker';
            document.getElementById('user-dept').value = '';
            document.getElementById('modal-user').classList.add('show');
        }}

        function editUser(id, name, tg, phone, role, dept) {{
            document.getElementById('modal-user-title').textContent = 'Редактировать сотрудника';
            document.getElementById('edit-user-id').value = id;
            document.getElementById('user-name').value = name;
            document.getElementById('user-tg').value = tg === '—' ? '' : tg;
            document.getElementById('user-phone').value = phone === '—' ? '' : phone;
            document.getElementById('user-role').value = role;
            document.getElementById('user-dept').value = dept === '—' ? '' : dept;
            document.getElementById('modal-user').classList.add('show');
        }}

        function openAddProject() {{
            document.getElementById('project-name').value = '';
            document.getElementById('project-address').value = '';
            document.getElementById('modal-project').classList.add('show');
        }}

        function closeModal(id) {{
            document.getElementById(id).classList.remove('show');
        }}

        // ============ SAVE ============
        async function saveUser() {{
            const id = document.getElementById('edit-user-id').value;
            const name = document.getElementById('user-name').value.trim();
            const tg = document.getElementById('user-tg').value.trim();
            const phone = document.getElementById('user-phone').value.trim();
            const role = document.getElementById('user-role').value;
            const dept = document.getElementById('user-dept').value;

            if (!name) {{
                showToast('Введите ФИО', 'error');
                return;
            }}

            try {{
                let resp;
                if (id) {{
                    // Update
                    resp = await fetch(`/admin/api/users/${{id}}`, {{
                        method: 'PUT',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            full_name: name,
                            telegram_id: tg || null,
                            phone_number: phone || null,
                            role: role,
                            department_name: dept || null,
                        }})
                    }});
                }} else {{
                    // Create
                    resp = await fetch('/admin/api/users', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            full_name: name,
                            telegram_id: tg || null,
                            phone_number: phone || null,
                            role: role,
                            department_name: dept || null,
                        }})
                    }});
                }}

                if (resp.ok) {{
                    showToast(id ? 'Сотрудник обновлён' : 'Сотрудник добавлен', 'success');
                    closeModal('modal-user');
                    loadUsers();
                }} else {{
                    const err = await resp.json();
                    showToast('Ошибка: ' + (err.detail || 'неизвестная'), 'error');
                }}
            }} catch(e) {{
                showToast('Ошибка сети', 'error');
            }}
        }}

        async function saveProject() {{
            const name = document.getElementById('project-name').value.trim();
            const address = document.getElementById('project-address').value.trim();

            if (!name) {{
                showToast('Введите название объекта', 'error');
                return;
            }}

            try {{
                const resp = await fetch('/admin/api/projects', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, address }})
                }});

                if (resp.ok) {{
                    showToast('Объект добавлен', 'success');
                    closeModal('modal-project');
                    loadProjects();
                }} else {{
                    showToast('Ошибка при добавлении', 'error');
                }}
            }} catch(e) {{
                showToast('Ошибка сети', 'error');
            }}
        }}

        async function deactivateUser(id, name) {{
            if (!confirm(`Деактивировать сотрудника "${{name}}"?`)) return;

            try {{
                const resp = await fetch(`/admin/api/users/${{id}}`, {{ method: 'DELETE' }});
                if (resp.ok) {{
                    showToast('Сотрудник деактивирован', 'success');
                    loadUsers();
                }}
            }} catch(e) {{
                showToast('Ошибка', 'error');
            }}
        }}

        // ============ TOAST ============
        function showToast(msg, type) {{
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = 'toast show ' + type;
            setTimeout(() => toast.classList.remove('show'), 3000);
        }}
    </script>
</body>
</html>
"""


@admin_router.get("", response_class=HTMLResponse)
async def get_admin_panel():
    """Serve the admin panel."""
    return HTMLResponse(content=ADMIN_HTML)
