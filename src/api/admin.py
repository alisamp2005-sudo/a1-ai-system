"""
Admin Panel — manage users, projects, departments, routing rules.
Accessible at /admin
Protected by login/password authentication.
"""

import logging
import uuid
import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.db.models import User, Department, UserDepartment, Project
from src.services.document_storage import save_original

logger = logging.getLogger(__name__)
admin_router = APIRouter(prefix="/admin")

# ================================================================
# ADMIN CREDENTIALS (stored in memory, first admin created on startup)
# In production, these should be in DB
# ================================================================
ADMIN_USERS = {
    "admin": {
        "password_hash": hashlib.sha256("A1admin2026!".encode()).hexdigest(),
        "role": "superadmin",
        "name": "Администратор",
    }
}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def check_auth(request: Request) -> bool:
    """Check if user is authenticated via session."""
    return request.session.get("admin_authenticated", False)


# ================================================================
# API MODELS
# ================================================================

class UserCreate(BaseModel):
    full_name: str
    telegram_id: Optional[str] = None
    telegram_username: Optional[str] = None
    phone_number: Optional[str] = None
    role: str = "worker"
    department_name: Optional[str] = None
    position: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    telegram_id: Optional[str] = None
    telegram_username: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[str] = None
    department_name: Optional[str] = None
    is_active: Optional[bool] = None


class ProjectCreate(BaseModel):
    name: str
    address: Optional[str] = None
    status: str = "active"


class AdminUserCreate(BaseModel):
    username: str
    password: str
    name: str
    role: str = "admin"


class LoginData(BaseModel):
    username: str
    password: str


# ================================================================
# AUTH ENDPOINTS
# ================================================================

@admin_router.post("/api/login")
async def api_login(data: LoginData, request: Request):
    """Login to admin panel."""
    user = ADMIN_USERS.get(data.username)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    request.session["admin_authenticated"] = True
    request.session["admin_username"] = data.username
    request.session["admin_name"] = user["name"]
    return {"status": "ok", "name": user["name"]}


@admin_router.post("/api/logout")
async def api_logout(request: Request):
    """Logout from admin panel."""
    request.session.clear()
    return {"status": "ok"}


@admin_router.post("/api/admin-users")
async def api_create_admin_user(data: AdminUserCreate, request: Request):
    """Create a new admin panel user (only superadmin can do this)."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    current_user = ADMIN_USERS.get(request.session.get("admin_username"))
    if not current_user or current_user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Только суперадмин может создавать пользователей панели")

    if data.username in ADMIN_USERS:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    ADMIN_USERS[data.username] = {
        "password_hash": hash_password(data.password),
        "role": data.role,
        "name": data.name,
    }
    return {"status": "ok", "username": data.username}


@admin_router.get("/api/admin-users")
async def api_list_admin_users(request: Request):
    """List admin panel users."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {"users": [
        {"username": k, "name": v["name"], "role": v["role"]}
        for k, v in ADMIN_USERS.items()
    ]}


# ================================================================
# PROTECTED API ENDPOINTS
# ================================================================

@admin_router.get("/api/users")
async def api_get_users(request: Request, session: AsyncSession = Depends(get_session)):
    """Get all users with their departments."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await session.execute(
        select(User).order_by(User.full_name)
    )
    users = result.scalars().all()

    users_list = []
    for u in users:
        dept_result = await session.execute(
            select(Department.name)
            .join(UserDepartment, UserDepartment.department_id == Department.id)
            .where(UserDepartment.user_id == u.id)
        )
        dept_name = dept_result.scalar_one_or_none() or "—"

        users_list.append({
            "id": str(u.id),
            "full_name": u.full_name,
            "telegram_id": u.telegram_id or "",
            "telegram_username": getattr(u, 'telegram_username', '') or "",
            "phone_number": u.phone_number or "",
            "role": u.role,
            "department": dept_name,
            "is_active": u.is_active,
        })

    return {"users": users_list}


@admin_router.post("/api/users")
async def api_create_user(data: UserCreate, request: Request, session: AsyncSession = Depends(get_session)):
    """Create a new user."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    phone = data.phone_number or f"+7000{str(uuid.uuid4().int)[:7]}"

    user = User(
        full_name=data.full_name,
        telegram_id=data.telegram_id if data.telegram_id else None,
        telegram_username=data.telegram_username if hasattr(data, 'telegram_username') and data.telegram_username else None,
        phone_number=phone,
        role=data.role,
        is_active=True,
    )
    session.add(user)
    await session.flush()

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
async def api_update_user(user_id: str, data: UserUpdate, request: Request, session: AsyncSession = Depends(get_session)):
    """Update an existing user."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

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
    if hasattr(data, 'telegram_username') and data.telegram_username is not None:
        user.telegram_username = data.telegram_username if data.telegram_username else None
    if data.phone_number is not None:
        user.phone_number = data.phone_number
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    if data.department_name is not None:
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
async def api_delete_user(user_id: str, request: Request, session: AsyncSession = Depends(get_session)):
    """Deactivate a user (soft delete)."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

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
async def api_get_projects(request: Request, session: AsyncSession = Depends(get_session)):
    """Get all projects."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

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
async def api_create_project(data: ProjectCreate, request: Request, session: AsyncSession = Depends(get_session)):
    """Create a new project."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    project = Project(
        name=data.name,
        address=data.address,
        status=data.status,
    )
    session.add(project)
    await session.commit()
    return {"status": "ok", "id": str(project.id), "name": project.name}


