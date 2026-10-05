#!/usr/bin/env python3
# Автопилот поиска работы - одна точка входа для всех команд.
# Запуск:  uv run --no-project --python 3.12 ~/avtopilot/ap.py <команда>
import os, sys
from pathlib import Path

# Windows пишет вывод в старой кодировке (cp1252/cp1251): русские буквы и значки
# роняли программу, как только вывод читает ИИ, а не окно (найдено автопроверкой).
for _potok in (sys.stdout, sys.stderr):
    try:
        _potok.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

argv = sys.argv[1:]
if "--dannye" in argv:            # расписание передаёт папку данных явно
    i = argv.index("--dannye")
    os.environ["AVTOPILOT_DANNYE"] = argv[i + 1]
    del argv[i:i + 2]
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

KOMANDY = """Команды Автопилота:
  sozdat          папка данных и шаблон настроек
  ustanovit-hh    браузер для входа в hh (один раз)
  vhod            вход в hh - человек входит сам в окне браузера
  rezume          резюме человека на hh: id, название, статус
  rezume-pokazat <id>                резюме целиком - проверить на дыры
  rezume-sozdat <файл> [--publish]   резюме на hh из файла (без --publish - проверка)
  roli <слово>    найти id профессиональных ролей hh
  gorod <слово>   найти id города или страны hh
  poisk           что найдёт рассылка: число вакансий за неделю и примеры
  proba           пробный прогон без отправки (можно из чата)
  rassylka        настоящая рассылка (только расписанием, в чате оборвётся)
  otchet          утренний отчёт + разбор входящих + сторож
  vhodyashchie    только разбор входящих
  storozh         только проверка
  raspisanie [ustanovit|udalit|proverit|zapustit]   zapustit - рассылка сейчас, в фоне
  proverka        всё ли на месте
  dlya-avtora     отчёт автору без личных данных"""


def main():
    if not argv or argv[0] in ("-h", "--help", "pomosh"):
        print(KOMANDY)
        return 0
    k, rest = argv[0], argv[1:]
    import nastroika
    prostye = {"sozdat": nastroika.sozdat, "proverka": nastroika.proverka,
               "ustanovit-hh": nastroika.ustanovit_hh, "vhod": nastroika.vhod,
               "rezume": nastroika.rezume, "poisk": nastroika.poisk,
               "dlya-avtora": nastroika.dlya_avtora}
    if k in prostye:
        return prostye[k]() or 0
    if k in ("roli", "gorod"):
        return getattr(nastroika, k)(" ".join(rest)) or 0
    if k == "rezume-sozdat":
        return nastroika.rezume_sozdat(rest) or 0
    if k == "rezume-pokazat":
        return nastroika.rezume_pokazat(" ".join(rest)) or 0
    if k in ("proba", "rassylka"):
        import rassylka
        return rassylka.main(proba=(k == "proba"))
    if k in ("otchet", "vhodyashchie", "storozh"):
        return __import__(k).main()
    if k == "raspisanie":
        import raspisanie
        from common import zagruzit
        cfg = zagruzit()
        deistvie = rest[0] if rest else "proverit"
        if deistvie == "ustanovit":
            return 0 if raspisanie.ustanovit(cfg) else 1
        if deistvie == "udalit":
            raspisanie.udalit(cfg)
            return 0
        if deistvie == "zapustit":
            return 0 if raspisanie.zapustit(cfg) else 1
        net = raspisanie.proverit(cfg)
        print("Расписание на месте." if not net else f"Нет задач: {', '.join(net)}")
        return 0 if not net else 1
    print(f"Нет команды «{k}».\n\n{KOMANDY}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
