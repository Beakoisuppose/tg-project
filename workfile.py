#!/usr/bin/env python3
import subprocess
import requests
import socket
import os
from datetime import datetime
import time
import sys

# ==========================
# CONFIG
# ==========================
TOKEN = "token"
CHAT_ID = "token"
REPORT_INTERVAL = 3600  # 1 час
API_URL = f"https://api.telegram.org/bot{TOKEN}"
LOG_PATH = os.path.expanduser("~/service_checker.log")

SERVICES = ["nginx", "prometheus", "grafana-server"]
CONTAINERS = ["container1", "container2"]
PORTS = [22, 80, 443]

# ==========================
# GLOBALS
# ==========================
LAST_UPDATE_ID = 0
last_report = 0


# ==========================
# UTILS
# ==========================
def log_to_file(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"[LOG ERROR] {e}", file=sys.stderr)


# ==========================
# CHECK FUNCTIONS
# ==========================
def check_service(service):
    try:
        result = subprocess.run(["systemctl", "is-active", service],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except Exception as e:
        log_to_file(f"Error checking service '{service}': {e}")
        return "error"


def check_container(container):
    try:
        result = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", container],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else "not_found"
    except FileNotFoundError:
        return "docker_not_found"
    except Exception as e:
        log_to_file(f"Error checking container '{container}': {e}")
        return "error"


def check_port(port, host="127.0.0.1"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return "open" if result == 0 else "closed"


def check_disk_usage(path="/"):
    try:
        stat = os.statvfs(path)
        total = stat.f_frsize * stat.f_blocks
        free = stat.f_frsize * stat.f_bfree
        used_pct = int(100 * (total - free) / total)
        return min(used_pct, 100)
    except Exception as e:
        log_to_file(f"Error checking disk '{path}': {e}")
        return -1


def check_memory():
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                key = parts[0].rstrip(":")
                if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
                    mem[key] = int(parts[1])
        ram_used_pct = int(100 * (1 - mem.get("MemAvailable", 0) / mem["MemTotal"])) if mem.get("MemTotal") else -1
        swap_used_pct = 0
        if mem.get("SwapTotal", 0) > 0:
            swap_used_pct = int(100 * (1 - mem.get("SwapFree", 0) / mem["SwapTotal"]))
        return ram_used_pct, swap_used_pct
    except Exception as e:
        log_to_file(f"Error checking memory: {e}")
        return -1, -1


def check_load():
    try:
        with open("/proc/loadavg") as f:
            load_line = f.read().split()
            load1 = float(load_line[0])
        cores = os.cpu_count() or 1
        return load1, cores
    except Exception as e:
        log_to_file(f"Error checking load: {e}")
        return 0.0, 1


# ==========================
# TELEGRAM
# ==========================
def send_telegram_message(message, buttons=False):
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [{"text": "🔄 Проверить сейчас", "callback_data": "run_check"}]
            ]
        }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        log_to_file(f"Telegram sent OK. Status: {response.status_code}")
    except Exception as e:
        log_to_file(f"Telegram send failed: {e}")


def answer_callback(callback_query_id):
    url = f"{API_URL}/answerCallbackQuery"
    try:
        requests.post(url, json={
            "callback_query_id": callback_query_id,
            "text": "Проверяю... 🔄",
            "show_alert": False
        }, timeout=3)
    except Exception as e:
        log_to_file(f"Callback answer failed: {e}")


