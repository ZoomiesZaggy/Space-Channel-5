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
from import_game import import_game, installed
from player_config import ACTIONS, DEFAULTS, KEYS, PADS, load, save

FROZEN = getattr(sys, 'frozen', False)
APP_ROOT = pathlib.Path(sys.executable).resolve().parent if FROZEN else pathlib.Path(__file__).resolve().parents[1]
ROOT = APP_ROOT
if FROZEN and sys.platform == 'darwin':
    ROOT = pathlib.Path.home() / 'Library/Application Support/SpaceChannel5'
elif FROZEN and sys.platform.startswith('linux'):
    ROOT = pathlib.Path(os.environ.get('XDG_DATA_HOME', pathlib.Path.home() / '.local/share')) / 'SpaceChannel5'
def game_environment():
    env = dict(os.environ, SC5_USER_ROOT=str(ROOT))
    if 'LD_LIBRARY_PATH_ORIG' in env: env['LD_LIBRARY_PATH'] = env['LD_LIBRARY_PATH_ORIG']
    elif FROZEN: env.pop('LD_LIBRARY_PATH', None)
    return env
EXECUTABLE = 'build/sc5-native-dev.exe' if os.name == 'nt' else 'build/sc5-native-dev'
SUFFIX = '.dll' if os.name == 'nt' else '.dylib' if sys.platform == 'darwin' else '.so' 

