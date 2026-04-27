import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, font as tkfont, ttk
import os, re, json, subprocess, urllib.request, threading, time

SESSION = os.path.expanduser("~/.fennec_session.json")

try:
    from spellchecker import SpellChecker; _spell = SpellChecker(); SPELL_OK = True
except ImportError:
    SPELL_OK = False

try:
    from pygments import lex
    from pygments.lexers import get_lexer_for_filename
    try: from pygments.lexers import TextLexer
    except ImportError: from pygments.lexers.special import TextLexer
    PYGMENTS_OK = True
except ImportError:
    PYGMENTS_OK = False

THEMES = {
    "light": dict(bg="#f0f0f0", tbg="#ffffff", fg="#000000", cur="#000000", sbg="#f0f0f0",
                  sfg="#444", ln="#bbb", sel="#0078d7", selfg="#fff",
                  ta="#ffffff", ti="#e0e0e0", tfg="#000", trm="#1e1e1e", trmfg="#d4d4d4"),
    "dark":  dict(bg="#1e1e1e", tbg="#1e1e1e", fg="#d4d4d4", cur="#fff", sbg="#007acc",
                  sfg="#fff", ln="#555", sel="#264f78", selfg="#fff",
                  ta="#1e1e1e", ti="#2d2d2d", tfg="#ccc", trm="#0e0e0e", trmfg="#d4d4d4"),
}
SYN = {
    "light": dict(kw="#0000ff", st="#a31515", cm="#008000", nu="#098658", fn="#795e26", cl="#267f99", bi="#0070c1"),
    "dark":  dict(kw="#569cd6", st="#ce9178", cm="#6a9955", nu="#b5cea8", fn="#dcdcaa", cl="#4ec9b0", bi="#9cdcfe"),
}

def _tag(t):
    s = str(t)
    if "Keyword" in s: return "kw"
    if "String" in s: return "st"
    if "Comment" in s: return "cm"
    if "Number" in s: return "nu"
    if "Name.Function" in s: return "fn"
    if "Name.Class" in s: return "cl"
    if "Name.Builtin" in s: return "bi"


