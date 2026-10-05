# Команды для установки и проверки. ИИ вызывает их по УСТАНОВКА.md.
import sys, json, re, shutil, platform, subprocess, datetime
from pathlib import Path
from common import (KOD, SHABLONY, DANNYE, NASTROIKI, LOG, ISTORIYA, VERSIYA, HH_VERSIYA, MAC, WIN,
                    ENV, BEZ_OKNA, uv_bin, hh, hh_komanda, api, zagruzit, zapros_bloka, filtry_poiska,
                    proverit_pismo)


def sozdat():
    """Папка данных и шаблон настроек. Ничего не затирает."""
    for d in ("hh", "log", "pisma", "otchety"):
        (DANNYE / d).mkdir(parents=True, exist_ok=True)
    if not NASTROIKI.exists():
        shutil.copy2(SHABLONY / "nastroiki.json", NASTROIKI)
    print(f"Папка данных: {DANNYE}")
    print(f"Настройки: {NASTROIKI}")


def proverka():
    """Всё ли на месте. Печатает по строке на пункт: OK или ПРОБЛЕМА со следующим шагом."""
    stroki = []

    def ok(t): stroki.append("OK        " + t)
    def bad(t): stroki.append("ПРОБЛЕМА  " + t)

    ok(f"Автопилот {VERSIYA}, {platform.system()} {platform.release()}, Python {platform.python_version()}")
    ok(f"uv: {uv_bin()}")
    if MAC and any(p in DANNYE.parts for p in ("Desktop", "Documents", "Downloads")):
        bad(f"данные лежат в {DANNYE} - на Mac расписание туда не пускают. Нужна папка в домашней.")
    if any(p in KOD.parts for p in ("Desktop", "Documents", "Downloads")) and MAC:
        bad(f"программа лежит в {KOD} - расписание туда не пустят. Перенеси в ~/avtopilot.")
    r = hh("--help", timeout=600)
    (ok if r.returncode == 0 else bad)(f"инструмент hh {HH_VERSIYA}" + ("" if r.returncode == 0 else f": {r.stderr[-200:]}"))
    if not NASTROIKI.exists():
        bad("нет настроек - выполни «ap.py sozdat»")
        print("\n".join(stroki)); return
    cfg = zagruzit()
    me = api("/me")
    if me.get("id"):
        ok(f"вход в hh: {me.get('first_name', '')} {me.get('last_name', '')}")
    else:
        bad("нет входа в hh - «ap.py vhod»")
    if cfg.get("rezume_id"):
        st = (api(f"/resumes/{cfg['rezume_id']}").get("status") or {}).get("id")
        (ok if st == "published" else bad)(f"резюме {cfg['rezume_id']}: статус {st}")
    else:
        bad("не выбрано резюме (rezume_id)")
    if not cfg.get("bloki"):
        bad("нет ни одного блока поиска")
    for b in cfg.get("bloki", []):
        p = DANNYE / b.get("pismo", "")
        beda = proverit_pismo(p.read_text(encoding="utf-8")) if p.is_file() else [f"нет файла {b.get('pismo')}"]
        (ok if not beda else bad)(f"письмо блока «{b['nazvanie']}»" + (": " + "; ".join(beda) if beda else ""))
    for k in ("imya", "otklikov_v_den", "rezhim_ii"):
        if not cfg.get(k):
            bad(f"не заполнено «{k}» в настройках")
    import raspisanie
    net = raspisanie.proverit(cfg)
    (ok if not net else bad)("расписание" + ("" if not net else f": нет задач {', '.join(net)}"))
    print("\n".join(stroki))


def ustanovit_hh():
    """Браузер для входа в hh (ставится один раз, ~150 МБ)."""
    r = subprocess.run(hh_komanda("install"), env=ENV, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **BEZ_OKNA)
    vyvod = r.stdout + r.stderr
    print(vyvod[-1500:])
    # инструмент иногда пишет ошибку, но возвращает 0 - проверяем и текст
    if r.returncode != 0 or "[E]" in vyvod or "No module" in vyvod:
        print("Не получилось - смотри текст выше.")
        return 1
    print("Готово.")
    return 0


