# Проверка установки без входа в hh. Запускается на чистых Windows и Mac
# в GitHub Actions (.github/workflows/proverka.yml) после каждой правки.
# Идёт тем же путём, что ИИ человека по УСТАНОВКА.md.
import os, sys, json, time, subprocess, platform
from pathlib import Path

HOME = Path.home()
KOD = HOME / "avtopilot"
DANNYE = HOME / "avtopilot-dannye"
WIN = platform.system() == "Windows"
UV = str(HOME / ".local" / "bin" / ("uv.exe" if WIN else "uv"))
oshibki = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ap(*a, timeout=900):
    r = subprocess.run([UV, "run", "--no-project", "--python", "3.12", str(KOD / "ap.py"), *a],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    print(f"\n$ ap.py {' '.join(a)}  -> код {r.returncode}\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
    return r


def check(uslovie, chto):
    print(("OK    " if uslovie else "СБОЙ  ") + chto)
    if not uslovie:
        oshibki.append(chto)


print(f"Система: {platform.system()} {platform.release()}, папка: {KOD}")

for f in ["УСТАНОВКА.md", "ПОЧЕМУ.md", "ЕСЛИ-СЛОМАЛОСЬ.md", "AGENTS.md", "README.md",
          "shablony/ХОД-УСТАНОВКИ.md", "shablony/nastroiki.json"]:
    check((KOD / f).exists(), f"после распаковки на месте {f}")

r = ap("pomosh")
check("Команды Автопилота" in r.stdout, "pomosh печатает по-русски")

r = ap("sozdat")
check((DANNYE / "nastroiki.json").exists(), "sozdat создал папку данных и настройки")

r = ap("proverka")
check("OK        инструмент hh" in r.stdout, "инструмент hh скачивается и запускается")
check("нет входа в hh" in r.stdout, "proverka честно говорит, что входа нет")

sys.path.insert(0, str(KOD / "scripts"))
from common import zapros_bloka, proverit_pismo, notify   # noqa: E402
check(proverit_pismo("Здравствуйте! " + "а" * 250 + " рост на 30%") != [], "ловит % в письме")
check(proverit_pismo("Здравствуйте! " + "а" * 250 + " 30 процентов, %(vacancy_name)s") == [], "чистое письмо проходит")
check(zapros_bloka({"stop_slova": ["крипт*", "холодные звонки"]}, {"roli": ["110"]})
      == 'NOT (крипт* OR "холодные звонки")', "стоп-слова уходят в поисковый запрос")

for k in (("roli", "ассистент"), ("gorod", "Москва")):   # справочники hh: с адреса дата-центра могут не ответить
    ap(*k, timeout=300)

cfg = json.loads((DANNYE / "nastroiki.json").read_text(encoding="utf-8"))
cfg.update({"imya": "citest", "rezhim_ii": "tolko_predlagaet", "rezume_id": "test",
            "bloki": [{"nazvanie": "Тест", "roli": ["110"], "zapros": "",
                       "isklyuchit_v_nazvanii": [], "pismo": "pisma/test.txt"}]})
(DANNYE / "nastroiki.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
(DANNYE / "pisma").mkdir(exist_ok=True)
(DANNYE / "pisma" / "test.txt").write_text("Здравствуйте! " + "Проверка письма. " * 20, encoding="utf-8")

r = ap("raspisanie", "ustanovit")
check(r.returncode == 0, "расписание ставится")
r = ap("raspisanie")
check("на месте" in r.stdout, "расписание видно в системе")
if WIN:
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "Get-ScheduledTask -TaskName 'Avtopilot-citest-*' | ForEach-Object { "
                         "$_.TaskName + ' | ' + $_.Actions[0].Execute + ' ' + $_.Actions[0].Arguments "
                         "+ ' | wake=' + $_.Settings.WakeToRun + ' | triggers=' + $_.Triggers.Count }"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(ps.stdout, ps.stderr)
    check("wake=True" in ps.stdout, "задача будит спящий компьютер")
    check("--gui-script" in ps.stdout, "задача запускается без чёрного окна")
    check("triggers=2" in ps.stdout, "у рассылки два захода в день")

# Запуск задачи из расписания: без входа в hh рассылка должна сама написать ТРЕВОГА.txt.
# Так проверяем, что задача стартует, находит uv, программу и папку данных.
r = ap("raspisanie", "zapustit")
check(r.returncode == 0, "задача из расписания запускается")
trevoga = DANNYE / "ТРЕВОГА.txt"
for _ in range(60):
    if trevoga.exists():
        break
    time.sleep(5)
check(trevoga.exists(), "задача отработала по расписанию и нашла папку данных (ТРЕВОГА о входе)")
if trevoga.exists():
    print(trevoga.read_text(encoding="utf-8"))
for p in sorted((DANNYE / "log").glob("*.log")):
    print(f"--- {p.name}\n{p.read_text(encoding='utf-8', errors='replace')[-1500:]}")

ap("raspisanie", "udalit")
r = ap("raspisanie")
check("Нет задач" in r.stdout, "расписание снимается полностью")

r = ap("ustanovit-hh", timeout=1800)
check("Готово" in r.stdout, "браузер для входа в hh ставится")

notify("Автопилот", "Проверка уведомления")   # не должно уронить скрипт
check(True, "уведомление не роняет программу")

print("\n" + ("ВСЁ ПРОШЛО" if not oshibki else f"СБОЕВ: {len(oshibki)}\n- " + "\n- ".join(oshibki)))
sys.exit(1 if oshibki else 0)