class Tab:
    def __init__(self, container, fnt, on_change, theme):
        self.file_path = None; self.modified = False
        self._fnt = fnt; self._cb = on_change; self._theme = theme; self._hj = self._sj = None

        self.frame = tk.Frame(container)
        self.frame.grid_rowconfigure(0, weight=1); self.frame.grid_columnconfigure(1, weight=1)

        self.ln = tk.Canvas(self.frame, width=44, bd=0, highlightthickness=0)
        self.ln.grid(row=0, column=0, sticky="ns")

        tf = tk.Frame(self.frame); tf.grid(row=0, column=1, sticky="nsew")
        tf.grid_rowconfigure(0, weight=1); tf.grid_columnconfigure(0, weight=1)
        sb = tk.Scrollbar(tf); sb.grid(row=0, column=1, sticky="ns")
        self.ta = tk.Text(tf, undo=True, wrap="word", font=fnt, bd=0, padx=8, pady=6,
                          yscrollcommand=lambda *a: (sb.set(*a), self._draw_ln()))
        self.ta.grid(row=0, column=0, sticky="nsew"); sb.config(command=self.ta.yview)
        self.ta.tag_config("spell", underline=True, foreground="#cc2222")
        self.ta.bind("<<Modified>>", self._mod)
        for ev in ("<KeyRelease>","<ButtonRelease>","<MouseWheel>","<Configure>"):
            self.ta.bind(ev, lambda e: (self._draw_ln(), self._cb()))

    def _draw_ln(self):
        self.ln.delete("all"); t = THEMES[self._theme]; i = self.ta.index("@0,0")
        while True:
            d = self.ta.dlineinfo(i)
            if not d: break
            self.ln.create_text(38, d[1], anchor="ne", text=i.split(".")[0], font=self._fnt, fill=t["ln"])
            n = self.ta.index(f"{i}+1line")
            if n == i: break
            i = n

    def _mod(self, e=None):
        if self.ta.edit_modified():
            self.modified = True; self.ta.edit_modified(False); self._cb()
            self._sched_hl(); self._sched_sp()
        self._draw_ln()

    def _sched_hl(self):
        if self._hj: self.ta.after_cancel(self._hj)
        self._hj = self.ta.after(400, self._highlight)

    def _sched_sp(self):
        if self._sj: self.ta.after_cancel(self._sj)
        self._sj = self.ta.after(700, self._spellcheck)

    def _highlight(self):
        if not PYGMENTS_OK: return
        try: lx = get_lexer_for_filename(self.file_path or "untitled.txt")
        except: lx = TextLexer()
        syn = SYN[self._theme]
        for k, c in syn.items(): self.ta.tag_config(f"s{k}", foreground=c); self.ta.tag_remove(f"s{k}", "1.0", tk.END)
        row = col = 0
        for ttype, val in lex(self.ta.get("1.0", "end-1c"), lx):
            tg = _tag(ttype)
            for i, seg in enumerate(val.split("\n")):
                if i: row += 1; col = 0
                if tg and seg: self.ta.tag_add(f"s{tg}", f"{row+1}.{col}", f"{row+1}.{col+len(seg)}")
                col += len(seg)
        self.ta.tag_raise("spell")

    def _spellcheck(self):
        if not SPELL_OK: return
        self.ta.tag_remove("spell", "1.0", tk.END)
        for ln, line in enumerate(self.ta.get("1.0", tk.END).split("\n"), 1):
            for m in re.finditer(r"\b[a-zA-Z']+\b", line):
                w = m.group().strip("'")
                if w and _spell.unknown([w]):
                    self.ta.tag_add("spell", f"{ln}.{m.start()}", f"{ln}.{m.end()}")

    def retheme(self, key):
        self._theme = key; t = THEMES[key]; syn = SYN[key]
        self.ta.config(bg=t["tbg"], fg=t["fg"], insertbackground=t["cur"],
                       selectbackground=t["sel"], selectforeground=t["selfg"])
        self.ln.config(bg=t["tbg"])
        for k, c in syn.items(): self.ta.tag_config(f"s{k}", foreground=c)
        self._draw_ln()

    def label(self):
        return ("● " if self.modified else "") + (os.path.basename(self.file_path) if self.file_path else "Untitled")