def vhod():
    """Откроется окно браузера с hh - человек входит сам. Пароль ИИ не видит."""
    print("Сейчас откроется окно hh.ru. Войди как обычно: телефон или почта, код из SMS.")
    print("Окно закроется само после входа. Ждём до 10 минут.")
    subprocess.run(hh_komanda("authorize", "--no-headless"), env=ENV, timeout=600, **BEZ_OKNA)
    me = api("/me")
    if me.get("id"):
        print(f"Вход выполнен: {me.get('first_name', '')} {me.get('last_name', '')}")
        return 0
    print("Вход не получился. Попробуй ещё раз: «ap.py vhod».")
    return 1


def rezume():
    d = api("/resumes/mine")
    items = d.get("items", [])
    if not items:
        print("Резюме на hh нет." if "_oshibka" not in d else f"Ошибка: {d['_oshibka']}")
    for r in items:
        st = (r.get("status") or {}).get("name") or (r.get("status") or {}).get("id")
        print(f"{r['id']} | {r.get('title')} | {st} | обновлено {(r.get('updated_at') or '')[:10]} | {r.get('alternate_url')}")


def roli(slovo):
    """Поиск профессиональных ролей hh по слову - их id идут в «roli» блока."""
    d = api("/professional_roles")
    slovo = slovo.lower()
    for c in d.get("categories", []):
        for r in c.get("roles", []):
            if slovo in r["name"].lower() or slovo in c["name"].lower():
                print(f"{r['id']:>4} | {r['name']}  ({c['name']})")


def rezume_pokazat(rid):
    """Резюме целиком - чтобы ИИ проверил его на дыры до того, как на него уйдут сотни откликов."""
    r = api(f"/resumes/{rid.strip()}")
    if "_oshibka" in r or not r.get("id"):
        sys.exit(f"Не открылось резюме {rid}: {r.get('_oshibka', r)}")
    print(f"Название: {r.get('title')}")
    print(f"Статус: {(r.get('status') or {}).get('name')} | видимость: {(r.get('access') or {}).get('type', {}).get('name')}")
    zp = r.get("salary") or {}
    print(f"Зарплата: {zp.get('amount', 'не указана')} {zp.get('currency', '')}")
    print(f"Город: {(r.get('area') or {}).get('name')}")
    print(f"Роли: {', '.join(x['name'] for x in r.get('professional_roles') or [])}")
    print(f"Навыки: {', '.join(r.get('skill_set') or []) or 'нет'}")
    print(f"\nО себе:\n{r.get('skills') or 'пусто'}\n\nОпыт:")
    for e in r.get("experience") or []:
        print(f"- {e.get('start')} - {e.get('end') or 'сейчас'} | {e.get('company')} | {e.get('position')}")
        print(f"  {(e.get('description') or '')[:400]}")
    for e in (r.get("education") or {}).get("primary") or []:
        print(f"Образование: {e.get('name')}, {e.get('organization') or ''} {e.get('year') or ''}")


def rezume_sozdat(argumenty):
    """Резюме на hh из файла по шаблону. Без --publish - только проверка, ничего не создаёт."""
    if not argumenty:
        sys.exit("Укажи файл резюме: ap.py rezume-sozdat <файл> [--publish]")
    put = str(Path(argumenty[0]).expanduser())
    r = hh("create-resume", put, "--publish" if "--publish" in argumenty else "--dry-run", timeout=300)
    print(r.stdout + r.stderr)
    if "--publish" in argumenty:
        print("Теперь найди id нового резюме: ap.py rezume")


def gorod(slovo):
    """id региона hh для «regiony» - если человек ищет не только удалёнку."""
    d = api("/suggests/areas", text=slovo)
    if not d.get("items"):
        print("Не нашлось. Попробуй страну или крупный город рядом.")
    for a in d.get("items", []):
        print(f"{a['id']:>6} | {a['text']}")


