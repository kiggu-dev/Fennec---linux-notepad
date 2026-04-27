import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont, ttk
import os, re, subprocess

try:
    from spellchecker import SpellChecker
    _spell = SpellChecker()
    SPELL_OK = True
except ImportError:
    SPELL_OK = False

THEME = {
    "bg":"#f5f0eb","tbg":"#ffffff","fg":"#1a1a1a","cur":"#1a1a1a",
    "sbg":"#e8e0d5","sfg":"#5a4a3a","ln":"#9a8878","sel":"#c8e6c9",
    "tbg2":"#1e1e1e","tfg":"#d4d4d4","tab_active":"#ffffff",
    "tab_inactive":"#ddd8d2","tab_fg":"#1a1a1a"
}

class EditorTab:
    def __init__(self, notebook, font, on_change):
        self.file_path = None
        self.modified = False
        self._spell_job = None
        self._font = font
        self._on_change = on_change

        self.frame = tk.Frame(notebook, bg=THEME["bg"])
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(1, weight=1)

        self.ln_canvas = tk.Canvas(self.frame, width=48, bd=0, highlightthickness=0, bg=THEME["tbg"])
        self.ln_canvas.grid(row=0, column=0, sticky="ns")

        tf = tk.Frame(self.frame)
        tf.grid(row=0, column=1, sticky="nsew")
        tf.grid_rowconfigure(0, weight=1)
        tf.grid_columnconfigure(0, weight=1)

        self.sb_y = tk.Scrollbar(tf)
        self.sb_y.grid(row=0, column=1, sticky="ns")
        self.sb_x = tk.Scrollbar(tf, orient="horizontal")
        self.sb_x.grid(row=1, column=0, sticky="ew")

        self.ta = tk.Text(
            tf, undo=True, wrap="word", font=self._font, bd=0, padx=10, pady=8,
            yscrollcommand=self._yscroll, xscrollcommand=self.sb_x.set,
            bg=THEME["tbg"], fg=THEME["fg"], insertbackground=THEME["cur"],
            selectbackground=THEME["sel"]
        )
        self.ta.grid(row=0, column=0, sticky="nsew")
        self.sb_y.config(command=self.ta.yview)
        self.sb_x.config(command=self.ta.xview)
        self.ta.tag_config("misspelled", underline=True, foreground="#cc2222")

        self.ta.bind("<<Modified>>", self._on_modified)
        for ev in ("<KeyRelease>","<ButtonRelease>","<MouseWheel>","<Configure>"):
            self.ta.bind(ev, self._on_event)

    def _yscroll(self, *a):
        self.sb_y.set(*a)
        self._draw_lines()

    def _draw_lines(self, *_):
        c = self.ln_canvas
        c.delete("all")
        i = self.ta.index("@0,0")
        while True:
            dl = self.ta.dlineinfo(i)
            if dl is None: break
            c.create_text(42, dl[1], anchor="ne", text=i.split(".")[0], font=self._font, fill=THEME["ln"])
            ni = self.ta.index(f"{i}+1line")
            if ni == i: break
            i = ni

    def _on_modified(self, event=None):
        if self.ta.edit_modified():
            self.modified = True
            self.ta.edit_modified(False)
            self._on_change()
            self._schedule_spell()
        self._draw_lines()

    def _on_event(self, event=None):
        self._draw_lines()
        self._on_change()

    def _schedule_spell(self):
        if self._spell_job:
            self.ta.after_cancel(self._spell_job)
        self._spell_job = self.ta.after(600, self._check_spelling)

    def _check_spelling(self):
        if not SPELL_OK: return
        self.ta.tag_remove("misspelled","1.0",tk.END)
        for lineno, line in enumerate(self.ta.get("1.0",tk.END).split("\n"), 1):
            for m in re.finditer(r"\b[a-zA-Z']+\b", line):
                word = m.group().strip("'")
                if word and _spell.unknown([word]):
                    self.ta.tag_add("misspelled",f"{lineno}.{m.start()}",f"{lineno}.{m.end()}")

    def get_title(self):
        name = os.path.basename(self.file_path) if self.file_path else "Untitled"
        return ("● " if self.modified else "") + name