# ==========================
# REPORT
# ==========================
def generate_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"*📊 Отчёт о состоянии сервера — {now}*\n\n"
    critical = False

    report += "*Сервисы:*\n```\nNAME              STATUS\n-------------------------\n"
    for svc in SERVICES:
        status = check_service(svc)
        emoji = "🟢" if status == "active" else "🔴"
        if status != "active":
            critical = True
        report += f"{svc:<16} {emoji} {status}\n"
    report += "```\n\n"

    report += "*Docker контейнеры:*\n```\nNAME              STATUS\n-------------------------\n"
    for cont in CONTAINERS:
        status = check_container(cont)
        emoji = "🟢" if status == "running" else "🔴"
        if status != "running":
            critical = True
        report += f"{cont:<16} {emoji} {status}\n"
    report += "```\n\n"

    report += "*Порты:*\n```\nPORT    STATUS\n----------------\n"
    for port in PORTS:
        status = check_port(port)
        emoji = "🟢" if status == "open" else "🔴"
        if status != "open":
            critical = True
        report += f"{str(port):<7} {emoji} {status}\n"
    report += "```\n\n"

    disk_pct = check_disk_usage("/")
    if disk_pct >= 0:
        disk_emoji = "🟢" if disk_pct < 85 else "🟠" if disk_pct < 95 else "🔴"
        if disk_pct >= 95:
            critical = True
        report += f"*Диск (/):* {disk_emoji} {disk_pct}% занято\n"
    else:
        report += "*Диск (/):* ⚠️ ошибка\n"

    ram_pct, swap_pct = check_memory()
    if ram_pct >= 0:
        ram_emoji = "🟢" if ram_pct < 80 else "🟠" if ram_pct < 90 else "🔴"
        swap_emoji = "🟢" if swap_pct < 50 else "🟠" if swap_pct < 80 else "🔴"
        if ram_pct >= 90 or swap_pct >= 80:
            critical = True
        report += f"*RAM:* {ram_emoji} {ram_pct}% | *Swap:* {swap_emoji} {swap_pct}%\n"
    else:
        report += "*RAM/Swap:* ⚠️ ошибка\n"

    load1, cores = check_load()
    load_emoji = "🟢" if load1 < cores else "🟠" if load1 < 2 * cores else "🔴"
    if load1 > 3 * cores:
        critical = True
    report += f"*Нагрузка (1m):* {load_emoji} {load1:.2f} (ядер: {cores})\n"

    report += "\n"
    if critical:
        report += "⚠️ *ВНИМАНИЕ: проблемы!*\n"
    else:
        report += "✅ *Все системы в норме.*\n"

    total = len(SERVICES) + len(CONTAINERS) + len(PORTS) + 3
    failed = report.count("🔴")
    ok = total - failed
    report += f"\n📊 *Итого: {ok}/{total} OK*"
    return report


# ==========================
# TELEGRAM UPDATES
# ==========================
def check_updates():
    global LAST_UPDATE_ID, last_report

    try:
        url = f"{API_URL}/getUpdates?offset={LAST_UPDATE_ID+1}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        for update in data.get("result", []):
            LAST_UPDATE_ID = update["update_id"]

            if "callback_query" in update:
                cb = update["callback_query"]
                if cb["data"] == "run_check":
                    answer_callback(cb["id"])

                    report = generate_report()
                    send_telegram_message(report, buttons=True)

                    # Сбрасываем таймер — след. отчёт через час
                    last_report = time.time()

                    log_to_file("manual check done")

    except Exception as e:
        log_to_file(f"check_updates error: {e}")


# ==========================
# MAIN LOOP
# ==========================
def main_loop():
    global last_report
    last_report = time.time()
    log_to_file(f"🚀 Цикл запущен. Интервал: {REPORT_INTERVAL} сек")

    while True:
        now = time.time()

        if now - last_report >= REPORT_INTERVAL:
            try:
                report = generate_report()
                send_telegram_message(report, buttons=True)
                last_report = now
                log_to_file("📬 Регулярный отчёт отправлен")
            except Exception as e:
                log_to_file(f"ошибка регулярного отчёта: {e}")

        check_updates()
        time.sleep(10)


# ==========================
# ENTRY POINT
# ==========================
if __name__ == "__main__":
    try:
        log_to_file("🟢 Скрипт запущен")
        main_loop()
    except KeyboardInterrupt:
        log_to_file("🛑 Остановлен вручную")
    except Exception as e:
        error_msg = f"💥 Критическая ошибка: {e}"
        log_to_file(error_msg)
        try:
            send_telegram_message(f"🔥 Ошибка: `{error_msg}`")
        except:
            pass
