# Сторож: каждое утро проверяет, что рассылка работает честно, пишет СОСТОЯНИЕ.txt.
# Известные поломки чинит сам, если режим ИИ это разрешает; остальное кладёт
# в ТРЕВОГА.txt - ИИ прочитает её при следующем открытии (AGENTS.md).
# Урок автора: сторож 13 дней писал «в логе капча», и никто не реагировал.
# Поэтому каждая проблема здесь - со следующим шагом, а не просто строкой.
import sys, json, datetime
from common import DANNYE, ISTORIYA, zagruzit, api, pisat_fail, notify, proverit_pismo
import raspisanie


def main():
    cfg = zagruzit()
    rezhim = cfg.get("rezhim_ii", "izvestnoe_sam")
    sam_chinit = rezhim in ("izvestnoe_sam", "vse_sam")
    problemy, ok, sdelano = [], [], []

    me = api("/me")
    if me.get("id"):
        ok.append("вход в hh работает")
    else:
        problemy.append("ВХОД В HH ИСТЁК. Шаг: скажи ИИ «войди в hh».")

    r = api(f"/resumes/{cfg.get('rezume_id')}")
    st = (r.get("status") or {}).get("id")
    if st == "published":
        ok.append(f"резюме опубликовано: {r.get('title')}")
    else:
        problemy.append(f"РЕЗЮМЕ НЕ ОПУБЛИКОВАНО (статус {st}), отклики уходят впустую. "
                        "Шаг: открой резюме на hh.ru и опубликуй, или скажи ИИ «проверь резюме».")

    for b in cfg.get("bloki", []):
        p = DANNYE / b["pismo"]
        beda = proverit_pismo(p.read_text(encoding="utf-8")) if p.exists() else ["нет файла"]
        if beda:
            problemy.append(f"Письмо для «{b['nazvanie']}»: {'; '.join(beda)}. Шаг: скажи ИИ «поправь письмо».")

    try:
        ist = json.loads(ISTORIYA.read_text(encoding="utf-8"))
    except Exception:
        ist = []
    vchera = str(datetime.date.today() - datetime.timedelta(days=1))
    sutki = [x for x in ist if x["data"] >= vchera]
    if not ist:
        problemy.append("Рассылка ещё ни разу не отработала по расписанию. "
                        "Если установка была вчера или раньше - компьютер был выключен в это время.")
    elif not sutki:
        problemy.append("ЗА СУТКИ НЕ БЫЛО НИ ОДНОГО ЗАПУСКА. Компьютер был выключен "
                        "(спать можно, выключать нельзя) или сломалось расписание.")
    else:
        otpr = sum(x["otpravleno"] for x in sutki)
        ok.append(f"за сутки запусков {len(sutki)}, отправлено откликов {otpr}")
        if otpr == 0:
            problemy.append("ЗА СУТКИ НЕ УШЛО НИ ОДНОГО ОТКЛИКА. Шаг: скажи ИИ «что-то не работает».")

    posl = ist[-2:]
    if len(posl) == 2 and all(x["kapcha"] > 0 for x in posl):
        problemy.append("КАПЧА ДВА ЗАПУСКА ПОДРЯД: hh просит доказать, что ты не бот, "
                        "и рассылка встаёт. Проверенного решения пока нет - ЕСЛИ-СЛОМАЛОСЬ.md, раздел «Капча».")
    if any(x.get("oshibki") for x in posl):
        problemy.append("В последних запусках ошибки. Шаг: скажи ИИ «что-то не работает» - он прочитает журнал.")

    net = raspisanie.proverit(cfg)
    if not net:
        ok.append("расписание на месте")
    elif sam_chinit:
        raspisanie.ustanovit(cfg)
        sdelano.append(f"расписание было потеряно ({', '.join(net)}) - восстановлено")
    else:
        problemy.append(f"РАСПИСАНИЕ ПОТЕРЯНО: {', '.join(net)}. Шаг: скажи ИИ «восстанови расписание».")

    stamp = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    L = [f"ПРОВЕРКА, {stamp}", "=" * 50]
    if problemy:
        L += [f"ПРОБЛЕМЫ ({len(problemy)}):"] + ["  ! " + p for p in problemy] + [""]
    if sdelano:
        L += ["ПОЧИНЕНО САМО:"] + ["  * " + s for s in sdelano] + [""]
    L += ["В порядке:"] + ["  . " + o for o in ok]
    text = "\n".join(L)
    pisat_fail("СОСТОЯНИЕ.txt", text)
    print(text)

    if sdelano:   # журнал самостоятельных правок - человек всегда видит, что менялось
        with open(DANNYE / "ИЗМЕНЕНИЯ.md", "a", encoding="utf-8") as f:
            for s in sdelano:
                f.write(f"- {stamp} сторож: {s}\n")
    trevoga = DANNYE / "ТРЕВОГА.txt"
    if problemy:
        pisat_fail("ТРЕВОГА.txt", text)
        notify(f"Автопилот: проблем {len(problemy)}", problemy[0][:120])
    elif trevoga.exists():
        trevoga.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
