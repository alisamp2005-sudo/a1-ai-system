"""
Telegram Mini App — Daily Report Form for site managers (прорабы).
Accessible at /miniapp/report
"""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)
miniapp_router = APIRouter(prefix="/miniapp")

REPORT_FORM_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>А1 — Ежедневный отчет</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--tg-theme-bg-color, #ffffff);
            color: var(--tg-theme-text-color, #1a1a2e);
            padding: 16px;
            padding-bottom: 100px;
        }
        h1 {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            text-align: center;
        }
        .form-group {
            margin-bottom: 16px;
        }
        label {
            display: block;
            font-size: 14px;
            font-weight: 500;
            color: var(--tg-theme-hint-color, #666);
            margin-bottom: 6px;
        }
        input, select, textarea {
            width: 100%;
            padding: 12px 14px;
            border: 1px solid var(--tg-theme-hint-color, #ddd);
            border-radius: 10px;
            font-size: 16px;
            background: var(--tg-theme-secondary-bg-color, #f5f5f5);
            color: var(--tg-theme-text-color, #333);
            outline: none;
            transition: border-color 0.2s;
        }
        input:focus, select:focus, textarea:focus {
            border-color: var(--tg-theme-button-color, #2196f3);
        }
        textarea {
            min-height: 80px;
            resize: vertical;
        }
        .section-title {
            font-size: 16px;
            font-weight: 600;
            margin-top: 24px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--tg-theme-hint-color, #eee);
        }
        .weather-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .workers-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 12px;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 0;
        }
        .checkbox-group input[type="checkbox"] {
            width: 20px;
            height: 20px;
        }
        .checkbox-group label {
            margin: 0;
            font-size: 15px;
            color: var(--tg-theme-text-color, #333);
        }
        .submit-btn {
            width: 100%;
            padding: 14px;
            background: var(--tg-theme-button-color, #2196f3);
            color: var(--tg-theme-button-text-color, #fff);
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 24px;
        }
        .submit-btn:active {
            opacity: 0.8;
        }
        .success-message {
            display: none;
            text-align: center;
            padding: 40px 20px;
        }
        .success-message .icon {
            font-size: 48px;
            margin-bottom: 16px;
        }
        .success-message h2 {
            font-size: 20px;
            margin-bottom: 8px;
        }
        .success-message p {
            color: var(--tg-theme-hint-color, #666);
        }
    </style>
</head>
<body>
    <div id="form-container">
        <h1>📋 Ежедневный отчет</h1>

        <div class="form-group">
            <label>Объект</label>
            <select id="project">
                <option value="">Выберите объект...</option>
                <option value="Михалковская">Михалковская</option>
                <option value="Хорошевское шоссе">Хорошевское шоссе</option>
                <option value="Варшавское шоссе">Варшавское шоссе</option>
                <option value="Ленинградский проспект">Ленинградский проспект</option>
                <option value="Рязанский проспект">Рязанский проспект</option>
            </select>
        </div>

        <div class="form-group">
            <label>Дата отчета</label>
            <input type="date" id="report_date" />
        </div>

        <div class="section-title">👷 Персонал на объекте</div>
        <div class="workers-grid">
            <div class="form-group">
                <label>ИТР</label>
                <input type="number" id="workers_itr" placeholder="0" min="0" />
            </div>
            <div class="form-group">
                <label>Рабочие</label>
                <input type="number" id="workers_labor" placeholder="0" min="0" />
            </div>
            <div class="form-group">
                <label>Субподряд</label>
                <input type="number" id="workers_sub" placeholder="0" min="0" />
            </div>
        </div>

        <div class="section-title">🌤 Погода</div>
        <div class="weather-grid">
            <div class="form-group">
                <label>Температура, °C</label>
                <input type="number" id="weather_temp" placeholder="25" />
            </div>
            <div class="form-group">
                <label>Условия</label>
                <select id="weather_cond">
                    <option value="sunny">☀️ Ясно</option>
                    <option value="cloudy">⛅ Облачно</option>
                    <option value="rain">🌧 Дождь</option>
                    <option value="snow">❄️ Снег</option>
                    <option value="wind">💨 Ветер</option>
                </select>
            </div>
        </div>

        <div class="section-title">🏗 Выполненные работы</div>
        <div class="form-group">
            <label>Описание выполненных работ за день</label>
            <textarea id="work_done" placeholder="Бетонирование плиты перекрытия 3 этажа, монтаж арматуры..."></textarea>
        </div>

        <div class="section-title">⚠️ Проблемы и простои</div>
        <div class="form-group">
            <label>Проблемы (если есть)</label>
            <textarea id="problems" placeholder="Задержка поставки арматуры на 2 часа..."></textarea>
        </div>

        <div class="section-title">📦 Потребности</div>
        <div class="form-group">
            <label>Что нужно на завтра</label>
            <textarea id="needs" placeholder="Бетон М300 — 20 м³, арматура d12 — 2 тонны..."></textarea>
        </div>

        <div class="section-title">✅ Безопасность</div>
        <div class="checkbox-group">
            <input type="checkbox" id="safety_briefing" />
            <label for="safety_briefing">Инструктаж проведен</label>
        </div>
        <div class="checkbox-group">
            <input type="checkbox" id="safety_ppe" />
            <label for="safety_ppe">Все в СИЗ</label>
        </div>
        <div class="checkbox-group">
            <input type="checkbox" id="safety_incidents" />
            <label for="safety_incidents">Происшествий нет</label>
        </div>

        <button class="submit-btn" onclick="submitReport()">📤 Отправить отчет</button>
    </div>

    <div class="success-message" id="success">
        <div class="icon">✅</div>
        <h2>Отчет отправлен!</h2>
        <p>Данные переданы в систему А1</p>
    </div>

    <script>
        // Initialize Telegram Web App
        const tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();

        // Set today's date
        document.getElementById('report_date').valueAsDate = new Date();

        function submitReport() {
            const data = {
                project: document.getElementById('project').value,
                report_date: document.getElementById('report_date').value,
                workers_itr: parseInt(document.getElementById('workers_itr').value) || 0,
                workers_labor: parseInt(document.getElementById('workers_labor').value) || 0,
                workers_sub: parseInt(document.getElementById('workers_sub').value) || 0,
                weather_temp: document.getElementById('weather_temp').value,
                weather_cond: document.getElementById('weather_cond').value,
                work_done: document.getElementById('work_done').value,
                problems: document.getElementById('problems').value,
                needs: document.getElementById('needs').value,
                safety_briefing: document.getElementById('safety_briefing').checked,
                safety_ppe: document.getElementById('safety_ppe').checked,
                safety_incidents: document.getElementById('safety_incidents').checked,
            };

            if (!data.project) {
                tg.showAlert('Выберите объект!');
                return;
            }
            if (!data.work_done) {
                tg.showAlert('Опишите выполненные работы!');
                return;
            }

            // Send data to bot
            tg.sendData(JSON.stringify(data));

            // Show success
            document.getElementById('form-container').style.display = 'none';
            document.getElementById('success').style.display = 'block';

            // Close Mini App after 2 seconds
            setTimeout(() => tg.close(), 2000);
        }
    </script>
</body>
</html>
"""


@miniapp_router.get("/report", response_class=HTMLResponse)
async def get_report_form():
    """Serve the daily report Mini App form."""
    return HTMLResponse(content=REPORT_FORM_HTML)
