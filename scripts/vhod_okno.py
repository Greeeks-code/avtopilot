# Вход в hh в обычном окне браузера, а не в «экране телефона».
# hh-applicant-tool 1.9.4 открывает вход как телефон Galaxy A55: экран 480x1040
# с увеличением 2.25. На ноутбуке с масштабом Windows 125% такой «телефон» выше
# окна, капча при входе уезжает за нижний край, и прокрутить её нельзя
# (найдено при установке на Windows 13.10.2026, вход занял 35 минут).
# Здесь размеры телефона убираются - страница подстраивается под окно.
# Запуск: ap.py vhod (сам по себе не нужен).
import sys
from playwright.async_api import Browser

_new_context = Browser.new_context


async def new_context(self, **kw):
    for k in ("viewport", "screen", "device_scale_factor", "is_mobile", "has_touch"):
        kw.pop(k, None)
    kw["no_viewport"] = True
    return await _new_context(self, **kw)


Browser.new_context = new_context

from hh_applicant_tool.main import main

sys.exit(main())
