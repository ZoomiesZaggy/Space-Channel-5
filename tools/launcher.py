"""Disc selection, personal builds and persistent player settings."""
import os
import json
import pathlib
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from player_config import ACTIONS, DEFAULTS, KEYS, PADS, load, save

ROOT = pathlib.Path(__file__).resolve().parents[1]

class Launcher:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title('Space Channel 5')
        self.window.geometry('720x650')
        self.path = ROOT / 'userdata/settings.ini'
        try:
            values = load(self.path)
        except (OSError, ValueError) as error:
            messagebox.showerror('Settings could not be loaded', str(error))
            values = dict(DEFAULTS)
        self.vars = {k: tk.StringVar(value=v) for k, v in values.items()}
        self.messages = queue.Queue()
        self.building = False
        self.game = None
        self.game_log = 'userdata/last-launch.log'
        self.steam_id = ''
        try:
            steam = json.loads((ROOT / 'userdata/steam-launch.json').read_text())
            value = str(steam.get('game_id', ''))
            if value.isdigit() and len(value) <= 20: self.steam_id = value
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        tabs = ttk.Notebook(self.window)
        tabs.pack(fill='both', expand=True, padx=16, pady=12)
        play, controls = ttk.Frame(tabs, padding=12), ttk.Frame(tabs, padding=12)
        tabs.add(play, text='Play and display')
        tabs.add(controls, text='Controls')
        mods = ttk.Frame(tabs, padding=12)
        tabs.add(mods, text='Mods')
        ttk.Label(mods, text='Native mod (optional)', font=('', 12, 'bold')).pack(anchor='w')
        ttk.Label(mods, text='Choose a trusted mod DLL. Leave this empty to play without native mods.\nMods run code on your PC and may change gameplay or saves.', wraplength=600).pack(anchor='w', pady=12)
        mod_row = ttk.Frame(mods); mod_row.pack(fill='x')
        ttk.Entry(mod_row, textvariable=self.vars['native_mod']).pack(side='left', fill='x', expand=True)
        ttk.Button(mod_row, text='Browse…', command=self.browse_mod).pack(side='left', padx=6)
        ttk.Button(mods, text='Disable native mod', command=lambda: self.vars['native_mod'].set('')).pack(anchor='w', pady=12)
        ttk.Label(mods, text='Save settings, then restart the game to apply your selection.').pack(anchor='w')
        ttk.Button(mods, text='Save settings', command=self.save).pack(anchor='w', pady=12)
        ttk.Label(play, text='Original USA game disc (.gdi)').pack(anchor='w')
        row = ttk.Frame(play); row.pack(fill='x', pady=6)
        ttk.Entry(row, textvariable=self.vars['gdi']).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse…', command=self.browse).pack(side='left', padx=6)
        ttk.Label(play, text='Music and sound volume').pack(anchor='w', pady=(12, 0))
        ttk.Spinbox(play, from_=0, to=100, textvariable=self.vars['volume'], width=8).pack(anchor='w')
        ttk.Label(play, text='Audio buffer in ms (smaller reduces buffering; increase if audio breaks up)').pack(anchor='w', pady=(8, 0))
        ttk.Combobox(play, textvariable=self.vars['audio_buffer_ms'], values=('32', '48', '64', '96', '128'), state='readonly', width=8).pack(anchor='w')
        ttk.Checkbutton(play, text='Fullscreen', variable=self.vars['fullscreen'], onvalue='1', offvalue='0').pack(anchor='w', pady=8)
        ttk.Checkbutton(play, text='VSync (may increase latency; off by default)', variable=self.vars['vsync'], onvalue='1', offvalue='0').pack(anchor='w')
        ttk.Checkbutton(play, text='Use texture packs from userdata/mods/MK-51051', variable=self.vars['texture_packs'], onvalue='1', offvalue='0').pack(anchor='w', pady=8)
        ttk.Label(play, text='Window size multiplier (original image is 640 × 480)').pack(anchor='w', pady=(12, 0))
        ttk.Combobox(play, textvariable=self.vars['window_scale'], values=('1', '2', '3', '4'), state='readonly', width=8).pack(anchor='w')
        ttk.Label(play, text='Settings apply on the next launch. Saves stay in userdata.\nFullscreen keeps the original game aspect ratio.', wraplength=600).pack(anchor='w', pady=18)
        buttons = ttk.Frame(play); buttons.pack(fill='x')
        ttk.Button(buttons, text='Save settings', command=self.save).pack(side='left')
        self.play_button = ttk.Button(buttons, text='Play directly', command=self.play); self.play_button.pack(side='left', padx=10)
        if self.steam_id:
            ttk.Button(buttons, text='Play via Steam', command=self.play_steam).pack(side='left', padx=(0, 10))
        self.build_button = ttk.Button(buttons, text='Build from my disc…', command=self.build); self.build_button.pack(side='left')
        ttk.Button(play, text='Input/audio measurement test', command=self.probe).pack(anchor='w', pady=12)
        ttk.Label(controls, text='Action').grid(row=0, column=0, padx=8, pady=8)
        ttk.Label(controls, text='Keyboard').grid(row=0, column=1, padx=8)
        ttk.Label(controls, text='Controller').grid(row=0, column=2, padx=8)
        labels = ('Pause / Start', 'Up', 'Down', 'Left', 'Right', 'Shoot', 'Rescue / Back', 'Dreamcast X', 'Dreamcast Y')
        for row, (action, label) in enumerate(zip(ACTIONS, labels), 1):
            ttk.Label(controls, text=label).grid(row=row, column=0, sticky='w', padx=8, pady=7)
            for column, prefix, choices in ((1, 'key_', KEYS), (2, 'pad_', PADS)):
                ttk.Combobox(controls, textvariable=self.vars[prefix+action], values=choices, state='readonly', width=18).grid(row=row, column=column, padx=8)
        ttk.Button(controls, text='Restore default controls', command=self.reset_controls).grid(row=10, column=0, columnspan=3, pady=12)
        self.log = tk.Text(self.window, height=8, state='disabled', wrap='word')
        self.log.pack(fill='x', padx=16, pady=(0, 12))
        self.window.after(200, self.poll)

    def browse(self):
        path = filedialog.askopenfilename(filetypes=[('Dreamcast GDI', '*.gdi')])
        if path: self.vars['gdi'].set(path)

    def browse_mod(self):
        path = filedialog.askopenfilename(filetypes=[('Native mod', '*.dll')])
        if path: self.vars['native_mod'].set(path)

    def reset_controls(self):
        for key in DEFAULTS:
            if key.startswith(('key_', 'pad_')): self.vars[key].set(DEFAULTS[key])

    def save(self):
        try:
            save(self.path, {k: v.get() for k, v in self.vars.items()})
            self.messages.put('Settings saved.\n')
            return True
        except (OSError, ValueError) as error:
            messagebox.showerror('Check settings', str(error))
            return False

    def play(self):
        if not self.save() or not self.game_stopped(): return
        gdi = pathlib.Path(self.vars['gdi'].get())
        if not gdi.is_file():
            messagebox.showerror('Select your disc', 'Choose the original USA .gdi file first.'); return
        required = ['build/sc5-native-dev.exe', 'build/native-diff.dll', 'build/libwinpthread-1.dll', 'extracted/1ST_READ.BIN'] + [f'build/native-diff-round{i}.dll' for i in range(1, 5)]
        if any(not (ROOT / p).is_file() for p in required):
            messagebox.showinfo('Build required', 'Use “Build from my disc…” to create your personal build first.'); return
        if self.building or (self.game and self.game.poll() is None): return
        log = (ROOT / 'userdata/last-launch.log').open('w', encoding='utf-8')
        try:
            self.game_log = 'userdata/last-launch.log'
            self.game = subprocess.Popen([str(ROOT / 'build/sc5-native-dev.exe'), '--gdi', str(gdi.resolve())], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.play_button.configure(state='disabled'); self.build_button.configure(state='disabled')
            self.messages.put('Game launched. Close the game before changing settings.\n')
        except OSError as error:
            messagebox.showerror('Launch failed', str(error))
        finally:
            log.close()

    def build(self):
        if self.building or not self.save() or not self.game_stopped(): return
        self.building = True
        gdi_path = self.vars['gdi'].get()
        self.build_button.configure(state='disabled'); self.play_button.configure(state='disabled')
        def worker():
            try:
                command = [sys.executable, '-u', str(ROOT / 'tools/bootstrap.py'), '--gdi', gdi_path]
                with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)) as proc:
                    for line in proc.stdout: self.messages.put(line)
                    self.messages.put(f'Build exited with code {proc.wait()}.\n')
            except Exception as error:
                self.messages.put(f'Build failed: {error}\n')
            finally:
                self.messages.put(None)
        threading.Thread(target=worker, daemon=True).start()

    def game_stopped(self):
        executable = ROOT / 'build/sc5-native-dev.exe'
        if executable.exists():
            try:
                # Windows denies a writable handle while the executable is
                # mapped by a running game. No bytes are written here.
                with executable.open('r+b'): pass
            except PermissionError:
                messagebox.showinfo('Game is running', 'Close the game before building or starting another session.')
                return False
        return True

    def play_steam(self):
        if self.building or not self.save() or not self.game_stopped(): return
        try:
            os.startfile('steam://rungameid/' + self.steam_id)
            self.messages.put('Launched your existing Steam shortcut with Steam Input.\n')
        except OSError as error:
            messagebox.showerror('Steam launch failed', str(error))

    def probe(self):
        executable = ROOT / 'build/sc5-native-dev.exe'
        if self.building or (self.game and self.game.poll() is None): return
        if not executable.is_file():
            messagebox.showinfo('Build required', 'Build the native application first.'); return
        messagebox.showinfo('Measure your setup', 'Press a key or controller button to flash the screen and play a brief tone. Escape closes the test.\n\nFor physical delay, film the button, screen and speaker with a high-speed camera. The log only measures software boundaries; it does not calibrate gameplay.')
        (ROOT / 'userdata').mkdir(exist_ok=True)
        try:
            with (ROOT / 'userdata/latency-test.log').open('w') as log:
                self.game_log = 'userdata/latency-test.log'
                self.game = subprocess.Popen([str(executable), '--latency-test'], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except OSError as error:
            messagebox.showerror('Measurement test failed', str(error)); return
        self.play_button.configure(state='disabled'); self.build_button.configure(state='disabled')

    def poll(self):
        while not self.messages.empty():
            message = self.messages.get()
            if message is None:
                self.building = False; self.build_button.configure(state='normal'); self.play_button.configure(state='normal')
            else:
                self.log.configure(state='normal'); self.log.insert('end', message)
                if int(self.log.index('end-1c').split('.')[0]) > 300: self.log.delete('1.0', '100.0')
                self.log.see('end'); self.log.configure(state='disabled')
        if self.game and self.game.poll() is not None:
            self.messages.put(f'Application exited with code {self.game.returncode}. Details: {self.game_log}\n')
            self.game = None; self.play_button.configure(state='normal'); self.build_button.configure(state='normal')
        self.window.after(200, self.poll)

    def close(self):
        if self.building:
            messagebox.showinfo('Build running', 'Keep the launcher open until the build finishes.'); return
        self.window.destroy()

if __name__ == '__main__':
    Launcher().window.mainloop()
