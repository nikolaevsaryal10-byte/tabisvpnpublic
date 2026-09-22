# -*- coding: utf-8 -*-
"""
Tabis VPN Windows Installer (setup.exe)
Swiss Minimalist Setup Wizard
"""
import os
import sys
import shutil
import winreg
import ctypes
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

APP_NAME = "Tabis VPN"
APP_VERSION = "2.4.0"
APP_PUBLISHER = "Tabis VPN"
APP_URL = "https://tabisvpn.site"

DEFAULT_INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "TabisVPN")

def get_base_dir():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(os.path.dirname(__file__))

BASE_DIR = get_base_dir()

def create_shortcut(target_path, shortcut_path, description="Tabis VPN", icon_path=None):
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = target_path
        shortcut.WorkingDirectory = os.path.dirname(target_path)
        shortcut.Description = description
        if icon_path and os.path.exists(icon_path):
            shortcut.IconLocation = f"{icon_path},0"
        else:
            shortcut.IconLocation = f"{target_path},0"
        shortcut.save()
        return True
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False

def register_uninstaller(install_dir, exe_path):
    try:
        uninstall_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TabisVPN"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_key) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, f"{APP_NAME} {APP_VERSION}")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, exe_path)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{exe_path}" --uninstall')
            winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{exe_path}" --uninstall /silent')
            winreg.SetValueEx(key, "HelpLink", 0, winreg.REG_SZ, APP_URL)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception as e:
        print(f"Failed to register uninstaller: {e}")

