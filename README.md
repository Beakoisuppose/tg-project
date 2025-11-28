# 🛠️ Server Health Monitor — Telegram Bot

> **Лёгкий, быстрый и надёжный мониторинг сервера прямо в Telegram.**  
> Проверяет сервисы, Docker-контейнеры, порты, диск, память и нагрузку —  
> отправляет **Hourly Report** + отчёт по кнопке 🔄 *«Проверить сейчас»*.

![Python](https://img.shields.io/badge/Python-3.6%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-lightgrey)

---

## ✨ Возможности

- ✅ **Проверка systemd-сервисов** (`nginx`, `prometheus`, `grafana-server` и т.д.)
- ✅ **Мониторинг Docker-контейнеров** по имени
- ✅ **Проверка TCP-портов** (22, 80, 443 — легко расширить)
- ✅ **Системные метрики**
  - 💾 использование диска (`/`)
  - 🧠 RAM и Swap
  - ⚡ Load Average (1m)
- ✅ **Регулярные отчёты** — по умолчанию раз в час
- ✅ **Мгновенная проверка по кнопке** 🔄
- ✅ **Красивая Telegram-разметка** (Markdown + эмодзи)
- ✅ **Работа 24/7** как systemd-сервис
- ✅ **Zero external dependencies** — нужен только Python 3

---

## 📸 Пример отчёта

📊 Отчёт о состоянии сервера — 2025-11-28 15:30:22

Сервисы:
NAME STATUS
nginx 🟢 active
prometheus 🟢 active
grafana-server 🟢 active

Docker контейнеры:
NAME STATUS
container1 🟢 running
container2 🟢 running

Порты:
PORT STATUS
22 🟢 open
80 🟢 open
443 🟢 open

Диск (/): 🟢 42% занято
RAM: 🟢 65%
Swap: 🟢 0%
Load (1m): 🟢 0.75 (ядер: 4)

✅ Все системы в норме.
📊 Итог: 9/9 OK

---

## 🚀 Установка (5 шагов)

### **1. Создать проект**

```bash
mkdir -p ~/monitoring && cd ~/monitoring
nano workfile.py  # вставьте код бота
chmod +x workfile.py

```
### **2. Настроить конфиг в начале файла**
```
TOKEN = "ВАШ_ТОКЕН_БОТА"        # Получите у @BotFather
CHAT_ID = "ВАШ_CHAT_ID"         # Узнайте у @userinfobot
REPORT_INTERVAL = 3600          # 1 час

SERVICES = ["nginx", "prometheus", "grafana-server"]
CONTAINERS = ["app", "db"]
PORTS = [22, 80, 443]
```
### **3. Добавить systemd-сервис**
```
sudo nano /etc/systemd/system/service-checker.service
```
Вставить следующий код:
```
[Unit]
Description=Server Health Monitor Bot
After=network.target docker.service

[Service]
Type=simple
User=$youruser
Group=$your group
WorkingDirectory=/home/$youruser
ExecStart=/usr/bin/python3 /home/$youruser/workfile.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```
4. Запустить сервис
```
sudo systemctl daemon-reload
sudo systemctl enable --now service-checker.service
```

5. Проверить работу
```
systemctl status service-checker
journalctl -u service-checker -f
tail -f ~/service_checker.log
```

















