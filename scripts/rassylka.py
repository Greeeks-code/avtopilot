# Рассылка откликов на hh.ru. Запускается расписанием 2 раза в день.
# В чате ИИ НЕ запускать: прогон идёт до нескольких часов и оборвётся.
# Для проверки из чата - «ap.py proba»: пробный прогон без отправки, одна страница.
import sys, json, math, time, datetime
from common import (DANNYE, ISTORIYA, zagruzit, hh, pisat_log, log_segodnya,
                    pisat_fail, notify, zapros_bloka, proverit_pismo)


def otpravleno_segodnya():
    p = log_segodnya()
    return p.read_text(encoding="utf-8").count("📨") if p.exists() else 0


def argumenty(cfg, blok, skolko, proba):
    a = ["apply-vacancies", "--resume-id", cfg["rezume_id"],
         "--letter-file", str(DANNYE / blok["pismo"]), "--force-message", "--skip-tests",
         "--order-by", "publication_time",
         "--total-pages", "1" if proba else str(cfg.get("stranits", 3)),
         "--per-page", "20" if proba else str(cfg.get("na_stranitse", 50)),
         "--max-responses", str(skolko)]
    if blok.get("roli"):
        a += ["--professional-role", *blok["roli"]]
    if cfg.get("format_raboty"):
        a += ["--work-format", *cfg["format_raboty"]]
    if cfg.get("regiony"):
        a += ["--area", *cfg["regiony"]]
    if cfg.get("opyt"):                      # hh принимает только одно значение
        a += ["--experience", cfg["opyt"]]
    if cfg.get("zarplata_ot"):
        a += ["--salary", str(cfg["zarplata_ot"]), "--currency", cfg.get("valyuta") or "RUR"]
    z = zapros_bloka(cfg, blok)
    if z:
        a += ["--search", z]
    if proba:
        a += ["--dry-run"]
    return a


def main(proba=None):
    if proba is None:
        proba = "--proba" in sys.argv
    cfg = zagruzit()
    for k in ("rezume_id", "bloki"):
        if not cfg.get(k):
            sys.exit(f"В настройках не заполнено «{k}» - вернись к анкете.")
    for b in cfg["bloki"]:
        p = DANNYE / b["pismo"]
        beda = proverit_pismo(p.read_text(encoding="utf-8")) if p.exists() else ["нет файла"]
        if beda:
            t = f"Письмо блока «{b['nazvanie']}» ({b['pismo']}): {'; '.join(beda)}. Скажи ИИ «поправь письмо»."
            pisat_fail("ТРЕВОГА.txt", t)
            notify("Рассылка не запущена", t[:120])
            sys.exit(t)

    start = datetime.datetime.now()
    pisat_log(f"=== {start:%Y-%m-%d %H:%M} запуск{' (проба, без отправки)' if proba else ''} ===")

    if not proba:
        r = hh("refresh-token", timeout=120)
        pisat_log(r.stdout + r.stderr)
    r = hh("whoami", timeout=120)
    pisat_log(r.stdout + r.stderr)
    if r.returncode != 0:
        pisat_log("ВХОД В HH ИСТЁК - нужен повторный вход")
        pisat_fail("ТРЕВОГА.txt", "Вход в hh истёк. Открой ИИ в папке avtopilot и скажи: «войди в hh».")
        notify("Отклики остановились", "Нужно заново войти в hh: скажи ИИ «войди в hh»")
        return 1
    if not proba:
        r = hh("update-resumes", timeout=300)   # поднять резюме в поиске
        pisat_log(r.stdout + r.stderr)

    limit = int(cfg.get("otklikov_v_den", 40))
    ostalos = limit - otpravleno_segodnya()
    if ostalos <= 0 and not proba:
        pisat_log(f"Дневной лимит {limit} уже выбран, сегодня больше не отправляем.")
        return 0
    zakhodov = max(1, len(cfg.get("vremya_zakhodov") or [1]))
    na_blok = max(1, math.ceil(limit / (zakhodov * len(cfg["bloki"]))))

    itog = {"data": str(start.date()), "vremya": f"{start:%H:%M}", "proba": proba,
            "otpravleno": 0, "kapcha": 0, "oshibki": 0, "bloki": []}
    for n, blok in enumerate(cfg["bloki"]):
        skolko = min(na_blok, ostalos) if not proba else na_blok
        if skolko <= 0:
            break
        pisat_log(f"--- {blok['nazvanie']} ---")
        r = hh(*argumenty(cfg, blok, skolko, proba), timeout=4 * 3600)
        out = r.stdout + r.stderr
        pisat_log(out)
        b = {"nazvanie": blok["nazvanie"], "otpravleno": out.count("📨"),
             "kapcha": out.count("Требуется капча"),
             "oshibki": out.count("Traceback") + out.count("[E]")}
        itog["bloki"].append(b)
        for k in ("otpravleno", "kapcha", "oshibki"):
            itog[k] += b[k]
        ostalos -= b["otpravleno"]
        if n < len(cfg["bloki"]) - 1 and not proba:
            time.sleep(int(cfg.get("pauza_mezhdu_blokami_sek", 90)))

    pisat_log(f"ИТОГ: отправлено {itog['otpravleno']}, капча {itog['kapcha']}, "
              f"ошибок {itog['oshibki']}")
    pisat_log(f"=== {datetime.datetime.now():%Y-%m-%d %H:%M} конец ===")

    if not proba:   # история для сторожа: по ней он видит капчу и провалы
        try:
            ist = json.loads(ISTORIYA.read_text(encoding="utf-8"))
        except Exception:
            ist = []
        ist = (ist + [itog])[-60:]
        ISTORIYA.write_text(json.dumps(ist, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(itog, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
