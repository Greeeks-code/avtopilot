# Общее для всех скриптов Автопилота: где лежат данные, как вызвать hh,
# настройки, журнал, уведомления. Работает на Mac и Windows.
import os, sys, json, re, shutil, subprocess, platform, datetime
from pathlib import Path

KOD = Path(__file__).resolve().parent.parent       # папка программы (~/avtopilot)
SCRIPTS = KOD / "scripts"
SHABLONY = KOD / "shablony"
VERSIYA = (KOD / "VERSION").read_text(encoding="utf-8").strip() if (KOD / "VERSION").exists() else "?"

# Проверенная версия инструмента hh. Новую ставим только после проверки автором:
# 1.9.x меняет поведение, и обновление «само» может сломать рассылку у всех.
HH_VERSIYA = "1.9.4"

# Данные человека: настройки, письма, вход в hh, журналы.
# На Mac не в Desktop/Documents/Downloads: расписание туда не пускают
# («Operation not permitted», так рассылка автора молчала 15-17.09.2026).
DANNYE = Path(os.environ.get("AVTOPILOT_DANNYE", Path.home() / "avtopilot-dannye"))
NASTROIKI = DANNYE / "nastroiki.json"
LOG = DANNYE / "log"
ISTORIYA = DANNYE / "istoriya-rassylok.json"

WIN = platform.system() == "Windows"
MAC = platform.system() == "Darwin"

# Чтобы русские буквы не ломались в консоли Windows.
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def uv_bin():
    exe = "uv.exe" if WIN else "uv"
    home = Path.home()
    for c in (shutil.which("uv"), home / ".local" / "bin" / exe, home / ".cargo" / "bin" / exe,
              "/opt/homebrew/bin/uv", "/usr/local/bin/uv"):
        if c and Path(c).exists():
            return str(c)
    sys.exit("Не найден uv. Установка - шаг 3 в УСТАНОВКА.md.")


def hh(*args, timeout=None):
    """Запуск hh-applicant-tool нужной версии со своей папкой входа.
    Каждая установка Автопилота хранит вход в hh в своих данных - так на одном
    компьютере могут жить два человека."""
    return subprocess.run(hh_komanda(*args), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=ENV, **BEZ_OKNA)


def hh_komanda(*args):
    # [playwright] - браузер для входа в hh: с версии 1.9 он не ставится сам,
    # и без него никто не смог бы войти (найдено автопроверкой 05.10.2026).
    return [uv_bin(), "tool", "run", "--from", f"hh-applicant-tool[playwright]=={HH_VERSIYA}",
            "hh-applicant-tool", "-c", str(DANNYE / "hh"), *args]


# На Windows расписание запускает нас без консоли; без этого флага каждый вызов
# hh открывал бы чёрное окно.
BEZ_OKNA = {"creationflags": subprocess.CREATE_NO_WINDOW} if WIN else {}


def api(endpoint, pary=(), **params):
    """Запрос к API hh. pary - повторяющиеся параметры: [("work_format", "REMOTE"), ...]."""
    args = ["call-api", endpoint] + [f"{k}={v}" for k, v in [*pary, *params.items()]]
    r = hh(*args, timeout=120)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"_oshibka": (r.stdout + r.stderr)[-300:]}


def zagruzit():
    if not NASTROIKI.exists():
        sys.exit(f"Нет настроек {NASTROIKI}. Сначала пройди установку (УСТАНОВКА.md).")
    return json.loads(NASTROIKI.read_text(encoding="utf-8"))


def sohranit(cfg):
    NASTROIKI.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")


def log_segodnya():
    LOG.mkdir(parents=True, exist_ok=True)
    return LOG / f"{datetime.date.today()}.log"


def pisat_log(text):
    with open(log_segodnya(), "a", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def pisat_fail(imya, text):
    (DANNYE / imya).write_text(text, encoding="utf-8")


def notify(title, text):
    # Уведомление на экране; если не вышло - просто печать.
    print(f"[{title}] {text}")
    try:
        t = text.replace('"', "'").replace("'", "’")
        h = title.replace('"', "'").replace("'", "’")
        if MAC:
            subprocess.run(["osascript", "-e", f'display notification "{t}" with title "{h}" sound name "Glass"'],
                           timeout=10)
        elif WIN:
            ps = ("[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null;"
                  "$n=New-Object System.Windows.Forms.NotifyIcon;"
                  "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
                  f"$n.ShowBalloonTip(10000,'{h}','{t}',[System.Windows.Forms.ToolTipIcon]::Info);"
                  "Start-Sleep -Seconds 10;$n.Dispose()")
            subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                           timeout=30, **BEZ_OKNA)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", h, t], timeout=10)
    except Exception:
        pass


# ---------- поиск ----------

def _slovo(w):
    w = w.strip()
    return f'"{w}"' if re.search(r"[\s+#.\-/]", w) and not w.startswith('"') else w


def zapros_bloka(cfg, blok):
    """Строка поиска hh для блока. Стоп-слова и чужие роли - прямо в запросе (NOT),
    а не через --excluded-filter: тот открывает страницу каждой вакансии на hh.ru,
    и после его включения у автора 22.09.2026 началась капча."""
    chasti = []
    if blok.get("zapros"):
        chasti.append(f"({blok['zapros']})")
    imena = blok.get("isklyuchit_v_nazvanii") or []
    if imena:
        chasti.append("NOT NAME:(" + " OR ".join(_slovo(w) for w in imena) + ")")
    stop = cfg.get("stop_slova") or []
    if stop:
        chasti.append("NOT (" + " OR ".join(_slovo(w) for w in stop) + ")")
    return " ".join(chasti) or None


def filtry_poiska(cfg, blok):
    """Общие фильтры hh как пары (параметр API, значение) - одни и те же
    для рассылки и для предпросмотра, чтобы человек видел ровно то, куда пойдут отклики."""
    p = []
    for r in blok.get("roli") or []:
        p.append(("professional_role", r))
    for f in cfg.get("format_raboty") or []:
        p.append(("work_format", f))
    for a in cfg.get("regiony") or []:
        p.append(("area", a))
    if cfg.get("opyt"):                      # одно значение: hh принимает только одно
        p.append(("experience", cfg["opyt"]))
    if cfg.get("zarplata_ot"):
        p.append(("salary", cfg["zarplata_ot"]))
        p.append(("currency", cfg.get("valyuta") or "RUR"))
    return p


def proverit_pismo(text):
    """Ловушки шаблона hh: письмо проходит через `текст % данные` и через {вариант|вариант}.
    «Рост на 30%» роняет отклик ошибкой, лишняя фигурная скобка ломает текст."""
    beda = []
    if len(text.strip()) < 200:
        beda.append("письмо короче 200 знаков")
    chisto = re.sub(r"%%|%\((vacancy_name|vacancy_url|employer_name|resume_title|resume_url"
                    r"|first_name|last_name|phone|email)\)s", "", text)
    if "%" in chisto:
        beda.append("знак % - написать «процентов» или %%")
    if text.count("{") != text.count("}"):
        beda.append("непарные фигурные скобки { }")
    return beda


def stop_regex(cfg):
    """Стоп-слова для текста писем во входящих. \\b - начало слова:
    без него «крипт» ловил «скрипт», «трейд» - «Интертрейд»."""
    slova = [re.escape(w.strip('"*').lower()) for w in cfg.get("stop_slova") or [] if w.strip('"*')]
    return re.compile(r"\b(" + "|".join(slova) + ")", re.I) if slova else None
