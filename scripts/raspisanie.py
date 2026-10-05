# Расписание: Mac - launchd, Windows - Планировщик заданий.
# Компьютер может спать: Mac выполнит пропущенное при пробуждении, Windows
# разбудит компьютер сам (WakeToRun) или выполнит при первой возможности.
# Выключенный компьютер не запустит ничего - облака нет сознательно (ПОЧЕМУ.md).
import os, sys, subprocess, plistlib
from pathlib import Path
from common import KOD, DANNYE, LOG, MAC, WIN, BEZ_OKNA, uv_bin


def zadachi(cfg):
    return {"rassylka": cfg.get("vremya_zakhodov") or ["09:10", "16:00"],
            "otchet": [cfg.get("vremya_otcheta") or "09:00"]}


def _imya(cfg):
    return "".join(c for c in (cfg.get("imya") or "user").lower() if c.isalnum()) or "user"


def metka(cfg, z):
    return f"ru.avtopilot.{_imya(cfg)}.{z}" if MAC else f"Avtopilot-{_imya(cfg)}-{z}"


def argumenty(z):
    a = ["run", "--no-project", "--python", "3.12"]
    if WIN:
        a.append("--gui-script")   # без чёрного окна: его закрытие убило бы рассылку
    return a + [str(KOD / "ap.py"), "--dannye", str(DANNYE), z]


def ustanovit(cfg):
    LOG.mkdir(parents=True, exist_ok=True)
    for z, vremya in zadachi(cfg).items():
        if MAC:
            m = metka(cfg, z)
            plist = Path.home() / "Library" / "LaunchAgents" / f"{m}.plist"
            plist.parent.mkdir(parents=True, exist_ok=True)
            with open(plist, "wb") as f:
                plistlib.dump({
                    "Label": m,
                    "ProgramArguments": [uv_bin(), *argumenty(z)],
                    "StartCalendarInterval": [{"Hour": int(t.split(":")[0]), "Minute": int(t.split(":")[1])}
                                              for t in vremya],
                    "EnvironmentVariables": {"PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:"
                                                     + str(Path.home() / ".local" / "bin")},
                    "StandardOutPath": str(LOG / f"launchd-{z}.log"),
                    "StandardErrorPath": str(LOG / f"launchd-{z}.log"),
                }, f)
            uid = os.getuid()
            subprocess.run(["launchctl", "bootout", f"gui/{uid}/{m}"], capture_output=True)
            r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True, text=True)
            if r.returncode != 0:
                subprocess.run(["launchctl", "load", "-w", str(plist)], capture_output=True)
        elif WIN:
            def q(s):
                return "'" + str(s).replace("'", "''") + "'"
            arg = " ".join(f'"{x}"' if " " in x or "\\" in x else x for x in argumenty(z))
            trig = ", ".join(f"(New-ScheduledTaskTrigger -Daily -At {t})" for t in vremya)
            ps = (f"$a = New-ScheduledTaskAction -Execute {q(uv_bin())} -Argument {q(arg)};"
                  f"$t = @({trig});"
                  "$s = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries "
                  "-DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 6);"
                  f"Register-ScheduledTask -TaskName {q(metka(cfg, z))} -Action $a -Trigger $t -Settings $s -Force | Out-Null")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, **BEZ_OKNA)
            if r.returncode != 0:
                print(r.stdout, r.stderr)
        else:
            sys.exit("Расписание сделано для Mac и Windows.")
    net = proverit(cfg)
    print("Расписание установлено." if not net else f"Не встали задачи: {', '.join(net)}")
    return not net


def proverit(cfg):
    """Список задач, которых нет в системе (пусто - всё на месте)."""
    net = []
    if MAC:
        spisok = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
        net = [z for z in zadachi(cfg) if metka(cfg, z) not in spisok]
    elif WIN:
        for z in zadachi(cfg):
            r = subprocess.run(["schtasks", "/query", "/tn", metka(cfg, z)], capture_output=True, **BEZ_OKNA)
            if r.returncode != 0:
                net.append(z)
    return net


def zapustit(cfg, z="rassylka"):
    """Запуск задачи расписания прямо сейчас, в фоне. Так первую рассылку можно
    запустить из чата: она пойдёт отдельно от ИИ и не оборвётся."""
    if MAC:
        r = subprocess.run(["launchctl", "kickstart", f"gui/{os.getuid()}/{metka(cfg, z)}"],
                           capture_output=True, text=True)
    elif WIN:
        r = subprocess.run(["schtasks", "/run", "/tn", metka(cfg, z)], capture_output=True, text=True, **BEZ_OKNA)
    else:
        return False
    print("Запущено в фоне. Ход - в журнале log/<сегодня>.log." if r.returncode == 0
          else f"Не запустилось: {r.stdout}{r.stderr}")
    return r.returncode == 0


def udalit(cfg):
    for z in zadachi(cfg):
        m = metka(cfg, z)
        if MAC:
            plist = Path.home() / "Library" / "LaunchAgents" / f"{m}.plist"
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{m}"], capture_output=True)
            if plist.exists():
                plist.unlink()
        elif WIN:
            subprocess.run(["schtasks", "/delete", "/tn", m, "/f"], capture_output=True, **BEZ_OKNA)
    print("Расписание удалено.")