def poisk():
    """Что найдёт рассылка: сколько вакансий за 7 дней и 5 свежих по каждому блоку.
    Показать человеку и спросить: «на такие откликаемся?»"""
    cfg = zagruzit()
    for b in cfg.get("bloki", []):
        z = zapros_bloka(cfg, b)
        pary = filtry_poiska(cfg, b) + [("period", 7), ("per_page", 5), ("order_by", "publication_time")]
        if z:
            pary.append(("text", z))
            d = api("/vacancies", pary)
        else:
            d = api(f"/resumes/{cfg['rezume_id']}/similar_vacancies", pary)
        print(f"\n=== {b['nazvanie']}: за 7 дней {d.get('found', 'ошибка ' + str(d.get('_oshibka', ''))[:150])}")
        for v in d.get("items", []):
            zp = v.get("salary") or {}
            zp = f"{zp.get('from') or ''}-{zp.get('to') or ''} {zp.get('currency') or ''}".strip(" -") if zp else "з/п не указана"
            print(f"  - {v['name'][:60]} | {(v.get('employer') or {}).get('name', '')[:30]} | {zp}")
        if z:
            print(f"  запрос: {z[:300]}")


def dlya_avtora():
    """Отчёт для автора, когда ИИ не справился сам. Без паролей, токенов и личных данных."""
    try:
        cfg = zagruzit()
    except SystemExit:
        cfg = {}
    try:
        ist = json.loads(ISTORIYA.read_text(encoding="utf-8"))[-6:]
    except Exception:
        ist = []
    zhurnal = sorted(LOG.glob("20*.log"))[-2:] if LOG.exists() else []
    stroki = []
    for p in zhurnal:
        for s in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if re.search(r"\[E\]|\[W\]|Traceback|Error|ошибк|капч|ИТОГ|запуск|конец", s, re.I):
                stroki.append(f"{p.stem}: {s}")
    tekst = "\n".join(stroki[-60:])
    # вычищаем то, что может указать на человека или дать доступ
    tekst = re.sub(r"(state|token|code|key)=[^\s&]+", r"\1=***", tekst, flags=re.I)
    tekst = re.sub(r"https?://hh\.ru/resume/\w+", "hh.ru/resume/***", tekst)
    tekst = re.sub(r"\+?\d[\d\s\-()]{9,}\d", "***", tekst)
    tekst = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "***@***", tekst)
    sost = DANNYE / "СОСТОЯНИЕ.txt"
    khod = DANNYE / "ХОД-УСТАНОВКИ.md"
    otchet = "\n".join([
        f"ДЛЯ АВТОРА АВТОПИЛОТА, {datetime.datetime.now():%d.%m.%Y %H:%M}",
        f"Версия {VERSIYA}, hh-applicant-tool {HH_VERSIYA}, {platform.system()} {platform.release()}, "
        f"Python {platform.python_version()}",
        f"Блоков: {len(cfg.get('bloki', []))}, откликов в день: {cfg.get('otklikov_v_den')}, "
        f"режим ИИ: {cfg.get('rezhim_ii')}",
        "", "Ход установки:", khod.read_text(encoding="utf-8") if khod.exists() else "нет",
        "", "Последние запуски:", json.dumps(ist, ensure_ascii=False),
        "", "Состояние:", sost.read_text(encoding="utf-8") if sost.exists() else "нет",
        "", "Ошибки и итоги из журнала:", tekst or "нет"])
    (DANNYE / "ДЛЯ-АВТОРА.txt").write_text(otchet, encoding="utf-8")
    print(otchet)
    # Копия на рабочий стол - человеку проще всего найти и переслать её оттуда.
    # На Windows рабочий стол часто внутри OneDrive.
    home = Path.home()
    for stol in (home / "Desktop", home / "OneDrive" / "Desktop", home / "OneDrive" / "Рабочий стол"):
        if stol.is_dir():
            (stol / "ДЛЯ-АВТОРА-автопилот.txt").write_text(otchet, encoding="utf-8")
            print(f"\nФайл на рабочем столе: {stol / 'ДЛЯ-АВТОРА-автопилот.txt'} - перешли его автору.")
            break
    else:
        print(f"\nФайл: {DANNYE / 'ДЛЯ-АВТОРА.txt'} - перешли его автору.")