class Launcher:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title('Space Channel 5')
        self.window.geometry('720x720')
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
        tabs.add(play, text='Play')
        graphics = ttk.Frame(tabs, padding=12)
        tabs.add(graphics, text='Display')
        tabs.add(controls, text='Controls')
        mods = ttk.Frame(tabs, padding=12)
        tabs.add(mods, text='Mods')
        ttk.Label(mods, text='Native mod (optional)', font=('', 12, 'bold')).pack(anchor='w')
        ttk.Label(mods, text='Choose a trusted native mod library. Leave this empty to play without native mods.\nMods run code on your PC and may change gameplay or saves.', wraplength=600).pack(anchor='w', pady=12)
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
        ttk.Label(play, text='Rhythm timing offset in ms (positive accepts later responses)').pack(anchor='w', pady=(8, 0))
        ttk.Spinbox(play, from_=-250, to=250, increment=25, textvariable=self.vars['rhythm_offset_ms'], width=8).pack(anchor='w')
        ttk.Checkbutton(graphics, text='Fullscreen', variable=self.vars['fullscreen'], onvalue='1', offvalue='0').pack(anchor='w', pady=8)
        ttk.Checkbutton(graphics, text='VSync', variable=self.vars['vsync'], onvalue='1', offvalue='0').pack(anchor='w')
        ttk.Label(graphics, text='Picture layout', font=('', 12, 'bold')).pack(anchor='w', pady=(16, 6))
        for value, label in enumerate(('Original 4:3', 'Widescreen window — preserve complete picture', 'Fill screen — crop top/bottom as needed', 'Stretch to fill screen')):
            ttk.Radiobutton(graphics, text=label, variable=self.vars['display_mode'], value=str(value)).pack(anchor='w', pady=4)
        ttk.Label(graphics, text='Preserve picture is recommended for prerecorded backgrounds. Crop may hide HUD elements; stretch changes proportions.', wraplength=580).pack(anchor='w', pady=10)
        ttk.Checkbutton(graphics, text='Motion interpolation to 60 FPS', variable=self.vars['motion_interpolation'], onvalue='1', offvalue='0').pack(anchor='w', pady=8)
        ttk.Label(graphics, text='Interpolates matching geometry. Videos retain their original cadence. Adds up to 17 ms of display delay; gameplay and music timing are unchanged.', wraplength=580).pack(anchor='w')
        ttk.Checkbutton(graphics, text='Use texture packs', variable=self.vars['texture_packs'], onvalue='1', offvalue='0').pack(anchor='w', pady=12)
        ttk.Label(graphics, text='Window size multiplier').pack(anchor='w', pady=(8, 0))
        ttk.Combobox(graphics, textvariable=self.vars['window_scale'], values=('1', '2', '3', '4'), state='readonly', width=8).pack(anchor='w')
        ttk.Label(graphics, text='Settings apply on the next launch.').pack(anchor='w', pady=12)
        ttk.Button(graphics, text='Save settings', command=self.save).pack(anchor='w')
        buttons = ttk.Frame(play); buttons.pack(fill='x')
        ttk.Button(buttons, text='Save settings', command=self.save).pack(side='left')
        self.play_button = ttk.Button(buttons, text='Play directly', command=self.play); self.play_button.pack(side='left', padx=10)
        if self.steam_id:
            ttk.Button(buttons, text='Play via Steam', command=self.play_steam).pack(side='left', padx=(0, 10))
        self.build_button = ttk.Button(buttons, text='Import my disc…' if FROZEN else 'Build from my disc…', command=self.build); self.build_button.pack(side='left')
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
        path = filedialog.askopenfilename(filetypes=[('Native mod', '*' + SUFFIX)])
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
        if FROZEN and not installed(ROOT):
            try:
                import_game(gdi, ROOT)
                self.messages.put('Disc imported. No compilation needed.\n')
            except Exception as error:
                messagebox.showerror('Disc import failed', str(error)); return
        required = [EXECUTABLE, 'build/native-diff' + SUFFIX, 'extracted/1ST_READ.BIN'] + [f'build/native-diff-round{i}{SUFFIX}' for i in range(1, 5)]
        if any(not ((ROOT if p.startswith('extracted/') else APP_ROOT) / p).is_file() for p in required):
            messagebox.showinfo('Missing game files', 'Extract the complete release archive again.' if FROZEN else 'Use “Build from my disc…” to create your personal build first.'); return
        if self.building or (self.game and self.game.poll() is None): return
        log = (ROOT / 'userdata/last-launch.log').open('w', encoding='utf-8')
        try:
            self.game_log = 'userdata/last-launch.log'
            self.game = subprocess.Popen([str(APP_ROOT / EXECUTABLE), '--gdi', str(gdi.resolve())], cwd=ROOT, env=game_environment(), stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.play_button.configure(state='disabled'); self.build_button.configure(state='disabled')
            self.messages.put('Game launched. Close the game before changing settings.\n')
        except OSError as error:
            messagebox.showerror('Launch failed', str(error))
        finally:
            log.close()

    def build(self):
        if FROZEN:
            if self.building or not self.save() or not self.game_stopped(): return
            try:
                count = import_game(self.vars['gdi'].get(), ROOT)
                self.messages.put(f'Imported {count} game files. Ready to play.\n')
            except Exception as error:
                messagebox.showerror('Disc import failed', str(error))
            return
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
        executable = APP_ROOT / EXECUTABLE
        if self.game and self.game.poll() is None: return False
        if os.name == 'nt' and executable.exists():
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
            uri = 'steam://rungameid/' + self.steam_id
            if os.name == 'nt': os.startfile(uri)
            else: subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', uri])
            self.messages.put('Launched your existing Steam shortcut with Steam Input.\n')
        except OSError as error:
            messagebox.showerror('Steam launch failed', str(error))

    def probe(self):
        executable = APP_ROOT / EXECUTABLE
        if self.building or (self.game and self.game.poll() is None): return
        if not executable.is_file():
            messagebox.showinfo('Build required', 'Build the native application first.'); return
        messagebox.showinfo('Measure your setup', 'Press a key or controller button to flash the screen and play a brief tone. Escape closes the test.\n\nFor physical delay, film the button, screen and speaker with a high-speed camera. The log only measures software boundaries; it does not calibrate gameplay.')
        (ROOT / 'userdata').mkdir(exist_ok=True)
        try:
            with (ROOT / 'userdata/latency-test.log').open('w') as log:
                self.game_log = 'userdata/latency-test.log'
                self.game = subprocess.Popen([str(executable), '--latency-test'], cwd=ROOT, env=game_environment(), stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
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
    if len(sys.argv) == 3 and sys.argv[1] == '--import-disc':
        import_game(sys.argv[2], ROOT)
    else:
        Launcher().window.mainloop()