class Fennec:
    FONT, SIZE = "Courier New", 11

    def __init__(self, root):
        self.root = root; self.root.title("Fennec"); self.root.geometry("1000x700")
        self.fsize = self.SIZE; self._fnt = tkfont.Font(family=self.FONT, size=self.SIZE)
        self._theme = "light"; self.recent = []; self._tabs = []; self._idx = 0
        self._splash(); self._ui(); self._menu(); self._keys()
        self._load_session() or self.new_tab()
        self.root.deiconify()

    def _splash(self):
        sp = tk.Toplevel(self.root); sp.overrideredirect(True); sp.config(bg="#1e1e1e")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        sp.geometry(f"300x85+{sw//2-150}+{sh//2-42}")
        tk.Label(sp, text="Fennec", bg="#1e1e1e", fg="white", font=("Segoe UI",18,"bold")).pack(pady=(10,5))
        bar = ttk.Progressbar(sp, length=260, mode="determinate"); bar.pack()
        sp.update()
        for i in range(0, 101, 10): bar["value"]=i; sp.update(); time.sleep(0.018)
        sp.destroy()

    def _ui(self):
        th = THEMES[self._theme]; self.root.config(bg=th["bg"])
        self.root.grid_rowconfigure(1, weight=1); self.root.grid_columnconfigure(0, weight=1)
        # Tab bar
        self._tbar = tk.Frame(self.root, bg=th["ti"], height=32)
        self._tbar.grid(row=0, column=0, sticky="ew"); self._tbar.grid_propagate(False)
        self._tbf = tk.Frame(self._tbar, bg=th["ti"]); self._tbf.pack(side="left", fill="y")
        tk.Button(self._tbar, text=" + ", bd=0, relief="flat", cursor="hand2",
                  bg=th["ti"], fg=th["tfg"], font=("Segoe UI",11), command=self.new_tab).pack(side="left", padx=2)
        # Editor
        self._ec = tk.Frame(self.root, bg=th["bg"]); self._ec.grid(row=1, column=0, sticky="nsew")
        self._ec.grid_rowconfigure(0, weight=1); self._ec.grid_columnconfigure(0, weight=1)
        # Terminal
        self._tf = tk.Frame(self.root, bg="#1e1e1e", height=180)
        self._tf.grid(row=2, column=0, sticky="ew"); self._tf.grid_remove(); self._tf.grid_propagate(False)
        self._tf.grid_rowconfigure(0, weight=1); self._tf.grid_columnconfigure(0, weight=1)
        self._tout = tk.Text(self._tf, bg="#1e1e1e", fg="#d4d4d4", font=("Courier New",10), bd=0, padx=6, state="disabled", wrap="word")
        self._tout.grid(row=0, column=0, sticky="nsew")
        tsb = tk.Scrollbar(self._tf, command=self._tout.yview); tsb.grid(row=0, column=1, sticky="ns")
        self._tout.config(yscrollcommand=tsb.set)
        ef = tk.Frame(self._tf, bg="#2a2a2a"); ef.grid(row=1, column=0, columnspan=2, sticky="ew")
        tk.Label(ef, text="$", bg="#2a2a2a", fg="#00ff88", font=("Courier New",10)).pack(side="left", padx=6)
        self._tcmd = tk.Entry(ef, bg="#2a2a2a", fg="#d4d4d4", insertbackground="white", font=("Courier New",10), bd=0)
        self._tcmd.pack(side="left", fill="x", expand=True, pady=4, padx=2)
        self._tcmd.bind("<Return>", self._run_cmd)
        # Status bar
        self._sf = tk.Frame(self.root, height=24, bg=th["sbg"])
        self._sf.grid(row=3, column=0, sticky="ew"); self._sf.grid_propagate(False); self._sf.grid_columnconfigure(0, weight=1)
        self._sl = tk.Label(self._sf, anchor="w", padx=8, bg=th["sbg"], fg=th["sfg"], font=("Segoe UI",9))
        self._sl.grid(row=0, column=0, sticky="ew")
        self._sr = tk.Label(self._sf, anchor="e", padx=8, bg=th["sbg"], fg=th["sfg"], font=("Segoe UI",9))
        self._sr.grid(row=0, column=1, sticky="e")

    def _cur(self): return self._tabs[self._idx] if self._tabs else None

    def _upd(self):
        t = self._cur()
        if not t: return
        th = THEMES[self._theme]
        for i, tab in enumerate(self._tabs):
            bg = th["ta"] if i==self._idx else th["ti"]
            tab._btn.config(text=tab.label(), bg=bg); tab._cbtn.config(bg=bg); tab._bf.config(bg=bg)
        ln, col = t.ta.index("insert").split(".")
        txt = t.ta.get("1.0", tk.END); w = len(txt.split()) if txt.strip() else 0
        self._sl.config(text=f"  Ln {ln}, Col {int(col)+1}")
        self._sr.config(text=f"{w} words  ·  {self.fsize}pt  ·  UTF-8  ")
        self.root.title(f"Fennec — {t.label()}")

    def new_tab(self, path=None):
        tab = Tab(self._ec, self._fnt, self._upd, self._theme)
        tab.frame.grid(row=0, column=0, sticky="nsew")
        tab.ta.bind("<Button-3>", lambda e, t=tab: self._rclick(e, t))
        idx = len(self._tabs); self._tabs.append(tab); th = THEMES[self._theme]
        bf = tk.Frame(self._tbf, bg=th["ti"]); bf.pack(side="left")
        btn = tk.Button(bf, bd=0, relief="flat", cursor="hand2", padx=10, pady=4,
                        bg=th["ti"], fg=th["tfg"], font=("Segoe UI",9), command=lambda i=idx: self.switch(i))
        btn.pack(side="left")
        cb = tk.Button(bf, text="✕", bd=0, relief="flat", cursor="hand2", padx=4, pady=4,
                       bg=th["ti"], fg="#888", font=("Segoe UI",8), command=lambda i=idx: self.close_tab(i))
        cb.pack(side="left")
        tab._btn = btn; tab._cbtn = cb; tab._bf = bf
        if path: self._load(tab, path)
        self._idx = idx; self.switch(idx)
        return tab

    def switch(self, idx):
        if idx >= len(self._tabs): return
        self._idx = idx
        for t in self._tabs: t.frame.grid_remove()
        self._tabs[idx].frame.grid(); self._tabs[idx].ta.focus_set(); self._upd()

    def close_tab(self, idx):
        if idx >= len(self._tabs): return
        t = self._tabs[idx]
        if t.modified:
            r = messagebox.askyesnocancel("Unsaved", f"Save '{t.label()}'?")
            if r is True: self._save(t)
            elif r is None: return
        t.frame.destroy(); t._bf.destroy(); self._tabs.pop(idx)
        if not self._tabs: self.new_tab(); return
        self._idx = min(idx, len(self._tabs)-1)
        for i, t in enumerate(self._tabs):
            t._btn.config(command=lambda i=i: self.switch(i)); t._cbtn.config(command=lambda i=i: self.close_tab(i))
        self.switch(self._idx)

    def _rclick(self, event, tab):
        idx = tab.ta.index(f"@{event.x},{event.y}"); m = tk.Menu(self.root, tearoff=0)
        if SPELL_OK and "spell" in tab.ta.tag_names(idx):
            ws = tab.ta.index(f"{idx} wordstart"); we = tab.ta.index(f"{idx} wordend")
            w = tab.ta.get(ws, we).strip("'")
            for s in sorted(_spell.candidates(w) or [])[:6]:
                def fix(r=s, a=ws, b=we, tb=tab): tb.ta.delete(a,b); tb.ta.insert(a,r); tb._spellcheck()
                m.add_command(label=s, command=fix)
            m.add_separator()
        for lbl, ev in [("Cut","<<Cut>>"),("Copy","<<Copy>>"),("Paste","<<Paste>>")]:
            m.add_command(label=lbl, command=lambda e=ev, tb=tab: tb.ta.event_generate(e))
        m.tk_popup(event.x_root, event.y_root)

    def _toggle_term(self):
        if self._tf.winfo_ismapped(): self._tf.grid_remove()
        else: self._tf.grid(); self._tcmd.focus_set()

    def _run_cmd(self, e=None):
        cmd = self._tcmd.get().strip()
        if not cmd: return
        self._tcmd.delete(0, tk.END); self._tw(f"$ {cmd}\n")
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if r.stdout: self._tw(r.stdout)
            if r.stderr: self._tw(r.stderr)
        except subprocess.TimeoutExpired: self._tw("Timed out.\n")
        except Exception as ex: self._tw(str(ex)+"\n")

    def _tw(self, txt):
        self._tout.config(state="normal"); self._tout.insert(tk.END, txt)
        self._tout.see(tk.END); self._tout.config(state="disabled")

    def _apply_theme(self):
        th = THEMES[self._theme]
        self.root.config(bg=th["bg"]); self._tbar.config(bg=th["ti"]); self._tbf.config(bg=th["ti"])
        self._sf.config(bg=th["sbg"]); self._sl.config(bg=th["sbg"],fg=th["sfg"]); self._sr.config(bg=th["sbg"],fg=th["sfg"])
        for t in self._tabs: t.retheme(self._theme)
        self._upd()

    def toggle_dark(self):
        self._theme = "dark" if self._theme=="light" else "light"; self._apply_theme()

    def zoom(self, delta):
        ns = max(8, min(48, self.fsize+delta))
        if ns != self.fsize: self.fsize=ns; self._fnt.config(size=ns); self._upd()

    def _load(self, tab, path):
        try:
            with open(path,"r",encoding="utf-8") as f: c=f.read()
            tab.ta.delete("1.0",tk.END); tab.ta.insert(tk.END,c)
            tab.ta.edit_modified(False); tab.modified=False; tab.file_path=path
            self._add_recent(path); tab._sched_hl()
        except Exception as ex: messagebox.showerror("Error",str(ex))

    def _save(self, tab):
        if not tab: return
        if not tab.file_path: return self._save_as(tab)
        try:
            with open(tab.file_path,"w",encoding="utf-8") as f: f.write(tab.ta.get("1.0",tk.END))
            tab.ta.edit_modified(False); tab.modified=False; self._upd()
        except Exception as ex: messagebox.showerror("Error",str(ex))

    def _save_as(self, tab):
        if not tab: return
        p = filedialog.asksaveasfilename(defaultextension=".txt",
            filetypes=[("Text","*.txt"),("Markdown","*.md"),("Python","*.py"),("All","*.*")])
        if p: tab.file_path=p; self._save(tab); self._add_recent(p)

    def new_file(self):
        t = self._cur()
        if t and not t.modified and not t.file_path and not t.ta.get("1.0","end-1c").strip(): return
        self.new_tab()

    def open_file(self):
        p = filedialog.askopenfilename(filetypes=[("Text","*.txt"),("Markdown","*.md"),("Python","*.py"),("All","*.*")])
        if not p: return
        t = self._cur()
        if t and not t.modified and not t.file_path and not t.ta.get("1.0","end-1c").strip(): self._load(t,p)
        else: self.new_tab(p)

    def open_url(self):
        url = simpledialog.askstring("Open URL","Enter URL:",parent=self.root)
        if not url: return
        def fetch():
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Fennec/1.0"}),timeout=10) as r:
                    content = r.read().decode("utf-8","replace")
                self.root.after(0, lambda: self._open_content(url, content))
            except Exception as ex: self.root.after(0, lambda: messagebox.showerror("URL Error",str(ex)))
        threading.Thread(target=fetch, daemon=True).start()

    def _open_content(self, url, content):
        t = self._cur()
        tab = t if (t and not t.modified and not t.file_path and not t.ta.get("1.0","end-1c").strip()) else self.new_tab()
        tab.ta.delete("1.0",tk.END); tab.ta.insert(tk.END,content); tab.ta.edit_modified(False); tab.modified=False
        tab._btn.config(text=(url.split("/")[-1][:18] or "url")); tab._sched_hl()

    def save_session(self):
        data = [{"path":t.file_path,"cursor":t.ta.index("insert"),
                 **({"content":t.ta.get("1.0","end-1c")} if not t.file_path else {})} for t in self._tabs]
        try:
            with open(SESSION,"w") as f: json.dump({"tabs":data,"active":self._idx,"theme":self._theme},f)
        except: pass

    def _load_session(self):
        if not os.path.exists(SESSION): return False
        try:
            with open(SESSION) as f: s=json.load(f)
            self._theme = s.get("theme","light"); loaded = False
            for e in s.get("tabs",[]):
                tab = self.new_tab()
                if e.get("path") and os.path.exists(e["path"]): self._load(tab,e["path"])
                elif e.get("content"): tab.ta.insert(tk.END,e["content"]); tab.ta.edit_modified(False); tab.modified=False
                try: tab.ta.mark_set("insert",e.get("cursor","1.0")); tab.ta.see("insert")
                except: pass
                loaded = True
            if loaded: self.switch(min(s.get("active",0),len(self._tabs)-1)); self._apply_theme(); return True
        except: pass
        return False

    def _add_recent(self, path):
        if path in self.recent: self.recent.remove(path)
        self.recent.insert(0,path); self.recent=self.recent[:10]; self._rmenu.delete(0,tk.END)
        for p in self.recent:
            self._rmenu.add_command(label=os.path.basename(p), command=lambda x=p: self.new_tab(x))

    def find_replace(self):
        t = self._cur()
        if not t: return
        d = tk.Toplevel(self.root); d.title("Find & Replace"); d.resizable(False,False); d.transient(self.root)
        fv,rv,cv = tk.StringVar(),tk.StringVar(),tk.BooleanVar()
        tk.Label(d,text="Find:").grid(row=0,column=0,padx=8,pady=6,sticky="e")
        fe = tk.Entry(d,textvariable=fv,width=28); fe.grid(row=0,column=1,padx=8,pady=6)
        tk.Label(d,text="Replace:").grid(row=1,column=0,padx=8,sticky="e")
        tk.Entry(d,textvariable=rv,width=28).grid(row=1,column=1,padx=8)
        tk.Checkbutton(d,text="Match case",variable=cv).grid(row=2,column=1,sticky="w",padx=8,pady=2)
        msg=tk.Label(d,text="",fg="grey"); msg.grid(row=4,column=0,columnspan=2,pady=(0,6))
        last=[None]
        def fl(): return 0 if cv.get() else re.IGNORECASE
        def c2i(n):
            s=t.ta.get("1.0",tk.END)[:n].split("\n"); return f"{len(s)}.{len(s[-1])}"
        def fnext(*_):
            q=fv.get()
            if not q: return
            txt=t.ta.get("1.0",tk.END); off=len(t.ta.get("1.0",last[0])) if last[0] else 0
            m=re.search(q,txt[off:],fl()) or (off and re.search(q,txt,fl()))
            if not m: msg.config(text="Not found."); return
            base=off if re.search(q,txt[off:],fl()) else 0; s2,e2=c2i(base+m.start()),c2i(base+m.end())
            t.ta.tag_remove("sel","1.0",tk.END); t.ta.tag_add("sel",s2,e2)
            t.ta.mark_set("insert",e2); t.ta.see(s2); last[0]=e2; msg.config(text="")
        def repl():
            try:
                s2,e2=t.ta.index("sel.first"),t.ta.index("sel.last")
                if re.fullmatch(fv.get(),t.ta.get(s2,e2),fl()): t.ta.delete(s2,e2); t.ta.insert(s2,rv.get()); last[0]=s2
            except tk.TclError: pass
            fnext()
        def repl_all():
            txt=t.ta.get("1.0",tk.END); new,n=re.subn(fv.get(),rv.get(),txt,flags=fl())
            if n: t.ta.delete("1.0",tk.END); t.ta.insert("1.0",new); msg.config(text=f"{n} replaced.")
            else: msg.config(text="Not found.")
        bf=tk.Frame(d); bf.grid(row=3,column=0,columnspan=2,pady=8)
        for lbl,cmd in [("Find Next",fnext),("Replace",repl),("Replace All",repl_all),("Close",d.destroy)]:
            tk.Button(bf,text=lbl,command=cmd,width=11).pack(side="left",padx=3)
        fe.focus_set(); d.bind("<Return>",fnext); d.bind("<Escape>",lambda e:d.destroy())

    def go_to_line(self):
        t=self._cur()
        if not t: return
        d=tk.Toplevel(self.root); d.title("Go to Line"); d.resizable(False,False); d.transient(self.root)
        tk.Label(d,text="Line number:").pack(padx=12,pady=(12,4))
        e=tk.Entry(d,width=14); e.pack(padx=12,pady=4); e.focus_set()
        def go():
            try: t.ta.mark_set("insert",f"{int(e.get())}.0"); t.ta.see("insert"); d.destroy()
            except: pass
        tk.Button(d,text="Go",command=go,width=10).pack(pady=(4,12))
        d.bind("<Return>",lambda _:go()); d.bind("<Escape>",lambda _:d.destroy())

    def _menu(self):
        mb=tk.Menu(self.root,tearoff=0)
        fm=tk.Menu(mb,tearoff=0)
        fm.add_command(label="New Tab",    accelerator="Ctrl+T",       command=self.new_tab)
        fm.add_command(label="New",        accelerator="Ctrl+N",       command=self.new_file)
        fm.add_command(label="Open…",      accelerator="Ctrl+O",       command=self.open_file)
        fm.add_command(label="Open URL…",                              command=self.open_url)
        fm.add_command(label="Save",       accelerator="Ctrl+S",       command=lambda:self._save(self._cur()))
        fm.add_command(label="Save As…",   accelerator="Ctrl+Shift+S", command=lambda:self._save_as(self._cur()))
        fm.add_separator(); self._rmenu=tk.Menu(fm,tearoff=0); fm.add_cascade(label="Recent Files",menu=self._rmenu)
        fm.add_separator()
        fm.add_command(label="Close Tab",  accelerator="Ctrl+W",  command=lambda:self.close_tab(self._idx))
        fm.add_command(label="Exit",                               command=self.exit_app)
        mb.add_cascade(label="File",menu=fm)
        em=tk.Menu(mb,tearoff=0)
        em.add_command(label="Undo",accelerator="Ctrl+Z",command=lambda:self._cur().ta.edit_undo())
        em.add_command(label="Redo",accelerator="Ctrl+Y",command=lambda:self._cur().ta.edit_redo())
        em.add_separator()
        for lbl,ev in [("Cut","<<Cut>>"),("Copy","<<Copy>>"),("Paste","<<Paste>>"),("Select All","<<SelectAll>>")]:
            em.add_command(label=lbl,command=lambda e=ev:self._cur().ta.event_generate(e))
        em.add_separator()
        em.add_command(label="Find & Replace…",accelerator="Ctrl+F",command=self.find_replace)
        em.add_command(label="Go to Line…",    accelerator="Ctrl+G",command=self.go_to_line)
        mb.add_cascade(label="Edit",menu=em)
        vm=tk.Menu(mb,tearoff=0)
        vm.add_command(label="Toggle Dark Mode",accelerator="Ctrl+D",command=self.toggle_dark)
        vm.add_separator()
        vm.add_command(label="Zoom In",    accelerator="Ctrl++", command=lambda:self.zoom(2))
        vm.add_command(label="Zoom Out",   accelerator="Ctrl+-", command=lambda:self.zoom(-2))
        vm.add_command(label="Reset Zoom", accelerator="Ctrl+0", command=lambda:self.zoom(self.SIZE-self.fsize))
        vm.add_separator()
        self._wv=tk.BooleanVar(value=True)
        vm.add_checkbutton(label="Word Wrap",variable=self._wv,
                           command=lambda:self._cur().ta.config(wrap="word" if self._wv.get() else "none"))
        vm.add_separator()
        vm.add_command(label="Toggle Terminal",accelerator="Ctrl+`",command=self._toggle_term)
        mb.add_cascade(label="View",menu=vm)
        self.root.config(menu=mb)

    def _keys(self):
        b=self.root.bind
        b("<Control-t>",lambda e:self.new_tab()); b("<Control-w>",lambda e:self.close_tab(self._idx))
        b("<Control-n>",lambda e:self.new_file()); b("<Control-o>",lambda e:self.open_file())
        b("<Control-s>",lambda e:self._save(self._cur())); b("<Control-S>",lambda e:self._save_as(self._cur()))
        b("<Control-f>",lambda e:self.find_replace()); b("<Control-g>",lambda e:self.go_to_line())
        b("<Control-d>",lambda e:self.toggle_dark())
        b("<Control-equal>",lambda e:self.zoom(2)); b("<Control-minus>",lambda e:self.zoom(-2))
        b("<Control-0>",lambda e:self.zoom(self.SIZE-self.fsize))
        b("<Control-MouseWheel>",lambda e:self.zoom(2 if e.delta>0 else -2))
        b("<Control-grave>",lambda e:self._toggle_term())

    def exit_app(self):
        self.save_session()
        for t in self._tabs:
            if t.modified:
                r=messagebox.askyesnocancel("Unsaved",f"Save '{t.label()}'?")
                if r is True: self._save(t)
                elif r is None: return
        self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = Fennec(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()