def set_autostart_reg(exe_path, enable=True):
    try:
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_WRITE) as key:
            if enable:
                winreg.SetValueEx(key, "TabisVPN", 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                try:
                    winreg.DeleteValue(key, "TabisVPN")
                except FileNotFoundError:
                    pass
    except Exception as e:
        print(f"Failed to set autostart: {e}")

def kill_running_instances():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "TabisVPN.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def perform_install(target_dir, autostart=True, desktop_shortcut=True, launch_now=True, silent=False):
    try:
        kill_running_instances()
        os.makedirs(target_dir, exist_ok=True)

        source_exe = os.path.join(BASE_DIR, "TabisVPN.exe")
        if not os.path.exists(source_exe):
            source_exe = os.path.join(BASE_DIR, "dist", "TabisVPN.exe")

        dest_exe = os.path.join(target_dir, "TabisVPN.exe")
        shutil.copy2(source_exe, dest_exe)

        # Copy icon if available
        icon_src = os.path.join(BASE_DIR, "ui", "icon.ico")
        icon_dest = os.path.join(target_dir, "icon.ico")
        if os.path.exists(icon_src):
            try:
                shutil.copy2(icon_src, icon_dest)
            except Exception:
                pass

        # Autostart
        if autostart:
            set_autostart_reg(dest_exe, True)

        # Start Menu Shortcut
        start_menu_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
        start_menu_lnk = os.path.join(start_menu_dir, "Tabis VPN.lnk")
        create_shortcut(dest_exe, start_menu_lnk, "Tabis VPN Client", icon_dest if os.path.exists(icon_dest) else dest_exe)

        # Desktop Shortcut
        if desktop_shortcut:
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            desktop_lnk = os.path.join(desktop_dir, "Tabis VPN.lnk")
            create_shortcut(dest_exe, desktop_lnk, "Tabis VPN Client", icon_dest if os.path.exists(icon_dest) else dest_exe)

        # Register in Windows Programs & Features
        register_uninstaller(target_dir, dest_exe)

        # Launch
        if launch_now:
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen([dest_exe], cwd=target_dir)

        return True
    except Exception as e:
        if not silent:
            ctypes.windll.user32.MessageBoxW(0, f"Ошибка установки:\n{e}", "Tabis VPN Installer", 0x10)
        return False

def run_gui():
    root = tk.Tk()
    root.title("Установка Tabis VPN")
    root.geometry("460x520")
    root.resizable(False, False)
    root.configure(bg="#F9F9F7")

    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 460) // 2
    y = (root.winfo_screenheight() - 520) // 2
    root.geometry(f"+{x}+{y}")

    # Set icon if exists
    ico_path = os.path.join(BASE_DIR, "ui", "icon.ico")
    if os.path.exists(ico_path):
        try:
            root.iconbitmap(ico_path)
        except Exception:
            pass

    # Top banner / header
    header_frame = tk.Frame(root, bg="#121416", height=100)
    header_frame.pack(fill="x")
    header_frame.pack_propagate(False)

    # Logo image in header
    logo_img_label = None
    logo_path = os.path.join(BASE_DIR, "ui", "logo.png")
    if os.path.exists(logo_path):
        try:
            pil_img = Image.open(logo_path).resize((52, 52), Image.LANCZOS)
            tk_logo = ImageTk.PhotoImage(pil_img)
            logo_img_label = tk.Label(header_frame, image=tk_logo, bg="#121416")
            logo_img_label.image = tk_logo
            logo_img_label.pack(side="left", padx=(20, 10))
        except Exception:
            pass

    title_frame = tk.Frame(header_frame, bg="#121416")
    title_frame.pack(side="left", fill="both", expand=True, pady=18)

    title_lbl = tk.Label(title_frame, text="TABIS VPN", font=("Inter", 16, "bold"), fg="#FFFFFF", bg="#121416")
    title_lbl.pack(anchor="w")

    ver_lbl = tk.Label(title_frame, text=f"Версия {APP_VERSION} • Высокоскоростной VPN", font=("Segoe UI", 9), fg="#089AFF", bg="#121416")
    ver_lbl.pack(anchor="w")

    # Body frame
    body = tk.Frame(root, bg="#F9F9F7", padx=24, pady=20)
    body.pack(fill="both", expand=True)

    info_text = (
        "Tabis VPN защищает ваше интернет-соединение, используя современный "
        "протокол Hysteria 2 (QUIC/UDP) со скоростью до 300 Мбит/с."
    )
    info_lbl = tk.Label(body, text=info_text, font=("Segoe UI", 9), fg="#5E5E5F", bg="#F9F9F7", wraplength=410, justify="left")
    info_lbl.pack(anchor="w", pady=(0, 16))

    # Install location
    dir_frame = tk.LabelFrame(body, text=" Папка установки ", font=("Segoe UI", 9, "bold"), fg="#121416", bg="#F9F9F7", padx=10, pady=8)
    dir_frame.pack(fill="x", pady=(0, 16))

    dir_var = tk.StringVar(value=DEFAULT_INSTALL_DIR)
    dir_entry = tk.Entry(dir_frame, textvariable=dir_var, font=("Consolas", 9), bg="#FFFFFF", fg="#121416", relief="solid", bd=1)
    dir_entry.pack(fill="x")

    # Options checkboxes
    opts_frame = tk.LabelFrame(body, text=" Параметры ", font=("Segoe UI", 9, "bold"), fg="#121416", bg="#F9F9F7", padx=10, pady=8)
    opts_frame.pack(fill="x", pady=(0, 20))

    var_autostart = tk.BooleanVar(value=True)
    chk_auto = tk.Checkbutton(opts_frame, text="Запускать Tabis VPN при входе в Windows (рекомендуется)", variable=var_autostart, font=("Segoe UI", 9), bg="#F9F9F7", activebackground="#F9F9F7")
    chk_auto.pack(anchor="w", pady=2)

    var_desktop = tk.BooleanVar(value=True)
    chk_desk = tk.Checkbutton(opts_frame, text="Создать ярлык на Рабочем столе", variable=var_desktop, font=("Segoe UI", 9), bg="#F9F9F7", activebackground="#F9F9F7")
    chk_desk.pack(anchor="w", pady=2)

    var_launch = tk.BooleanVar(value=True)
    chk_launch = tk.Checkbutton(opts_frame, text="Запустить Tabis VPN после установки", variable=var_launch, font=("Segoe UI", 9), bg="#F9F9F7", activebackground="#F9F9F7")
    chk_launch.pack(anchor="w", pady=2)

    # Status / Progress label
    status_lbl = tk.Label(body, text="", font=("Segoe UI", 9), fg="#10B981", bg="#F9F9F7")
    status_lbl.pack(anchor="w", pady=(0, 10))

    # Action buttons
    btn_frame = tk.Frame(body, bg="#F9F9F7")
    btn_frame.pack(fill="x", side="bottom")

    def do_install_btn():
        install_btn.config(state="disabled", text="УСТАНОВКА...")
        status_lbl.config(text="Копирование файлов и настройка...", fg="#089AFF")
        root.update()

        target = dir_var.get().strip() or DEFAULT_INSTALL_DIR
        ok = perform_install(
            target_dir=target,
            autostart=var_autostart.get(),
            desktop_shortcut=var_desktop.get(),
            launch_now=var_launch.get(),
            silent=False
        )

        if ok:
            status_lbl.config(text="Установка успешно завершена!", fg="#10B981")
            install_btn.config(text="ГОТОВО", state="normal", command=root.destroy)
        else:
            status_lbl.config(text="Ошибка установки", fg="#E11D48")
            install_btn.config(state="normal", text="ПОВТОРИТЬ")

    install_btn = tk.Button(
        btn_frame,
        text="УСТАНОВИТЬ",
        font=("Segoe UI", 10, "bold"),
        bg="#089AFF",
        fg="#FFFFFF",
        activebackground="#0077CC",
        activeforeground="#FFFFFF",
        relief="flat",
        cursor="hand2",
        padx=20,
        pady=8,
        command=do_install_btn
    )
    install_btn.pack(side="right")

    cancel_btn = tk.Button(
        btn_frame,
        text="Отмена",
        font=("Segoe UI", 9),
        bg="#E8E8E6",
        fg="#121416",
        activebackground="#D0D0CE",
        relief="flat",
        cursor="hand2",
        padx=14,
        pady=8,
        command=root.destroy
    )
    cancel_btn.pack(side="right", padx=(0, 10))

    root.mainloop()

def main():
    # Silent install mode for auto-updater
    args = [a.lower() for a in sys.argv]
    if "/silent" in args or "/s" in args or "--silent" in args:
        target = DEFAULT_INSTALL_DIR
        perform_install(target_dir=target, autostart=True, desktop_shortcut=True, launch_now=True, silent=True)
        sys.exit(0)

    run_gui()

if __name__ == "__main__":
    main()
