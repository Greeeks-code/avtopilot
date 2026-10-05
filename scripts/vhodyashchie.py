# Разбор входящих: читает новые сообщения работодателей и делит их на то,
# что требует ответа человека, и на шум. Ничего не отправляет.
import sys, json, re, time, datetime
from common import DANNYE, zagruzit, api, pisat_fail, notify, stop_regex

SHABLON = [r"рассмотрим ваше резюме", r"если навыки и опыт подойдут", r"мы свяжемся с вами",
           r"спасибо за (ваш )?отклик[.!]?$", r"ваш отклик (получен|принят)", r"в ближайшее время"]
PORYADOK = ["ЗВОНОК", "АНКЕТА", "ТЕСТОВОЕ", "НАПОМИНАНИЕ", "ВОПРОС", "ПРОЧЕЕ"]


def klass(text, state):
    t = " ".join(text.split())
    tl = t.lower()
    if re.search(r"forms\.gle|docs\.google|survey|анкет|опросник|google\.com/forms", tl):
        return "АНКЕТА"
    if re.search(r"тестов(ое|ый)|пробное задание|выполнить задание", tl):
        return "ТЕСТОВОЕ"
    if state == "interview" or re.search(r"созвон|собеседовани|интервью|zoom|встреч|когда вам удобно|слот", tl):
        return "ЗВОНОК"
    if re.search(r"напомина|затерял|не получил(и)? ответ|ещё раз|еще раз", tl):
        return "НАПОМИНАНИЕ"
    if "?" in t or re.search(r"подскажите|расскажите|уточните|ответьте|напишите,", tl):
        return "ВОПРОС"
    if any(re.search(rx, tl) for rx in SHABLON) or len(t) < 120:
        return "ШАБЛОН"
    return "ПРОЧЕЕ"


def main():
    cfg = zagruzit()
    stop = stop_regex(cfg)

    kandidaty, page = [], 0
    while True:
        d = api("/negotiations", per_page=100, page=page)
        items = d.get("items", [])
        if not items:
            break
        kandidaty += [n for n in items if n.get("has_new_messages")]
        if page >= d.get("pages", 1) - 1 or page > 12:
            break
        page += 1

    otkazy = [n for n in kandidaty if (n.get("state") or {}).get("id") == "discard"]
    zhivye = [n for n in kandidaty if (n.get("state") or {}).get("id") != "discard"]

    # Отказы открываем - они становятся прочитанными и не висят в уведомлениях hh.
    for n in otkazy:
        api(f"/negotiations/{n['id']}/messages")
        time.sleep(0.5)

    # Открытие снимает пометку «новое», поэтому живые из прошлого разбора держим,
    # пока последнее слово за работодателем.
    fail = DANNYE / "vhodyashchie.json"
    try:
        proshlye = json.loads(fail.read_text(encoding="utf-8"))
    except Exception:
        proshlye = []
    uzhe = {n["id"] for n in zhivye}
    for r in proshlye:
        if r["id"] not in uzhe:
            zhivye.append({"id": r["id"], "state": {}, "vacancy": {"name": r["vakansiya"],
                           "employer": {"name": r["rabotodatel"]}, "alternate_url": r["ssylka"]}})

    rows, shum = [], 0
    for n in zhivye:
        v = n.get("vacancy") or {}
        vse = api(f"/negotiations/{n['id']}/messages").get("items", [])
        if vse and (vse[-1].get("author") or {}).get("participant_type") != "employer":
            continue   # человек уже ответил
        msgs = [x for x in vse if (x.get("author") or {}).get("participant_type") == "employer"]
        text = (msgs[-1].get("text") or "") if msgs else ""
        row = {"id": n["id"], "tip": klass(text, (n.get("state") or {}).get("id") or ""),
               "kogda": (msgs[-1].get("created_at") or "")[:10] if msgs else "",
               "vakansiya": v.get("name") or "?",
               "rabotodatel": (v.get("employer") or {}).get("name") or "?",
               "ssylka": v.get("alternate_url") or "",
               "chat": f"https://hh.ru/applicant/negotiations/item?id={n['id']}",
               "text": " ".join(text.split())}
        musor = stop and stop.search(f"{row['vakansiya']} {row['rabotodatel']} {row['text'][:400]}")
        if row["tip"] == "ШАБЛОН" or musor:
            shum += 1
        else:
            rows.append(row)

    rows.sort(key=lambda r: (PORYADOK.index(r["tip"]) if r["tip"] in PORYADOK else 9, r["kogda"]))
    fail.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    L = [f"ВХОДЯЩИЕ, {datetime.datetime.now():%d.%m.%Y %H:%M}", "=" * 52,
         f"Непрочитанных всего: {len(kandidaty)}",
         f"  отказы (помечены прочитанными): {len(otkazy)}",
         f"  шум (отписки и стоп-ниши): {shum}",
         f"  ТРЕБУЮТ ОТВЕТА: {len(rows)}", ""]
    for i, r in enumerate(rows, 1):
        L += [f"{i}. [{r['tip']}] {r['vakansiya'][:50]} | {r['rabotodatel'][:30]}  ({r['kogda']})",
              f"   {r['text'][:220]}", f"   {r['chat']}", ""]
    text = "\n".join(L)
    pisat_fail("ВХОДЯЩИЕ.txt", text)
    print(text)
    if rows:
        notify("Входящие разобраны", f"Требуют ответа: {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