@admin_router.put("/api/projects/{project_id}")
async def api_update_project(project_id: str, request: Request, session: AsyncSession = Depends(get_session)):
    """Update project status."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    import json as json_lib
    body = await request.body()
    data = json_lib.loads(body)

    result = await session.execute(select(Project).where(Project.id == int(project_id)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if "status" in data:
        project.status = data["status"]
    if "name" in data:
        project.name = data["name"]
    if "address" in data:
        project.address = data["address"]

    await session.commit()
    return {"status": "ok", "id": str(project.id), "name": project.name}


@admin_router.get("/api/rag-documents")
async def api_get_rag_documents(request: Request):
    """Get list of loaded RAG documents."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    import os
    registry_path = "/app/data/loaded_documents.json"
    if os.path.exists(registry_path):
        import json as json_lib
        with open(registry_path, "r") as f:
            registry = json_lib.load(f)
        return {"documents": registry.get("documents", [])}
    return {"documents": []}


@admin_router.post("/api/upload-document")
async def api_upload_document(request: Request):
    """Upload a document to RAG from admin panel."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    import os
    import json as json_lib
    import tempfile
    import hashlib
    from src.services.document_processor import extract_text
    from src.services.rag_service import rag_service

    form = await request.form()
    file = form.get("file")
    category = form.get("category", "other")
    department = form.get("department", "")
    project_name = form.get("project_name", "")
    comment = form.get("comment", "")

    if not file:
        return {"status": "error", "error": "Файл не выбран"}

    # Read once, then reject an already indexed copy before costly extraction/embedding.
    content = await file.read()
    ext = os.path.splitext(file.filename)[1].lower()
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    registry_path = "/app/data/loaded_documents.json"
    try:
        if os.path.exists(registry_path):
            with open(registry_path, "r") as f:
                registry = json_lib.load(f)
        else:
            registry = {"documents": []}
    except Exception:
        registry = {"documents": []}

    duplicate = next(
        (item for item in registry.get("documents", [])
         if item.get("content_hash") == content_hash),
        None,
    )
    if duplicate:
        return {
            "status": "error",
            "error": f"Документ уже загружен: {duplicate.get('title', file.filename)}",
        }

    storage_path = save_original(content, file.filename, content_hash)
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Extract text
        text = await extract_text(tmp_path)
        if isinstance(text, tuple):
            text = text[0] if text else ""
        os.unlink(tmp_path)

        if not text or len(text.strip()) < 20:
            if os.path.exists(storage_path):
                os.unlink(storage_path)
            return {"status": "error", "error": "Не удалось извлечь текст из файла"}

        # Load into RAG
        title = os.path.splitext(file.filename)[0]
        if comment:
            title = f"{title} ({comment})"

        chunks_count = rag_service.add_text_document(
            text=text,
            category=category,
            title=title,
            source=f"admin:{file.filename}",
            project_name=project_name,
            department=department,
            comment=comment,
        )
        if chunks_count == 0:
            return {"status": "error", "error": "Не удалось загрузить документ в базу знаний"}

        # Register in the document registry loaded before text extraction.
        from datetime import datetime
        registry["documents"].append({
            "document_id": content_hash,
            "filename": file.filename,
            "title": title,
            "category": category,
            "content_hash": content_hash,
            "chunks": chunks_count,
            "project_name": project_name,
            "department": department,
            "comment": comment,
            "storage_path": storage_path,
            "rag_source": f"admin:{file.filename}",
            "source": "admin",
            "loaded_at": datetime.now().isoformat(),
            "loaded_by": "Админ",
        })

        os.makedirs(os.path.dirname(registry_path), exist_ok=True)
        with open(registry_path, "w") as f:
            json_lib.dump(registry, f, ensure_ascii=False, indent=2)

        return {"status": "ok", "chunks": chunks_count, "title": title}

    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if 'storage_path' in locals() and os.path.exists(storage_path):
            os.unlink(storage_path)
        return {"status": "error", "error": str(e)}


@admin_router.get("/api/reports")
async def api_get_reports(request: Request, session: AsyncSession = Depends(get_session)):
    """Get daily reports with optional filters."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    from src.db.models import DailyReport
    query = select(DailyReport).order_by(DailyReport.report_date.desc())

    # Apply filters from query params
    params = request.query_params
    if params.get("project"):
        query = query.where(DailyReport.project_name == params["project"])
    if params.get("status"):
        query = query.where(DailyReport.status == params["status"])
    if params.get("date"):
        from datetime import date as date_type
        try:
            filter_date = date_type.fromisoformat(params["date"])
            query = query.where(DailyReport.report_date == filter_date)
        except ValueError:
            pass

    result = await session.execute(query.limit(200))
    reports = result.scalars().all()

    return {"reports": [
        {
            "id": str(r.id),
            "date": str(r.report_date) if r.report_date else "",
            "project_name": r.project_name or "",
            "author_name": r.author_name or "",
            "work_done": r.work_done or "",
            "problems": r.problems or "",
            "workers_count": r.workers_count,
            "status": r.status or "new",
            "created_at": str(r.created_at) if r.created_at else "",
        }
        for r in reports
    ]}