class FennecNotepad:
    FONT, SIZE, STEP, MIN_Z, MAX_Z = "Courier New", 12, 2, 8, 48

    def __init__(self, root):
        self.root = root
        self.root.title("Fennec")
        self.root.geometry("960x720")
        self.root.config(bg=THEME["bg"])
        self.font_size = self.SIZE
        self.recent = []
        self._font = tkfont.Font(family=self.FONT, size=self.SIZE)
        self._tabs = []
        self._build_ui()
        self._build_menu()
        self._bind_shortcuts()
        self.new_tab()

    def _build_ui(self):
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Tab bar
        tab_bar_frame = tk.Frame(self.root, bg=THEME["tab_inactive"], height=34)
        tab_bar_frame.grid(row=0, column=0, sticky="ew")
        tab_bar_frame.grid_propagate(False)

        self.tab_bar = tk.Frame(tab_bar_frame, bg=THEME["tab_inactive"])
        self.tab_bar.pack(side="left", fill="y")

        new_btn = tk.Button(
            tab_bar_frame, text=" + ", bd=0, relief="flat", cursor="hand2",
            bg=THEME["tab_inactive"], fg=THEME["tab_fg"], font=("Segoe UI", 11),
            command=self.new_tab, activebackground=THEME["bg"]
        )
        new_btn.pack(side="left", padx=4)

        # Editor area
        self.editor_container = tk.Frame(self.root, bg=THEME["bg"])
        self.editor_container.grid(row=1, column=0, sticky="nsew")
        self.editor_container.grid_rowconfigure(0, weight=1)
        self.editor_container.grid_columnconfigure(0, weight=1)

        # Terminal
        self.term_frame = tk.Frame(self.root, bg=THEME["tbg2"], height=180)
        self.term_frame.grid(row=2, column=0, sticky="ew")
        self.term_frame.grid_remove()
        self.term_frame.grid_propagate(False)
        self.term_frame.grid_rowconfigure(0, weight=1)
        self.term_frame.grid_columnconfigure(0, weight=1)

        self.term_out = tk.Text(
            self.term_frame, bg=THEME["tbg2"], fg=THEME["tfg"],
            font=("Courier New",10), bd=0, padx=6, pady=4,
            state="disabled", wrap="word"
        )
        self.term_out.grid(row=0, column=0, sticky="nsew")
        tsb = tk.Scrollbar(self.term_frame, command=self.term_out.yview)
        tsb.grid(row=0, column=1, sticky="ns")
        self.term_out.config(yscrollcommand=tsb.set)

        ef2 = tk.Frame(self.term_frame, bg="#2a2a2a")
        ef2.grid(row=1, column=0, columnspan=2, sticky="ew")
        tk.Label(ef2, text="$", bg="#2a2a2a", fg="#00ff88", font=("Courier New",10)).pack(side="left", padx=6)
        self.term_entry = tk.Entry(
            ef2, bg="#2a2a2a", fg=THEME["tfg"], insertbackground="white",
            font=("Courier New",10), bd=0, relief="flat"
        )
        self.term_entry.pack(side="left", fill="x", expand=True, pady=5, padx=2)
        self.term_entry.bind("<Return>", self._run_cmd)

        # Status bar
        sf = tk.Frame(self.root, height=26, bg=THEME["sbg"])
        sf.grid(row=3, column=0, sticky="ew")
        sf.grid_propagate(False)
        sf.grid_columnconfigure(0, weight=1)
        self.st_l = tk.Label(sf, anchor="w", padx=10, bg=THEME["sbg"], fg=THEME["sfg"])
        self.st_l.grid(row=0, column=0, sticky="ew")
        self.st_r = tk.Label(sf, anchor="e", padx=10, bg=THEME["sbg"], fg=THEME["sfg"])
        self.st_r.grid(row=0, column=1, sticky="e")

    def _current(self):
        if not self._tabs: return None
        return self._tabs[self._active_idx]

    def new_tab(self, file_path=None):
        tab = EditorTab(self.editor_container, self._font, self._on_tab_change)
        tab.frame.grid(row=0, column=0, sticky="nsew")
        tab.ta.bind("<Button-3>", lambda e, t=tab: self._right_click(e, t))

        idx = len(self._tabs)
        self._tabs.append(tab)

        btn_frame = tk.Frame(self.tab_bar, bg=THEME["tab_inactive"])
        btn_frame.pack(side="left")

        btn = tk.Button(
            btn_frame, bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 9), padx=10, pady=6,
            bg=THEME["tab_inactive"], fg=THEME["tab_fg"],
            activebackground=THEME["tab_active"],
            command=lambda i=idx: self.switch_tab(i)
        )
        btn.pack(side="left")

        close = tk.Button(
            btn_frame, text="✕", bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 8), padx=4, pady=6,
            bg=THEME["tab_inactive"], fg="#888",
            activebackground=THEME["tab_active"],
            command=lambda i=idx: self.close_tab(i)
        )
        close.pack(side="left")

        tab._btn = btn
        tab._btn_frame = btn_frame
        tab._close_btn = close

        if file_path:
            self._load_into(tab, file_path)

        self._active_idx = idx
        self.switch_tab(idx)
        return tab

    def switch_tab(self, idx):
        if idx >= len(self._tabs): return
        self._active_idx = idx
        for i, tab in enumerate(self._tabs):
            tab.frame.grid_remove()
            tab._btn_frame.config(bg=THEME["tab_inactive"])
            tab._btn.config(bg=THEME["tab_inactive"])
            tab._close_btn.config(bg=THEME["tab_inactive"])
        t = self._tabs[idx]
        t.frame.grid()
        t._btn_frame.config(bg=THEME["tab_active"])
        t._btn.config(bg=THEME["tab_active"])
        t._close_btn.config(bg=THEME["tab_active"])
        t.ta.focus_set()
        self._refresh_tab_labels()
        self._status()
        self.root.title(f"Fennec — {t.get_title()}")

    def close_tab(self, idx):
        if idx >= len(self._tabs): return
        tab = self._tabs[idx]
        if tab.modified:
            r = messagebox.askyesnocancel("Unsaved Changes", "Save before closing this tab?")
            if r is True: self._save_tab(tab)
            elif r is None: return
        tab.frame.destroy()
        tab._btn_frame.destroy()
        self._tabs.pop(idx)
        if not self._tabs:
            self.new_tab()
            return
        self._active_idx = min(idx, len(self._tabs)-1)
        for i, t in enumerate(self._tabs):
            t._btn.config(command=lambda i=i: self.switch_tab(i))
            t._close_btn.config(command=lambda i=i: self.close_tab(i))
        self.switch_tab(self._active_idx)

    def _on_tab_change(self):
        t = self._current()
        if not t: return
        self._refresh_tab_labels()
        self._status()
        self.root.title(f"Fennec — {t.get_title()}")

    def _refresh_tab_labels(self):
        for tab in self._tabs:
            tab._btn.config(text=tab.get_title())

    def _status(self):
        t = self._current()
        if not t: return
        ln, col = t.ta.index("insert").split(".")
        txt = t.ta.get("1.0", tk.END)
        w = len(txt.split()) if txt.strip() else 0
        self.st_l.config(text=f"  Ln {ln}, Col {int(col)+1}")
        self.st_r.config(text=f"{w} words  ·  {self.font_size}pt  ·  UTF-8  ")

    def _right_click(self, event, tab):
        idx = tab.ta.index(f"@{event.x},{event.y}")
        menu = tk.Menu(self.root, tearoff=0)
        if SPELL_OK and "misspelled" in tab.ta.tag_names(idx):
            ws = tab.ta.index(f"{idx} wordstart")
            we = tab.ta.index(f"{idx} wordend")
            word = tab.ta.get(ws, we).strip("'")
            suggestions = sorted(_spell.candidates(word) or [])[:6]
            if suggestions:
                for s in suggestions:
                    menu.add_command(label=s, command=lambda r=s: self._fix_word(tab, ws, we, r))
                menu.add_separator()
        menu.add_command(label="Cut",   command=lambda: tab.ta.event_generate("<<Cut>>"))
        menu.add_command(label="Copy",  command=lambda: tab.ta.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: tab.ta.event_generate("<<Paste>>"))
        menu.tk_popup(event.x_root, event.y_root)

    def _fix_word(self, tab, start, end, replacement):
        tab.ta.delete(start, end)
        tab.ta.insert(start, replacement)
        tab._check_spelling()

    def _toggle_terminal(self):
        if self.term_frame.winfo_ismapped():
            self.term_frame.grid_remove()
        else:
            self.term_frame.grid()
            self.term_entry.focus_set()

    def _run_cmd(self, event=None):
        cmd = self.term_entry.get().strip()
        if not cmd: return
        self.term_entry.delete(0, tk.END)
        self._term_write(f"$ {cmd}\n")
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if r.stdout: self._term_write(r.stdout)
            if r.stderr: self._term_write(r.stderr)
        except subprocess.TimeoutExpired:
            self._term_write("Command timed out.\n")
        except Exception as ex:
            self._term_write(str(ex)+"\n")

    def _term_write(self, text):
        self.term_out.config(state="normal")
        self.term_out.insert(tk.END, text)
        self.term_out.see(tk.END)
        self.term_out.config(state="disabled")

    def _build_menu(self):
        mb = tk.Menu(self.root, tearoff=0)

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="New Tab",    accelerator="Ctrl+T",       command=self.new_tab)
        fm.add_command(label="New",        accelerator="Ctrl+N",       command=self.new_file)
        fm.add_command(label="Open…",      accelerator="Ctrl+O",       command=self.open_file)
        fm.add_command(label="Save",       accelerator="Ctrl+S",       command=self.save_file)
        fm.add_command(label="Save As…",   accelerator="Ctrl+Shift+S", command=self.save_as)
        fm.add_separator()
        self.rec_menu = tk.Menu(fm, tearoff=0)
        fm.add_cascade(label="Recent Files", menu=self.rec_menu)
        fm.add_separator()
        fm.add_command(label="Close Tab",  accelerator="Ctrl+W",       command=lambda: self.close_tab(self._active_idx))
        fm.add_command(label="Exit",                                    command=self.exit_app)
        mb.add_cascade(label="File", menu=fm)

        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="Undo",       accelerator="Ctrl+Z", command=lambda: self._current().ta.edit_undo())
        em.add_command(label="Redo",       accelerator="Ctrl+Y", command=lambda: self._current().ta.edit_redo())
        em.add_separator()
        em.add_command(label="Cut",        command=lambda: self._current().ta.event_generate("<<Cut>>"))
        em.add_command(label="Copy",       command=lambda: self._current().ta.event_generate("<<Copy>>"))
        em.add_command(label="Paste",      command=lambda: self._current().ta.event_generate("<<Paste>>"))
        em.add_command(label="Select All", command=lambda: self._current().ta.event_generate("<<SelectAll>>"))
        em.add_separator()
        em.add_command(label="Find & Replace…", accelerator="Ctrl+F", command=self.find_replace)
        em.add_command(label="Go to Line…",     accelerator="Ctrl+G", command=self.go_to_line)
        mb.add_cascade(label="Edit", menu=em)

        vm = tk.Menu(mb, tearoff=0)
        vm.add_command(label="Zoom In",    accelerator="Ctrl++", command=self.zoom_in)
        vm.add_command(label="Zoom Out",   accelerator="Ctrl+-", command=self.zoom_out)
        vm.add_command(label="Reset Zoom", accelerator="Ctrl+0", command=self.zoom_reset)
        vm.add_separator()
        self.wrap_var = tk.BooleanVar(value=True)
        vm.add_checkbutton(label="Word Wrap", variable=self.wrap_var,
                           command=lambda: self._current().ta.config(wrap="word" if self.wrap_var.get() else "none"))
        vm.add_separator()
        vm.add_command(label="Toggle Terminal", accelerator="Ctrl+`", command=self._toggle_terminal)
        mb.add_cascade(label="View", menu=vm)

        self.root.config(menu=mb)

    def _bind_shortcuts(self):
        for k, v in {
            "<Control-t>":          lambda e: self.new_tab(),
            "<Control-w>":          lambda e: self.close_tab(self._active_idx),
            "<Control-n>":          lambda e: self.new_file(),
            "<Control-o>":          lambda e: self.open_file(),
            "<Control-s>":          lambda e: self.save_file(),
            "<Control-S>":          lambda e: self.save_as(),
            "<Control-f>":          lambda e: self.find_replace(),
            "<Control-g>":          lambda e: self.go_to_line(),
            "<Control-equal>":      lambda e: self.zoom_in(),
            "<Control-minus>":      lambda e: self.zoom_out(),
            "<Control-0>":          lambda e: self.zoom_reset(),
            "<Control-MouseWheel>": lambda e: self.zoom_in() if e.delta > 0 else self.zoom_out(),
            "<Control-grave>":      lambda e: self._toggle_terminal(),
        }.items():
            self.root.bind(k, v)

    def zoom_in(self):
        if self.font_size < self.MAX_Z:
            self.font_size += self.STEP; self._font.config(size=self.font_size); self._status()

    def zoom_out(self):
        if self.font_size > self.MIN_Z:
            self.font_size -= self.STEP; self._font.config(size=self.font_size); self._status()

    def zoom_reset(self):
        self.font_size = self.SIZE; self._font.config(size=self.font_size); self._status()

    def find_replace(self):
        t = self._current()
        if not t: return
        d = tk.Toplevel(self.root)
        d.title("Find & Replace"); d.resizable(False,False); d.transient(self.root)
        fv, rv, cv = tk.StringVar(), tk.StringVar(), tk.BooleanVar()
        tk.Label(d, text="Find:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        fe = tk.Entry(d, textvariable=fv, width=28); fe.grid(row=0, column=1, columnspan=2, padx=8, pady=6)
        tk.Label(d, text="Replace:").grid(row=1, column=0, padx=8, sticky="e")
        tk.Entry(d, textvariable=rv, width=28).grid(row=1, column=1, columnspan=2, padx=8)
        tk.Checkbutton(d, text="Match case", variable=cv).grid(row=2, column=1, sticky="w", padx=8, pady=4)
        msg = tk.Label(d, text="", fg="grey"); msg.grid(row=4, column=0, columnspan=3, pady=(0,6))
        last = [None]
        def flags(): return 0 if cv.get() else re.IGNORECASE
        def idx_of(n):
            lines = t.ta.get("1.0",tk.END)[:n].split("\n")
            return f"{len(lines)}.{len(lines[-1])}"
        def find_next(*_):
            q = fv.get()
            if not q: return
            txt = t.ta.get("1.0",tk.END)
            off = len(t.ta.get("1.0",last[0])) if last[0] else 0
            m = re.search(q,txt[off:],flags()) or (off and re.search(q,txt,flags()))
            if not m: msg.config(text="No matches found."); return
            base = off if re.search(q,txt[off:],flags()) else 0
            s,e = idx_of(base+m.start()),idx_of(base+m.end())
            t.ta.tag_remove("sel","1.0",tk.END); t.ta.tag_add("sel",s,e)
            t.ta.mark_set("insert",e); t.ta.see(s); last[0]=e; msg.config(text="")
        def replace_one():
            try:
                s,e = t.ta.index("sel.first"),t.ta.index("sel.last")
                if re.fullmatch(fv.get(),t.ta.get(s,e),flags()):
                    t.ta.delete(s,e); t.ta.insert(s,rv.get()); last[0]=s
            except tk.TclError: pass
            find_next()
        def replace_all():
            txt = t.ta.get("1.0",tk.END)
            new,n = re.subn(fv.get(),rv.get(),txt,flags=flags())
            if n: t.ta.delete("1.0",tk.END); t.ta.insert("1.0",new); msg.config(text=f"Replaced {n} occurrence(s).")
            else: msg.config(text="No matches found.")
        bf = tk.Frame(d); bf.grid(row=3,column=0,columnspan=3,pady=8)
        for lbl,cmd in [("Find Next",find_next),("Replace",replace_one),("Replace All",replace_all),("Close",d.destroy)]:
            tk.Button(bf,text=lbl,command=cmd,width=11).pack(side="left",padx=3)
        fe.focus_set(); d.bind("<Return>",find_next); d.bind("<Escape>",lambda e: d.destroy())

    def go_to_line(self):
        t = self._current()
        if not t: return
        d = tk.Toplevel(self.root); d.title("Go to Line"); d.resizable(False,False); d.transient(self.root)
        tk.Label(d, text="Line number:").pack(padx=12, pady=(12,4))
        e = tk.Entry(d, width=14); e.pack(padx=12, pady=4); e.focus_set()
        def jump():
            try: t.ta.mark_set("insert",f"{int(e.get())}.0"); t.ta.see("insert"); self._status(); d.destroy()
            except (ValueError,tk.TclError): pass
        tk.Button(d, text="Go", command=jump, width=10).pack(pady=(4,12))
        d.bind("<Return>", lambda _: jump()); d.bind("<Escape>", lambda _: d.destroy())

    def _add_recent(self, path):
        if path in self.recent: self.recent.remove(path)
        self.recent.insert(0,path); self.recent=self.recent[:8]
        self.rec_menu.delete(0,tk.END)
        for p in self.recent:
            self.rec_menu.add_command(label=os.path.basename(p), command=lambda x=p: self.new_tab(x))

    def new_file(self):
        t = self._current()
        if not t: return
        if t.modified:
            r = messagebox.askyesnocancel("Unsaved Changes","Save changes before proceeding?")
            if r is True: self._save_tab(t)
            elif r is None: return
        t.ta.delete("1.0",tk.END); t.file_path=None; t.modified=False
        self._on_tab_change()

    def open_file(self):
        p = filedialog.askopenfilename(filetypes=[("Text","*.txt"),("Markdown","*.md"),("Python","*.py"),("All","*.*")])
        if p:
            t = self._current()
            if t and not t.modified and t.file_path is None and not t.ta.get("1.0",tk.END).strip():
                self._load_into(t, p)
            else:
                self.new_tab(p)

    def _load_into(self, tab, path):
        try:
            with open(path,"r",encoding="utf-8") as f: content=f.read()
            tab.ta.delete("1.0",tk.END); tab.ta.insert(tk.END,content)
            tab.ta.edit_modified(False); tab.modified=False
            tab.file_path=path
            self._add_recent(path)
            self._on_tab_change()
            tab._schedule_spell()
        except Exception as ex: messagebox.showerror("Error",str(ex))

    def _save_tab(self, tab):
        if not tab.file_path: return self._save_tab_as(tab)
        try:
            with open(tab.file_path,"w",encoding="utf-8") as f: f.write(tab.ta.get("1.0",tk.END))
            tab.ta.edit_modified(False); tab.modified=False
            self._on_tab_change()
        except Exception as ex: messagebox.showerror("Error",str(ex))

    def _save_tab_as(self, tab):
        p = filedialog.asksaveasfilename(defaultextension=".txt",
            filetypes=[("Text","*.txt"),("Markdown","*.md"),("Python","*.py"),("All","*.*")])
        if p: tab.file_path=p; self._save_tab(tab); self._add_recent(p)

    def save_file(self):
        t = self._current()
        if t: self._save_tab(t)

    def save_as(self):
        t = self._current()
        if t: self._save_tab_as(t)

    def exit_app(self):
        for tab in self._tabs:
            if tab.modified:
                r = messagebox.askyesnocancel("Unsaved Changes", f"Save '{tab.get_title()}' before exiting?")
                if r is True: self._save_tab(tab)
                elif r is None: return
        self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    FennecNotepad(root)
    root.mainloop()
