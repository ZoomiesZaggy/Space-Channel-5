import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import uuid
import webbrowser

from .build import Native,FAULTS,bundled_name,compile_c,suffix,compiler
from .demo import initialize,make_demo
from .disc import Disc
from .sh4 import BASE,MAX_IMAGE,discover,translate

ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.environ.get("LOCALAPPDATA",str(Path.home()/".local"/"share")))/"DreamcastForge"
BG="#0c111b";PANEL="#151e2d";INK="#edf3ff";MUTED="#98aac2";ACCENT="#70e5c3";ORANGE="#ffb47c"

def load_state(path):
    try:
        state=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state,dict) or not isinstance(state.get("games",[]),list): raise ValueError()
        games=[]
        for game in state.get("games",[]):
            if isinstance(game,dict) and all(isinstance(game.get(k),str) for k in ("id","path","title","kind")):
                if len(game["id"])==32 and all(c in "0123456789abcdef" for c in game["id"]): games.append(game)
        return {"games":games,"flycast":state.get("flycast","") if isinstance(state.get("flycast",""),str) else ""}
    except (OSError,ValueError):return {"games":[],"flycast":""}

class App(tk.Tk):
    def __init__(self):
        super().__init__();self.title("Dreamcast Forge • Experimental 0.1");self.geometry("1100x760");self.minsize(920,680);self.configure(bg=BG)
        DATA.mkdir(parents=True,exist_ok=True)
        self.state_path=DATA/"settings.json";self.settings=load_state(self.state_path)
        self.jobs=queue.Queue();self.busy=False;self.selected=None;self.selection_token=0
        style=ttk.Style(self);style.theme_use("clam")
        style.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=INK,rowheight=36,borderwidth=0,font=("Segoe UI",11))
        style.map("Treeview",background=[("selected","#294a51")],foreground=[("selected",INK)])
        style.configure("Treeview.Heading",background=PANEL,foreground=MUTED,font=("Segoe UI",10))
        header=tk.Frame(self,bg=BG);header.pack(fill="x",padx=28,pady=(26,18))
        tk.Label(header,text="◉  DREAMCAST FORGE",bg=BG,fg=INK,font=("Segoe UI",24,"bold")).pack(side="left")
        tk.Label(header,text="EXPERIMENTAL  0.1",bg="#293044",fg=ORANGE,padx=12,pady=7,font=("Segoe UI",10,"bold")).pack(side="right")
        tk.Label(self,text="Explore your games. Build native code. Know what works.",bg=BG,fg=MUTED,font=("Segoe UI",12)).pack(anchor="w",padx=30)
        banner=tk.Frame(self,bg="#24302c");banner.pack(fill="x",padx=28,pady=(18,20))
        tk.Label(banner,text="Native recompilation is a prototype. Retail games need a hardware runtime and game-specific work.",bg="#24302c",fg="#c4e7da",padx=14,pady=12,font=("Segoe UI",10),anchor="w").pack(fill="x")
        content=tk.Frame(self,bg=BG);content.pack(fill="both",expand=True,padx=28)
        left=tk.Frame(content,bg=PANEL,width=290);left.pack(side="left",fill="y",padx=(0,18));left.pack_propagate(False)
        tk.Label(left,text="YOUR PROJECTS",bg=PANEL,fg=MUTED,font=("Segoe UI",10,"bold")).pack(anchor="w",padx=18,pady=(18,12))
        self.tree=ttk.Treeview(left,show="tree",selectmode="browse");self.tree.pack(fill="both",expand=True,padx=10)
        self.tree.bind("<<TreeviewSelect>>",self.select)
        self.button(left,"+  Import game or binary",self.import_game).pack(fill="x",padx=16,pady=12)
        self.button(left,"Set up Flycast…",self.setup_flycast,secondary=True).pack(fill="x",padx=16,pady=(0,16))
        right=tk.Frame(content,bg=BG);right.pack(side="left",fill="both",expand=True)
        self.title_label=tk.Label(right,bg=BG,fg=INK,font=("Segoe UI",22,"bold"),anchor="w",wraplength=650,justify="left");self.title_label.pack(fill="x")
        self.detail=tk.Label(right,bg=BG,fg=MUTED,font=("Segoe UI",11),anchor="w",justify="left",wraplength=635);self.detail.pack(fill="x",pady=(10,18))
        buttons=tk.Frame(right,bg=BG);buttons.pack(fill="x",pady=(0,12))
        self.primary=self.button(buttons,"Play native demo",self.primary_action);self.primary.pack(side="left",padx=(0,8))
        self.secondary=self.button(buttons,"Rebuild demo",self.secondary_action,secondary=True);self.secondary.pack(side="left")
        self.export_button=self.button(right,"Export C source…",self.export_source,secondary=True);self.export_button.pack(anchor="w",pady=(0,14))
        tk.Label(right,text="BUILD & INSPECTION LOG",bg=BG,fg=MUTED,font=("Segoe UI",9,"bold")).pack(anchor="w",pady=(6,8))
        logframe=tk.Frame(right,bg=PANEL);logframe.pack(fill="both",expand=True)
        self.log=tk.Text(logframe,bg=PANEL,fg="#bfd0e5",font=("Consolas",10),relief="flat",wrap="word",padx=15,pady=14,state="disabled")
        scroll=ttk.Scrollbar(logframe,command=self.log.yview);scroll.pack(side="right",fill="y");self.log.configure(yscrollcommand=scroll.set);self.log.pack(fill="both",expand=True)
        footer=tk.Frame(self,bg=BG);footer.pack(fill="x",padx=28,pady=16)
        self.status=tk.Label(footer,text="Ready  •  Files stay on your PC",bg=BG,fg=MUTED,font=("Segoe UI",10));self.status.pack(side="left")
        self.button(footer,"Quick start",self.help,secondary=True).pack(side="right")
        self.refresh();self.tree.selection_set("demo");self.select();self.after(75,self.poll)

    def button(self,parent,text,command,secondary=False):
        return tk.Button(parent,text=text,command=command,bg="#233044" if secondary else ACCENT,fg=INK if secondary else "#102820",activebackground="#3a5369" if secondary else "#a4f2dc",activeforeground=INK if secondary else BG,relief="flat",borderwidth=0,padx=16,pady=10,font=("Segoe UI",10,"bold"),cursor="hand2",disabledforeground="#6f7c8c")

    def save(self):
        temp=self.state_path.with_suffix(".tmp");temp.write_text(json.dumps(self.settings,indent=2),encoding="utf-8");temp.replace(self.state_path)

    def refresh(self):
        self.tree.delete(*self.tree.get_children());self.tree.insert("", "end",iid="demo",text="  Orbit Catch • SH-4 demo")
        for g in self.settings["games"]:self.tree.insert("","end",iid=g["id"],text="  "+g["title"][:34])

    def select(self,event=None):
        chosen=self.tree.selection()
        if not chosen:return
        self.selection_token+=1;key=chosen[0]
        self.selected=None if key=="demo" else next((g for g in self.settings["games"] if g["id"]==key),None)
        self.export_button.config(state="normal" if not self.busy else "disabled")
        if self.selected is None:
            self.title_label.config(text="Orbit Catch")
            self.detail.config(text="A playable compiler demonstration. Catch falling stars with ← → or A / D.\n\nGame logic: SH-4 machine code → C → native PC library.\nGraphics and input: a custom desktop host, not Dreamcast hardware.")
            self.primary.config(text="▶  Play native demo");self.secondary.config(text="Recompile demo")
            self.write("Bundled original sample • no commercial game data\n\nPlay uses the included native library on Windows x64 or Linux x64. Recompile regenerates C from the included SH-4 binary and builds it using your installed compiler.\n\nRetail Dreamcast compatibility: none established.",clear=True)
        else:
            g=self.selected;self.title_label.config(text=g["title"])
            self.detail.config(text=f"{g['kind'].upper()}  •  {g['path']}\n\nNative game support: not implemented for retail titles.\nAnalysis is experimental; a successful translation does not prove playability.")
            self.primary.config(text="Inspect & analyze");self.secondary.config(text="▶  Play with Flycast")
            self.write("Choose Inspect & analyze to identify the boot executable and report unsupported instructions.\n\nCHD and CDI: emulator launch only.\nGDI: keep the descriptor and all track files together.\nBIN: must be a flat, unscrambled SH-4 executable loaded at 0x8C010000; disc tracks are not executables. Use the CLI for other load addresses.\n\nFlycast is a separately installed emulator. It does not produce a standalone native port.",clear=True)

    def write(self,text,clear=False):
        self.log.config(state="normal")
        if clear:self.log.delete("1.0","end")
        self.log.insert("end",text+"\n");self.log.see("end");self.log.config(state="disabled")

    def work(self,label,fn,done):
        if self.busy:return
        self.busy=True;self.status.config(text=label+"…")
        for b in (self.primary,self.secondary,self.export_button):b.config(state="disabled")
        def run():
            try:self.jobs.put((done,fn(),None))
            except Exception as e:self.jobs.put((done,None,str(e)))
        threading.Thread(target=run,daemon=True).start()

    def poll(self):
        try:
            done,result,error=self.jobs.get_nowait();self.busy=False
            for b in (self.primary,self.secondary,self.export_button):b.config(state="normal")
            self.status.config(text="Ready  •  Files stay on your PC")
            if error:self.write(error);messagebox.showerror("Could not complete",error,parent=self)
            else:
                try:done(result)
                except Exception as e:messagebox.showerror("Could not complete",str(e),parent=self)
        except queue.Empty:pass
        self.after(75,self.poll)

    def import_game(self):
        if self.busy:return
        path=filedialog.askopenfilename(title="Choose a Dreamcast image or SH-4 executable",filetypes=[("Game images and executables","*.gdi *.iso *.chd *.cdi *.bin"),("All files","*")])
        if not path:return
        p=Path(path).resolve();kind=p.suffix.lower().lstrip(".")
        if kind not in ("gdi","iso","chd","cdi","bin"):
            messagebox.showerror("Unsupported format","Choose GDI, ISO, CHD, CDI, or a flat SH-4 BIN.",parent=self);return
        existing=next((g for g in self.settings["games"] if g["path"]==str(p)),None)
        if existing:self.tree.selection_set(existing["id"]);return
        g={"id":uuid.uuid4().hex,"path":str(p),"title":p.stem,"kind":kind}
        self.settings["games"].append(g);self.save();self.refresh();self.tree.selection_set(g["id"])

    def read_selected(self,g):
        path=Path(g["path"])
        if g["kind"] in ("gdi","iso"):return Disc(path).boot()
        if g["kind"]!="bin":raise ValueError("CHD/CDI extraction is not implemented. Use Play with Flycast, or supply a GDI with its tracks.")
        if path.stat().st_size>MAX_IMAGE:raise ValueError("BIN is too large. Choose a boot executable, not a full disc track (maximum 4 MiB).")
        blob=path.read_bytes();return {"title":g["title"],"boot_name":path.name,"bytes":len(blob)},blob

    def primary_action(self):
        if self.selected is None:self.play_demo();return
        game=dict(self.selected);token=self.selection_token
        def analyze():
            meta,blob=self.read_selected(game);found,issues=discover(blob)
            report={"metadata":meta,"sha256":hashlib.sha256(blob).hexdigest(),"load_address":"0x8C010000","reachable_instructions":len(found),"issues":issues,"retail_playable":False,
                    "note":"Assumes an unscrambled flat executable. No GPU/audio/disc/BIOS runtime. Instruction count excludes duplicated delay slots; it is not a compatibility percentage."}
            folder=DATA/"projects"/game["id"];folder.mkdir(parents=True,exist_ok=True)
            (folder/"analysis.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
            return report,folder
        def done(result):
            report,folder=result
            if token!=self.selection_token:return
            self.write(f"{report['metadata']['title']}\nBoot file: {report['metadata']['boot_name']}\nSize: {report['metadata']['bytes']:,} bytes\nDiscovered instructions: {report['reachable_instructions']:,}\nSHA-256: {report['sha256']}\n",clear=True)
            self.write("\n".join(report["issues"][:30]) if report["issues"] else "No unsupported opcode encountered on discovered paths. This does not prove complete code discovery or game compatibility.")
            self.write(f"\nRetail native build: unavailable. Graphics, sound, system services, and game-specific work are required.\nReport saved to {folder / 'analysis.json'}")
        self.work("Inspecting game",analyze,done)

    def secondary_action(self):
        if self.selected is None:self.play_demo(rebuild=True)
        else:self.launch_flycast()

    def play_demo(self,rebuild=False):
        def prepare():
            blob,_=make_demo();bundled=bundled_name()
            if not rebuild and bundled and (ROOT/"native"/bundled).is_file():
                path=ROOT/"native"/bundled
                expected=json.loads((ROOT/"native"/"checksums.json").read_text())[bundled]
                if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError("Bundled demo checksum mismatch. Extract a fresh copy or choose Recompile demo.")
                return path,"Using the bundled native SH-4 demo."
            folder=DATA/"builds"/uuid.uuid4().hex;folder.mkdir(parents=True,exist_ok=True)
            source=folder/"orbit.c";source.write_text(translate(blob),encoding="utf-8")
            return compile_c(source,folder/("orbit"+suffix())),f"Translated {len(blob)} SH-4 bytes to C and compiled successfully.\nBuild: {folder}"
        def done(result):
            path,log=result;self.write(log)
            existing=getattr(self,"demo_window",None)
            if existing and existing.winfo_exists():existing.close()
            self.demo_window=DemoWindow(self,Native(path))
        self.work("Preparing native demo",prepare,done)

    def export_source(self):
        game=dict(self.selected) if self.selected else None
        target=filedialog.asksaveasfilename(title="Export generated C",defaultextension=".c",initialfile="recompiled.c",filetypes=[("C source","*.c")])
        if not target:return
        def export():
            blob=self.read_selected(game)[1] if game else make_demo()[0]
            source=translate(blob);Path(target).write_text(source,encoding="utf-8");return target
        self.work("Translating SH-4",export,lambda p:self.write(f"Generated C saved to {p}\nThis is CPU code. Imported retail games still require a hardware runtime."))

    def setup_flycast(self):
        win=tk.Toplevel(self);win.title("Set up Flycast");win.configure(bg=BG);win.geometry("540x280");win.transient(self)
        tk.Label(win,text="Play retail games with an emulator",bg=BG,fg=INK,font=("Segoe UI",16,"bold")).pack(padx=20,pady=20)
        tk.Label(win,text="Download Flycast, extract it, then select its executable.\nConfigure controls and any required system files in Flycast.\nThis launches the emulator; it does not recompile a native port.",bg=BG,fg=MUTED,font=("Segoe UI",11),justify="left").pack(padx=20,pady=8)
        self.button(win,"Open official downloads",lambda:webbrowser.open("https://github.com/flyinghead/flycast/releases"),secondary=True).pack(pady=6)
        def choose():
            path=filedialog.askopenfilename(title="Select Flycast executable",parent=win)
            if path:self.settings["flycast"]=str(Path(path).resolve());self.save();win.destroy()
        self.button(win,"Choose installed Flycast…",choose).pack(pady=6)

    def launch_flycast(self):
        if not self.selected:return
        if self.selected["kind"]=="bin":messagebox.showinfo("Choose a disc image","Launch a GDI, ISO, CHD, or CDI, not a raw executable.",parent=self);return
        exe=Path(self.settings.get("flycast",""));game=Path(self.selected["path"])
        if not exe.is_file():self.setup_flycast();return
        if not game.is_file():messagebox.showerror("Missing game","The original image was moved or removed. Import it again.",parent=self);return
        if sys.platform=="win32" and exe.suffix.lower()!=".exe":messagebox.showerror("Choose an executable","Select flycast.exe, not a shortcut or script.",parent=self);return
        try:
            subprocess.Popen([str(exe.resolve()),str(game.resolve())],cwd=exe.parent)
            self.write("Started Flycast (emulation). Configure controller, video, BIOS, and saves inside Flycast.")
        except OSError as e:messagebox.showerror("Launch failed",str(e),parent=self)

    def help(self):
        webbrowser.open((ROOT/"QUICK_START.html").as_uri())

    def report_callback_exception(self,exc,value,tb):
        messagebox.showerror("Dreamcast Forge",str(value),parent=self)

class DemoWindow(tk.Toplevel):
    def __init__(self,parent,native):
        super().__init__(parent);self.title("Orbit Catch • Recompiled SH-4 logic");self.configure(bg=BG);self.resizable(False,False)
        self.native=native;self.keys=set();self.alive=True;self.paused=False
        self.canvas=tk.Canvas(self,width=720,height=530,bg=BG,highlightthickness=0);self.canvas.pack()
        self.info=tk.Label(self,text="← → / A D  Move     •     Space  Pause     •     Enter  Restart",bg=BG,fg=MUTED,font=("Segoe UI",11));self.info.pack(pady=(0,16))
        self.bind("<KeyPress>",self.key_down);self.bind("<KeyRelease>",lambda e:self.keys.discard(e.keysym.lower()))
        self.bind("<FocusOut>",self.focus_out);self.protocol("WM_DELETE_WINDOW",self.close)
        initialize(native);self.after(100,self.focus_force);self.tick()
    def close(self):self.alive=False;self.destroy()
    def focus_out(self,event):self.keys.clear();self.paused=True
    def key_down(self,e):
        key=e.keysym.lower()
        if key in self.keys:return
        self.keys.add(key)
        if key=="space":self.paused=not self.paused
        if key=="return":initialize(self.native);self.paused=False
        if key=="escape":self.close()
    def tick(self):
        if not self.alive:return
        n=self.native
        if not self.paused:
            n.set(0,int(bool(self.keys&{"left","a"}))|int(bool(self.keys&{"right","d"}))*2)
            status=n.run(BASE,2000)
            if status:
                self.paused=True;messagebox.showerror("Native runtime stopped",FAULTS.get(status,str(status)),parent=self)
        c=self.canvas;c.delete("all")
        for i in range(46):
            x=(i*173+37)%720;y=(i*97+11)%530;c.create_oval(x,y,x+2,y+2,fill="#293b55",outline="")
        c.create_text(40,34,anchor="w",text="ORBIT CATCH",fill=INK,font=("Segoe UI",20,"bold"))
        c.create_text(680,34,anchor="e",text=f"SCORE  {n.get(4):03}",fill=ACCENT,font=("Consolas",17,"bold"))
        c.create_text(40,67,anchor="w",text="SH-4 → C → native PC",fill=MUTED,font=("Segoe UI",10))
        c.create_text(680,67,anchor="e",text=f"LIVES  {n.get(5)}",fill=ORANGE,font=("Consolas",12))
        c.create_line(40,495,680,495,fill="#2d4058")
        x=n.get(1)+40;y=490
        c.create_polygon(x-29,y-10,x-20,y+3,x+20,y+3,x+29,y-10,x+18,y-4,x-18,y-4,fill=ACCENT,outline="#c1fff0",width=2)
        sx=n.get(2)+40;sy=n.get(3)+90;points=[]
        for i in range(10):
            angle=-math.pi/2+i*math.pi/5;radius=13 if i%2==0 else 6
            points.extend((sx+math.cos(angle)*radius,sy+math.sin(angle)*radius))
        c.create_polygon(*points,fill=ORANGE,outline="#ffe5bc")
        if not n.get(5) or self.paused:
            c.create_rectangle(160,210,560,340,fill=PANEL,outline="#384d65")
            c.create_text(360,252,text="NICE RUN" if not n.get(5) else "PAUSED",fill=INK,font=("Segoe UI",27,"bold"))
            c.create_text(360,303,text="Press Enter to restart" if not n.get(5) else "Press Space to resume",fill=MUTED,font=("Segoe UI",12))
        self.after(16,self.tick)

def main():
    try:App().mainloop()
    except tk.TclError as e:
        print(f"Could not open the desktop interface: {e}\nRun on a desktop with Python's tkinter installed.",file=sys.stderr)
        raise SystemExit(1)