@admin_router.get("/api/departments")
async def api_get_departments(request: Request, session: AsyncSession = Depends(get_session)):
    """Get all departments."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await session.execute(select(Department))
    departments = result.scalars().all()
    return {"departments": [
        {"id": str(d.id), "name": d.name}
        for d in departments
    ]}


# ================================================================
# LOGIN PAGE HTML
# ================================================================

LOGIN_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>А1 — Вход в админ-панель</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-card {
            background: white;
            border-radius: 16px;
            padding: 48px 40px;
            width: 400px;
            max-width: 90%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .login-card h1 {
            font-size: 24px;
            margin-bottom: 8px;
            color: #1a1a2e;
        }
        .login-card p {
            color: #666;
            font-size: 14px;
            margin-bottom: 32px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            color: #333;
            margin-bottom: 8px;
        }
        .form-group input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 15px;
            transition: border-color 0.2s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #2196f3;
        }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: #2196f3;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .btn-login:hover { background: #1976d2; }
        .error-msg {
            color: #f44336;
            font-size: 13px;
            margin-top: 12px;
            display: none;
        }
        .error-msg.show { display: block; }
    </style>
</head>
<body>
    <div class="login-card">
        <h1>А1 Админ-панель</h1>
        <p>Введите логин и пароль для входа</p>
        <div class="form-group">
            <label>Логин</label>
            <input type="text" id="login-username" value="admin" autofocus>
        </div>
        <div class="form-group">
            <label>Пароль</label>
            <input type="password" id="login-password" placeholder="Пароль">
        </div>
        <button class="btn-login" onclick="doLogin()">Войти</button>
        <div class="error-msg" id="error-msg">Неверный логин или пароль</div>
    </div>
    <script>
        document.getElementById('login-password').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') doLogin();
        });
        document.getElementById('login-username').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') document.getElementById('login-password').focus();
        });

        async function doLogin() {
            const username = document.getElementById('login-username').value.trim();
            const password = document.getElementById('login-password').value;
            const errEl = document.getElementById('error-msg');
            errEl.classList.remove('show');

            if (!username || !password) {
                errEl.textContent = 'Заполните все поля';
                errEl.classList.add('show');
                return;
            }

            try {
                const resp = await fetch('/admin/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                });

                if (resp.ok) {
                    window.location.href = '/admin/panel';
                } else {
                    errEl.textContent = 'Неверный логин или пароль';
                    errEl.classList.add('show');
                }
            } catch(e) {
                errEl.textContent = 'Ошибка сети';
                errEl.classList.add('show');
            }
        }
    </script>
</body>
</html>"""


# ================================================================
# ADMIN PANEL HTML (protected)
# ================================================================

