# Проверка: вывод Автопилота, перехваченный оболочкой (PowerShell, Git Bash),
# читается по-русски. Аргумент - файл с выводом «ap.py pomosh».
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # как в ap.py
t = open(sys.argv[1], "rb").read()
for kod in ("utf-8-sig", "utf-16"):
    try:
        tekst = t.decode(kod)
        break
    except UnicodeDecodeError:
        continue
else:
    tekst = ""
ok = "Команды Автопилота" in tekst
print(("OK    " if ok else "СБОЙ  ") + "русский текст читается: " + repr(tekst[:40]))
sys.exit(0 if ok else 1)
