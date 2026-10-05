# Утренний отчёт: сколько ушло, кто пригласил, кто написал. Следом - разбор
# входящих и сторож. Запускается расписанием каждое утро.
import sys, datetime
from common import DANNYE, api, pisat_fail, notify
import vhodyashchie, storozh


def main():
    segodnya = datetime.date.today()
    s = str(segodnya - datetime.timedelta(days=1))
    data = api("/negotiations", per_page=100)
    items = data.get("items", [])

    ushlo, priglasheniya, otkazy, otvety = [], [], [], []
    for n in items:
        v = n.get("vacancy") or {}
        stroka = f"{(v.get('name') or '?')[:46]} | {((v.get('employer') or {}).get('name') or '?')[:26]}"
        st = (n.get("state") or {}).get("id") or ""
        if st == "invitation":
            priglasheniya.append(stroka)
        elif st == "discard":
            otkazy.append(stroka)
        elif n.get("has_new_messages"):
            otvety.append(stroka)
        if (n.get("created_at") or "")[:10] >= s:
            ushlo.append(stroka)

    L = []
    trevoga = DANNYE / "ТРЕВОГА.txt"
    if trevoga.exists():
        L += ["!!! ЕСТЬ ПРОБЛЕМА, СМОТРИ НИЖЕ !!!", trevoga.read_text(encoding="utf-8"), ""]
    L += [f"ОТЧЁТ ПО ОТКЛИКАМ, {segodnya:%d.%m.%Y}", "=" * 52,
          f"Всего откликов в кабинете: {data.get('found', '?')}",
          f"Отправлено за сутки: {len(ushlo)}", ""]
    if priglasheniya:
        L.append(f"ПРИГЛАШЕНИЯ ({len(priglasheniya)}) - смотреть первым делом:")
        L += ["  + " + r for r in priglasheniya] + [""]
    if otvety:
        L.append(f"НОВЫЕ СООБЩЕНИЯ ОТ РАБОТОДАТЕЛЕЙ ({len(otvety)}) - подробно в ВХОДЯЩИЕ.txt:")
        L += ["  ! " + r for r in otvety[:15]] + [""]
    if ushlo:
        L.append("Ушло за сутки:")
        L += ["  . " + r for r in ushlo[:30]] + [""]
    L += [f"Отказов в последних 100 откликах: {len(otkazy)}", "",
          "Кабинет: https://hh.ru/applicant/negotiations"]
    text = "\n".join(L)
    (DANNYE / "otchety").mkdir(exist_ok=True)
    (DANNYE / "otchety" / f"{segodnya}.txt").write_text(text, encoding="utf-8")
    pisat_fail("ОТЧЁТ.txt", text)
    print(text)
    notify(f"Отклики: {len(ushlo)} за сутки",
           f"Приглашений: {len(priglasheniya)}" if priglasheniya else "Приглашений пока нет")

    for modul in (vhodyashchie, storozh):
        try:
            modul.main()
        except Exception as e:      # отчёт не должен падать из-за соседа
            print(f"{modul.__name__}: ошибка {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