ADMIN_HTML = """<!DOCTYPE html>
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
            cursor: pointer;
        }
        .sidebar a:hover, .sidebar a.active {
            background: rgba(255,255,255,0.1);
            color: white;
        }
        .sidebar a .icon { margin-right: 10px; }
        .sidebar .logout-btn {
            position: absolute;
            bottom: 20px;
            left: 20px;
            right: 20px;
            padding: 10px;
            background: rgba(244,67,54,0.2);
            color: #f44336;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
        }
        .sidebar .logout-btn:hover { background: rgba(244,67,54,0.3); }
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
        .btn-sm { padding: 6px 12px; font-size: 12px; }
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
            display: inline-block;
        }
        .badge-admin { background: #e3f2fd; color: #1565c0; }
        .badge-manager { background: #fff3e0; color: #e65100; }
        .badge-top_manager { background: #fce4ec; color: #c62828; }
        .badge-worker { background: #e8f5e9; color: #2e7d32; }
        .badge-active { background: #e8f5e9; color: #2e7d32; }
        .badge-inactive { background: #fafafa; color: #999; }
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
        .modal-overlay.show { display: flex; }
        .modal {
            background: white;
            border-radius: 12px;
            padding: 32px;
            width: 520px;
            max-width: 90%;
            max-height: 90vh;
            overflow-y: auto;
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
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #2196f3;
        }
        .toast {
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
        }
        .toast.show { display: block; }
        .toast.success { background: #4caf50; }
        .toast.error { background: #f44336; }
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
        .loading { text-align: center; padding: 40px; color: #999; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>А1 Админ</h2>
        <a class="active" href="javascript:void(0)" onclick="showTab('users', this)"><span class="icon">👥</span>Сотрудники</a>
        <a href="javascript:void(0)" onclick="showTab('projects', this)"><span class="icon">🏗</span>Объекты</a>
        <a href="javascript:void(0)" onclick="showTab('departments', this)"><span class="icon">🏢</span>Отделы</a>
        <a href="javascript:void(0)" onclick="showTab('reports', this)"><span class="icon">📋</span>Отчёты</a>
        <a href="javascript:void(0)" onclick="showTab('rag', this)"><span class="icon">📚</span>База знаний</a>
        <a href="javascript:void(0)" onclick="showTab('system', this)"><span class="icon">⚙️</span>Система</a>
        <a href="/dashboard"><span class="icon">📊</span>Дашборд</a>
        <button class="logout-btn" onclick="doLogout()">Выйти</button>
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
                        <tr><th>Название</th><th>Адрес</th><th>Статус</th><th>Действия</th></tr>
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

        <!-- REPORTS TAB -->
        <div class="tab-content" id="tab-reports">
            <div class="page-header">
                <h1>📋 Отчёты со стройки</h1>
            </div>
            <div class="card" style="margin-bottom:16px;padding:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
                <select id="filter-project" style="padding:8px;border-radius:6px;border:1px solid #ddd;">
                    <option value="">Все объекты</option>
                </select>
                <select id="filter-status" style="padding:8px;border-radius:6px;border:1px solid #ddd;">
                    <option value="">Все статусы</option>
                    <option value="new">Новый</option>
                    <option value="reviewed">Просмотрен</option>
                    <option value="flagged">Важный</option>
                </select>
                <input type="date" id="filter-date" style="padding:8px;border-radius:6px;border:1px solid #ddd;">
                <button class="btn btn-primary btn-sm" onclick="loadReports()">🔍 Фильтр</button>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th style="cursor:pointer" onclick="sortReports('date')">Дата ↕</th>
                            <th style="cursor:pointer" onclick="sortReports('project')">Объект ↕</th>
                            <th style="cursor:pointer" onclick="sortReports('author')">Автор ↕</th>
                            <th>Работы</th>
                            <th>Проблемы</th>
                            <th>Статус</th>
                        </tr>
                    </thead>
                    <tbody id="reports-table">
                        <tr><td colspan="6" class="loading">Загрузка...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- RAG DOCUMENTS TAB -->
        <div class="tab-content" id="tab-rag">
            <div class="page-header">
                <h1>📚 База знаний (RAG)</h1>
                <button class="btn btn-primary" onclick="openUploadDoc()">➕ Добавить документ</button>
            </div>
            <div class="card">
                <table>
                    <thead>
                        <tr><th>Название</th><th>Категория</th><th>Отдел/Объект</th><th>Фрагментов</th><th>Дата</th><th>Загрузил</th></tr>
                    </thead>
                    <tbody id="rag-table">
                        <tr><td colspan="6" class="loading">Загрузка...</td></tr>
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
                <label>Telegram Username</label>
                <input type="text" id="user-tg-username" placeholder="@username (без @)">
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
                <button class="btn btn-primary" onclick="saveUser()">Сохранить</button>
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
                <input type="text" id="project-name" placeholder="Название объекта">
            </div>
            <div class="form-group">
                <label>Адрес</label>
                <input type="text" id="project-address" placeholder="г. Москва, ул. ...">
            </div>
            <div style="display:flex;gap:12px;margin-top:20px;">
                <button class="btn btn-primary" onclick="saveProject()">Сохранить</button>
                <button class="btn" style="background:#eee;" onclick="closeModal('modal-project')">Отмена</button>
            </div>
        </div>
    </div>

    <!-- UPLOAD DOCUMENT MODAL -->
    <div class="modal-overlay" id="modal-doc">
        <div class="modal">
            <h3>Добавить документ в базу знаний</h3>
            <div class="form-group">
                <label>Файл *</label>
                <input type="file" id="doc-file" accept=".pdf,.docx,.doc,.xlsx,.xls,.txt,.csv,.pptx,.md,.json">
            </div>
            <div class="form-group">
                <label>Категория *</label>
                <select id="doc-category">
                    <option value="contract">📄 Договор</option>
                    <option value="act">📋 Акт (КС-2, КС-3)</option>
                    <option value="regulation">📖 Регламент/Инструкция</option>
                    <option value="normative">📐 Норматив (СНиП, ГОСТ, СП)</option>
                    <option value="request">📦 Заявка ТМЦ</option>
                    <option value="protocol">📝 Протокол совещания</option>
                    <option value="report">📊 Отчёт</option>
                    <option value="estimate">💰 Смета/Расчёт</option>
                    <option value="safety">🦺 Документ по ТБ</option>
                    <option value="hr">👤 Кадровый документ</option>
                    <option value="other">📁 Прочее</option>
                </select>
            </div>
            <div class="form-group">
                <label>Отдел</label>
                <select id="doc-department">
                    <option value="">— Не указан</option>
                </select>
            </div>
            <div class="form-group">
                <label>Объект</label>
                <select id="doc-project">
                    <option value="">— Не привязан</option>
                </select>
            </div>
            <div class="form-group">
                <label>Комментарий</label>
                <textarea id="doc-comment" rows="3" placeholder="Описание документа..."></textarea>
            </div>
            <div style="display:flex;gap:12px;margin-top:20px;">
                <button class="btn btn-primary" onclick="uploadDocument()">Загрузить</button>
                <button class="btn" style="background:#eee;" onclick="closeModal('modal-doc')">Отмена</button>
            </div>
        </div>
    </div>

    <!-- TOAST -->
    <div class="toast" id="toast"></div>

    <script>
        let departments = [];

        document.addEventListener('DOMContentLoaded', function() {
            loadUsers();
            loadProjects();
            loadDepartments();
            loadReports();
            loadRagDocuments();
        });

        function showTab(name, el) {
            document.querySelectorAll('.tab-content').forEach(function(t) { t.classList.remove('active'); });
            document.querySelectorAll('.sidebar a').forEach(function(a) { a.classList.remove('active'); });
            document.getElementById('tab-' + name).classList.add('active');
            if (el) el.classList.add('active');
        }

        async function loadUsers() {
            try {
                const resp = await fetch('/admin/api/users');
                if (resp.status === 401) { window.location.href = '/admin'; return; }
                const data = await resp.json();
                renderUsers(data.users);
                document.getElementById('stat-users').textContent = data.users.length;
                document.getElementById('stat-active').textContent = data.users.filter(function(u) { return u.is_active; }).length;
            } catch(e) {
                document.getElementById('users-table').innerHTML = '<tr><td colspan="6">Ошибка загрузки</td></tr>';
            }
        }

        async function loadProjects() {
            try {
                const resp = await fetch('/admin/api/projects');
                if (resp.status === 401) { window.location.href = '/admin'; return; }
                const data = await resp.json();
                renderProjects(data.projects);
                document.getElementById('stat-projects').textContent = data.projects.length;
            } catch(e) {
                document.getElementById('projects-table').innerHTML = '<tr><td colspan="3">Ошибка загрузки</td></tr>';
            }
        }

        async function loadDepartments() {
            try {
                const resp = await fetch('/admin/api/departments');
                if (resp.status === 401) { window.location.href = '/admin'; return; }
                const data = await resp.json();
                departments = data.departments;
                renderDepartments(departments);
                document.getElementById('stat-departments').textContent = departments.length;
                var sel = document.getElementById('user-dept');
                sel.innerHTML = '<option value="">— Не выбран —</option>';
                departments.forEach(function(d) {
                    sel.innerHTML += '<option value="' + d.name + '">' + d.name + '</option>';
                });
            } catch(e) {}
        }

        function renderUsers(users) {
            var tbody = document.getElementById('users-table');
            if (!users.length) {
                tbody.innerHTML = '<tr><td colspan="6">Нет сотрудников</td></tr>';
                return;
            }
            var html = '';
            users.forEach(function(u) {
                var safeName = (u.full_name || '').replace(/"/g, '&quot;');
                var safeTg = (u.telegram_id || '').replace(/"/g, '&quot;');
                var safeTgUser = (u.telegram_username || '').replace(/"/g, '&quot;');
                var safePhone = (u.phone_number || '').replace(/"/g, '&quot;');
                var tgDisplay = u.telegram_id || '';
                if (u.telegram_username) tgDisplay += (tgDisplay ? ' / ' : '') + '@' + u.telegram_username;
                if (!tgDisplay) tgDisplay = '-';
                html += '<tr>';
                html += '<td><b>' + u.full_name + '</b></td>';
                html += '<td><span class="badge badge-' + u.role + '">' + roleLabel(u.role) + '</span></td>';
                html += '<td>' + (u.department || '-') + '</td>';
                html += '<td>' + tgDisplay + '</td>';
                html += '<td><span class="badge badge-' + (u.is_active ? 'active' : 'inactive') + '">' + (u.is_active ? 'Активен' : 'Неактивен') + '</span></td>';
                html += '<td>';
                html += '<button class="btn btn-primary btn-sm" data-action="edit" data-id="' + u.id + '" data-name="' + safeName + '" data-tg="' + safeTg + '" data-tguser="' + safeTgUser + '" data-phone="' + safePhone + '" data-role="' + u.role + '" data-dept="' + (u.department || '') + '">✏️</button> ';
                html += '<button class="btn btn-danger btn-sm" data-action="deactivate" data-id="' + u.id + '" data-name="' + safeName + '">🗑</button>';
                html += '</td>';
                html += '</tr>';
            });
            tbody.innerHTML = html;
            // Attach event listeners
            tbody.querySelectorAll('[data-action="edit"]').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    editUser(this.dataset.id, this.dataset.name, this.dataset.tg, this.dataset.tguser, this.dataset.phone, this.dataset.role, this.dataset.dept);
                });
            });
            tbody.querySelectorAll('[data-action="deactivate"]').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    deactivateUser(this.dataset.id, this.dataset.name);
                });
            });
        }

        function renderProjects(projects) {
            var tbody = document.getElementById('projects-table');
            if (!projects.length) {
                tbody.innerHTML = '<tr><td colspan="4">Нет объектов</td></tr>';
                return;
            }
            var html = '';
            projects.forEach(function(p) {
                var badgeClass = p.status === 'active' ? 'active' : 'inactive';
                var statusLabel = p.status === 'active' ? 'Активный' : (p.status === 'completed' ? 'Завершён' : p.status);
                html += '<tr>';
                html += '<td><b>' + p.name + '</b></td>';
                html += '<td>' + p.address + '</td>';
                html += '<td><span class="badge badge-' + badgeClass + '">' + statusLabel + '</span></td>';
                html += '<td>';
                if (p.status === 'active') {
                    html += '<button class="btn btn-sm" data-action="status" data-id="' + p.id + '" data-status="completed">✅ Завершить</button>';
                } else {
                    html += '<button class="btn btn-primary btn-sm" data-action="status" data-id="' + p.id + '" data-status="active">▶ Активировать</button>';
                }
                html += '</td>';
                html += '</tr>';
            });
            tbody.innerHTML = html;
            tbody.querySelectorAll('[data-action="status"]').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    changeProjectStatus(this.dataset.id, this.dataset.status);
                });
            });
        }

        async function changeProjectStatus(id, newStatus) {
            try {
                var resp = await fetch('/admin/api/projects/' + id, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({status: newStatus})
                });
                if (resp.ok) {
                    showToast('Статус обновлён', 'success');
                    loadProjects();
                } else {
                    showToast('Ошибка', 'error');
                }
            } catch(e) {
                showToast('Ошибка сети', 'error');
            }
        }

        var allReports = [];
        var reportsSortField = 'date';
        var reportsSortDir = -1;

        async function loadReports() {
            try {
                var project = document.getElementById('filter-project').value;
                var status = document.getElementById('filter-status').value;
                var date = document.getElementById('filter-date').value;
                var url = '/admin/api/reports?';
                if (project) url += 'project=' + encodeURIComponent(project) + '&';
                if (status) url += 'status=' + status + '&';
                if (date) url += 'date=' + date + '&';
                var resp = await fetch(url);
                if (resp.status === 401) { window.location.href = '/admin'; return; }
                var data = await resp.json();
                allReports = data.reports;
                renderReports(allReports);
                // Populate project filter
                var filterSel = document.getElementById('filter-project');
                if (filterSel.options.length <= 1) {
                    var projects = [];
                    allReports.forEach(function(r) {
                        if (r.project_name && projects.indexOf(r.project_name) === -1) projects.push(r.project_name);
                    });
                    projects.sort();
                    projects.forEach(function(p) {
                        var opt = document.createElement('option');
                        opt.value = p; opt.textContent = p;
                        filterSel.appendChild(opt);
                    });
                }
            } catch(e) {
                document.getElementById('reports-table').innerHTML = '<tr><td colspan="6">Ошибка загрузки</td></tr>';
            }
        }

        function sortReports(field) {
            if (reportsSortField === field) {
                reportsSortDir *= -1;
            } else {
                reportsSortField = field;
                reportsSortDir = -1;
            }
            allReports.sort(function(a, b) {
                var va = a[field] || '';
                var vb = b[field] || '';
                if (va < vb) return -1 * reportsSortDir;
                if (va > vb) return 1 * reportsSortDir;
                return 0;
            });
            renderReports(allReports);
        }

        function renderReports(reports) {
            var tbody = document.getElementById('reports-table');
            if (!reports.length) {
                tbody.innerHTML = '<tr><td colspan="6">Нет отчётов</td></tr>';
                return;
            }
            var html = '';
            reports.forEach(function(r) {
                var statusBadge = r.status === 'new' ? 'active' : (r.status === 'flagged' ? 'inactive' : 'active');
                var statusLabel = r.status === 'new' ? '🆕 Новый' : (r.status === 'reviewed' ? '✅ Просмотрен' : '⚠️ Важный');
                var workShort = (r.work_done || '').substring(0, 60) + ((r.work_done || '').length > 60 ? '...' : '');
                var probShort = (r.problems || '-').substring(0, 40) + ((r.problems || '').length > 40 ? '...' : '');
                html += '<tr>';
                html += '<td>' + (r.date || '-') + '</td>';
                html += '<td><b>' + (r.project_name || '-') + '</b></td>';
                html += '<td>' + (r.author_name || '-') + '</td>';
                html += '<td>' + workShort + '</td>';
                html += '<td>' + (r.problems ? '<span style="color:#e74c3c">' + probShort + '</span>' : '-') + '</td>';
                html += '<td><span class="badge badge-' + statusBadge + '">' + statusLabel + '</span></td>';
                html += '</tr>';
            });
            tbody.innerHTML = html;
        }

        function openUploadDoc() {
            // Populate department and project selects
            var deptSel = document.getElementById('doc-department');
            deptSel.innerHTML = '<option value="">\u2014 \u041d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d</option>';
            departments.forEach(function(d) {
                var opt = document.createElement('option');
                opt.value = d.name; opt.textContent = d.name;
                deptSel.appendChild(opt);
            });
            // Projects from existing data
            fetch('/admin/api/projects').then(function(r){return r.json();}).then(function(data){
                var projSel = document.getElementById('doc-project');
                projSel.innerHTML = '<option value="">\u2014 \u041d\u0435 \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d</option>';
                (data.projects||[]).forEach(function(p){
                    var opt = document.createElement('option');
                    opt.value = p.name; opt.textContent = p.name;
                    projSel.appendChild(opt);
                });
            });
            document.getElementById('modal-doc').classList.add('active');
        }

        async function uploadDocument() {
            var fileInput = document.getElementById('doc-file');
            var category = document.getElementById('doc-category').value;
            var department = document.getElementById('doc-department').value;
            var project = document.getElementById('doc-project').value;
            var comment = document.getElementById('doc-comment').value;

            if (!fileInput.files.length) {
                showToast('\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0444\u0430\u0439\u043b', 'error');
                return;
            }

            var formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('category', category);
            formData.append('department', department);
            formData.append('project_name', project);
            formData.append('comment', comment);

            try {
                showToast('\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...', 'success');
                var resp = await fetch('/admin/api/upload-document', {
                    method: 'POST',
                    body: formData
                });
                if (resp.status === 401) { window.location.href = '/admin'; return; }
                var result = await resp.json();
                if (result.status === 'ok') {
                    showToast('\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d (' + result.chunks + ' \u0444\u0440\u0430\u0433\u043c\u0435\u043d\u0442\u043e\u0432)', 'success');
                    closeModal('modal-doc');
                    loadRagDocuments();
                } else {
                    showToast(result.error || '\u041e\u0448\u0438\u0431\u043a\u0430', 'error');
                }
            } catch(e) {
                showToast('\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u0435\u0442\u0438', 'error');
            }
        }

        async function loadRagDocuments() {
            try {
                var resp = await fetch('/admin/api/rag-documents');
                if (resp.status === 401) { window.location.href = '/admin'; return; }
                var data = await resp.json();
                renderRagDocuments(data.documents);
            } catch(e) {
                document.getElementById('rag-table').innerHTML = '<tr><td colspan="6">Ошибка загрузки</td></tr>';
            }
        }

        function renderRagDocuments(docs) {
            var tbody = document.getElementById('rag-table');
            if (!docs.length) {
                tbody.innerHTML = '<tr><td colspan="6">Нет загруженных документов</td></tr>';
                return;
            }
            var categories = {
                'contract': '📄 Договор',
                'act': '📋 Акт',
                'regulation': '📖 Регламент',
                'normative': '📐 Норматив',
                'request': '📦 Заявка ТМЦ',
                'protocol': '📝 Протокол',
                'report': '📊 Отчёт',
                'letter': '✉️ Письмо',
                'estimate': '💰 Смета',
                'safety': '🦺 ТБ',
                'hr': '👤 Кадры',
                'other': '📁 Прочее'
            };
            var html = '';
            docs.forEach(function(d) {
                var cat = categories[d.category] || d.category;
                var date = (d.loaded_at || '').substring(0, 10);
                var proj = d.project_name || d.department || '\u2014';
                html += '<tr>';
                html += '<td><b>' + (d.title || d.filename) + '</b></td>';
                html += '<td>' + cat + '</td>';
                html += '<td>' + proj + '</td>';
                html += '<td>' + (d.chunks || '?') + '</td>';
                html += '<td>' + date + '</td>';
                html += '<td>' + (d.loaded_by || '-') + '</td>';
                html += '</tr>';
            });
            tbody.innerHTML = html;
        }

        function renderDepartments(depts) {
            var tbody = document.getElementById('departments-table');
            var html = '';
            depts.forEach(function(d) { html += '<tr><td>' + d.name + '</td></tr>'; });
            tbody.innerHTML = html;
        }

        function roleLabel(role) {
            var labels = {
                'admin': 'Админ',
                'top_manager': 'ТОП',
                'manager': 'Руководитель',
                'worker': 'Сотрудник'
            };
            return labels[role] || role;
        }

        function openAddUser() {
            document.getElementById('modal-user-title').textContent = 'Добавить сотрудника';
            document.getElementById('edit-user-id').value = '';
            document.getElementById('user-name').value = '';
            document.getElementById('user-tg').value = '';
            document.getElementById('user-tg-username').value = '';
            document.getElementById('user-phone').value = '';
            document.getElementById('user-role').value = 'worker';
            document.getElementById('user-dept').value = '';
            document.getElementById('modal-user').classList.add('show');
        }

        function editUser(id, name, tg, tgUser, phone, role, dept) {
            document.getElementById('modal-user-title').textContent = 'Редактировать сотрудника';
            document.getElementById('edit-user-id').value = id;
            document.getElementById('user-name').value = name;
            document.getElementById('user-tg').value = (tg === '—' || tg === 'undefined') ? '' : tg;
            document.getElementById('user-tg-username').value = (tgUser === '—' || tgUser === 'undefined') ? '' : tgUser;
            document.getElementById('user-phone').value = (phone === '—' || phone === 'undefined') ? '' : phone;
            document.getElementById('user-role').value = role;
            document.getElementById('user-dept').value = (dept === '—' || dept === 'undefined') ? '' : dept;
            document.getElementById('modal-user').classList.add('show');
        }

        function openAddProject() {
            document.getElementById('project-name').value = '';
            document.getElementById('project-address').value = '';
            document.getElementById('modal-project').classList.add('show');
        }

        function closeModal(id) {
            document.getElementById(id).classList.remove('show');
        }

        async function saveUser() {
            var id = document.getElementById('edit-user-id').value;
            var name = document.getElementById('user-name').value.trim();
            var tg = document.getElementById('user-tg').value.trim();
            var tgUsername = document.getElementById('user-tg-username').value.trim().replace('@', '');
            var phone = document.getElementById('user-phone').value.trim();
            var role = document.getElementById('user-role').value;
            var dept = document.getElementById('user-dept').value;

            if (!name) {
                showToast('Введите ФИО', 'error');
                return;
            }

            try {
                var resp;
                var body = JSON.stringify({
                    full_name: name,
                    telegram_id: tg || null,
                    telegram_username: tgUsername || null,
                    phone_number: phone || null,
                    role: role,
                    department_name: dept || null
                });

                if (id) {
                    resp = await fetch('/admin/api/users/' + id, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: body
                    });
                } else {
                    resp = await fetch('/admin/api/users', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: body
                    });
                }

                if (resp.ok) {
                    showToast(id ? 'Сотрудник обновлён' : 'Сотрудник добавлен', 'success');
                    closeModal('modal-user');
                    loadUsers();
                } else {
                    var err = await resp.json();
                    showToast('Ошибка: ' + (err.detail || 'неизвестная'), 'error');
                }
            } catch(e) {
                showToast('Ошибка сети', 'error');
            }
        }

        async function saveProject() {
            var name = document.getElementById('project-name').value.trim();
            var address = document.getElementById('project-address').value.trim();

            if (!name) {
                showToast('Введите название объекта', 'error');
                return;
            }

            try {
                var resp = await fetch('/admin/api/projects', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name, address: address})
                });

                if (resp.ok) {
                    showToast('Объект добавлен', 'success');
                    closeModal('modal-project');
                    loadProjects();
                } else {
                    showToast('Ошибка при добавлении', 'error');
                }
            } catch(e) {
                showToast('Ошибка сети', 'error');
            }
        }

        async function deactivateUser(id, name) {
            if (!confirm('Деактивировать сотрудника "' + name + '"?')) return;

            try {
                var resp = await fetch('/admin/api/users/' + id, {method: 'DELETE'});
                if (resp.ok) {
                    showToast('Сотрудник деактивирован', 'success');
                    loadUsers();
                }
            } catch(e) {
                showToast('Ошибка', 'error');
            }
        }

        async function doLogout() {
            await fetch('/admin/api/logout', {method: 'POST'});
            window.location.href = '/admin';
        }

        function showToast(msg, type) {
            var toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = 'toast show ' + type;
            setTimeout(function() { toast.classList.remove('show'); }, 3000);
        }

        // Make all functions globally accessible for onclick handlers
        window.showTab = showTab;
        window.loadUsers = loadUsers;
        window.loadProjects = loadProjects;
        window.loadDepartments = loadDepartments;
        window.loadReports = loadReports;
        window.sortReports = sortReports;
        window.loadRagDocuments = loadRagDocuments;
        window.openUploadDoc = openUploadDoc;
        window.uploadDocument = uploadDocument;
        window.openAddUser = openAddUser;
        window.editUser = editUser;
        window.openAddProject = openAddProject;
        window.closeModal = closeModal;
        window.saveUser = saveUser;
        window.saveProject = saveProject;
        window.deactivateUser = deactivateUser;
        window.changeProjectStatus = changeProjectStatus;
        window.doLogout = doLogout;
        window.showToast = showToast;
    </script>
</body>
</html>"""


# ================================================================
# ROUTES
# ================================================================

@admin_router.get("", response_class=HTMLResponse)
async def get_admin_login(request: Request):
    """Show login page or redirect to panel if already authenticated."""
    if check_auth(request):
        return RedirectResponse(url="/admin/panel", status_code=302)
    return HTMLResponse(content=LOGIN_HTML)


@admin_router.get("/panel", response_class=HTMLResponse)
async def get_admin_panel(request: Request):
    """Serve the admin panel (protected)."""
    if not check_auth(request):
        return RedirectResponse(url="/admin", status_code=302)
    return HTMLResponse(content=ADMIN_HTML)
