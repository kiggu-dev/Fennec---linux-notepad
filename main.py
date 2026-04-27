import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont
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
    "tbg2":"#1e1e1e","tfg":"#d4d4d4"
}

class FennecNotepad:
    FONT, SIZE, STEP, MIN_Z, MAX_Z = "Courier New", 12, 2, 8, 48

    def __init__(self, root):
        self.root = root
        self.root.title("Fennec — Untitled")
        self.root.geometry("960x720")
        self.file_path = None
        self.font_size = self.SIZE
        self.recent = []
        self._font = tkfont.Font(family=self.FONT, size=self.SIZE)
        self._spell_job = None
        self._build_ui()
        self._build_menu()
        self._bind_shortcuts()
        self._status()

    def _build_ui(self):
        self.root.config(bg=THEME["bg"])
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        ef = tk.Frame(self.root, bg=THEME["bg"])
        ef.grid(row=0, column=0, sticky="nsew")
        ef.grid_rowconfigure(0, weight=1)
        ef.grid_columnconfigure(1, weight=1)

        self.ln_canvas = tk.Canvas(ef, width=48, bd=0, highlightthickness=0, bg=THEME["tbg"])
        self.ln_canvas.grid(row=0, column=0, sticky="ns")

        tf = tk.Frame(ef)
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
        for ev in ("<KeyRelease>", "<ButtonRelease>", "<MouseWheel>", "<Configure>"):
            self.ta.bind(ev, self._on_event)
        self.ta.bind("<Button-3>", self._right_click)

        # Terminal panel (hidden by default)
        self.term_frame = tk.Frame(self.root, bg=THEME["tbg2"], height=180)
        self.term_frame.grid(row=1, column=0, sticky="ew")
        self.term_frame.grid_remove()
        self.term_frame.grid_propagate(False)
        self.term_frame.grid_rowconfigure(0, weight=1)
        self.term_frame.grid_columnconfigure(0, weight=1)

        self.term_out = tk.Text(
            self.term_frame, bg=THEME["tbg2"], fg=THEME["tfg"],
            font=("Courier New", 10), bd=0, padx=6, pady=4,
            state="disabled", wrap="word"
        )
        self.term_out.grid(row=0, column=0, sticky="nsew")
        tsb = tk.Scrollbar(self.term_frame, command=self.term_out.yview)
        tsb.grid(row=0, column=1, sticky="ns")
        self.term_out.config(yscrollcommand=tsb.set)

        ef2 = tk.Frame(self.term_frame, bg="#2a2a2a")
        ef2.grid(row=1, column=0, columnspan=2, sticky="ew")
        tk.Label(ef2, text="$", bg="#2a2a2a", fg="#00ff88", font=("Courier New", 10)).pack(side="left", padx=6)
        self.term_entry = tk.Entry(
            ef2, bg="#2a2a2a", fg=THEME["tfg"], insertbackground="white",
            font=("Courier New", 10), bd=0, relief="flat"
        )
        self.term_entry.pack(side="left", fill="x", expand=True, pady=5, padx=2)
        self.term_entry.bind("<Return>", self._run_cmd)

        # Status bar
        sf = tk.Frame(self.root, height=26, bg=THEME["sbg"])
        sf.grid(row=2, column=0, sticky="ew")
        sf.grid_propagate(False)
        sf.grid_columnconfigure(0, weight=1)
        self.st_l = tk.Label(sf, anchor="w", padx=10, bg=THEME["sbg"], fg=THEME["sfg"])
        self.st_l.grid(row=0, column=0, sticky="ew")
        self.st_r = tk.Label(sf, anchor="e", padx=10, bg=THEME["sbg"], fg=THEME["sfg"])
        self.st_r.grid(row=0, column=1, sticky="e")

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
            title = os.path.basename(self.file_path) if self.file_path else "Untitled"
            self.root.title(f"● Fennec — {title}")
            self.ta.edit_modified(False)
            self._schedule_spell()
        self._draw_lines()
        self._status()

    def _on_event(self, event=None):
        self._draw_lines()
        self._status()

    def _status(self):
        ln, col = self.ta.index("insert").split(".")
        txt = self.ta.get("1.0", tk.END)
        w = len(txt.split()) if txt.strip() else 0
        spell_note = "  ·  spell: off (pip install pyspellchecker)" if not SPELL_OK else ""
        self.st_l.config(text=f"  Ln {ln}, Col {int(col)+1}")
        self.st_r.config(text=f"{w} words  ·  {self.font_size}pt  ·  UTF-8{spell_note}  ")

    def _schedule_spell(self):
        if self._spell_job:
            self.root.after_cancel(self._spell_job)
        self._spell_job = self.root.after(600, self._check_spelling)

    def _check_spelling(self):
        if not SPELL_OK: return
        self.ta.tag_remove("misspelled", "1.0", tk.END)
        for lineno, line in enumerate(self.ta.get("1.0", tk.END).split("\n"), 1):
            for m in re.finditer(r"\b[a-zA-Z']+\b", line):
                word = m.group().strip("'")
                if word and _spell.unknown([word]):
                    self.ta.tag_add("misspelled", f"{lineno}.{m.start()}", f"{lineno}.{m.end()}")

    def _right_click(self, event):
        idx = self.ta.index(f"@{event.x},{event.y}")
        menu = tk.Menu(self.root, tearoff=0)
        if SPELL_OK and "misspelled" in self.ta.tag_names(idx):
            ws = self.ta.index(f"{idx} wordstart")
            we = self.ta.index(f"{idx} wordend")
            word = self.ta.get(ws, we).strip("'")
            suggestions = sorted(_spell.candidates(word) or [])[:6]
            if suggestions:
                for s in suggestions:
                    menu.add_command(label=s, command=lambda r=s: self._fix_word(ws, we, r))
                menu.add_separator()
        menu.add_command(label="Cut",   command=lambda: self.ta.event_generate("<<Cut>>"))
        menu.add_command(label="Copy",  command=lambda: self.ta.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: self.ta.event_generate("<<Paste>>"))
        menu.tk_popup(event.x_root, event.y_root)

    def _fix_word(self, start, end, replacement):
        self.ta.delete(start, end)
        self.ta.insert(start, replacement)
        self._check_spelling()

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
            self._term_write(str(ex) + "\n")

    def _term_write(self, text):
        self.term_out.config(state="normal")
        self.term_out.insert(tk.END, text)
        self.term_out.see(tk.END)
        self.term_out.config(state="disabled")

    def _build_menu(self):
        mb = tk.Menu(self.root, tearoff=0)

        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="New",       accelerator="Ctrl+N",       command=self.new_file)
        fm.add_command(label="Open…",     accelerator="Ctrl+O",       command=self.open_file)
        fm.add_command(label="Save",      accelerator="Ctrl+S",       command=self.save_file)
        fm.add_command(label="Save As…",  accelerator="Ctrl+Shift+S", command=self.save_as)
        fm.add_separator()
        self.rec_menu = tk.Menu(fm, tearoff=0)
        fm.add_cascade(label="Recent Files", menu=self.rec_menu)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.exit_app)
        mb.add_cascade(label="File", menu=fm)

        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="Undo",         accelerator="Ctrl+Z", command=self.ta.edit_undo)
        em.add_command(label="Redo",         accelerator="Ctrl+Y", command=self.ta.edit_redo)
        em.add_separator()
        em.add_command(label="Cut",          command=lambda: self.ta.event_generate("<<Cut>>"))
        em.add_command(label="Copy",         command=lambda: self.ta.event_generate("<<Copy>>"))
        em.add_command(label="Paste",        command=lambda: self.ta.event_generate("<<Paste>>"))
        em.add_command(label="Select All",   command=lambda: self.ta.event_generate("<<SelectAll>>"))
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
                           command=lambda: self.ta.config(wrap="word" if self.wrap_var.get() else "none"))
        vm.add_separator()
        vm.add_command(label="Toggle Terminal", accelerator="Ctrl+`", command=self._toggle_terminal)
        mb.add_cascade(label="View", menu=vm)

        self.root.config(menu=mb)

    def _bind_shortcuts(self):
        for k, v in {
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
        d = tk.Toplevel(self.root)
        d.title("Find & Replace"); d.resizable(False, False); d.transient(self.root)
        fv, rv, cv = tk.StringVar(), tk.StringVar(), tk.BooleanVar()
        tk.Label(d, text="Find:").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        fe = tk.Entry(d, textvariable=fv, width=28); fe.grid(row=0, column=1, columnspan=2, padx=8, pady=6)
        tk.Label(d, text="Replace:").grid(row=1, column=0, padx=8, sticky="e")
        tk.Entry(d, textvariable=rv, width=28).grid(row=1, column=1, columnspan=2, padx=8)
        tk.Checkbutton(d, text="Match case", variable=cv).grid(row=2, column=1, sticky="w", padx=8, pady=4)
        msg = tk.Label(d, text="", fg="grey"); msg.grid(row=4, column=0, columnspan=3, pady=(0, 6))
        last = [None]
        def flags(): return 0 if cv.get() else re.IGNORECASE
        def idx_of(n):
            lines = self.ta.get("1.0", tk.END)[:n].split("\n")
            return f"{len(lines)}.{len(lines[-1])}"
        def find_next(*_):
            q = fv.get()
            if not q: return
            txt = self.ta.get("1.0", tk.END)
            off = len(self.ta.get("1.0", last[0])) if last[0] else 0
            m = re.search(q, txt[off:], flags()) or (off and re.search(q, txt, flags()))
            if not m: msg.config(text="No matches found."); return
            base = off if re.search(q, txt[off:], flags()) else 0
            s, e = idx_of(base+m.start()), idx_of(base+m.end())
            self.ta.tag_remove("sel","1.0",tk.END); self.ta.tag_add("sel",s,e)
            self.ta.mark_set("insert",e); self.ta.see(s); last[0]=e; msg.config(text="")
        def replace_one():
            try:
                s, e = self.ta.index("sel.first"), self.ta.index("sel.last")
                if re.fullmatch(fv.get(), self.ta.get(s,e), flags()):
                    self.ta.delete(s,e); self.ta.insert(s,rv.get()); last[0]=s
            except tk.TclError: pass
            find_next()
        def replace_all():
            txt = self.ta.get("1.0", tk.END)
            new, n = re.subn(fv.get(), rv.get(), txt, flags=flags())
            if n: self.ta.delete("1.0",tk.END); self.ta.insert("1.0",new); msg.config(text=f"Replaced {n} occurrence(s).")
            else: msg.config(text="No matches found.")
        bf = tk.Frame(d); bf.grid(row=3, column=0, columnspan=3, pady=8)
        for lbl, cmd in [("Find Next",find_next),("Replace",replace_one),("Replace All",replace_all),("Close",d.destroy)]:
            tk.Button(bf, text=lbl, command=cmd, width=11).pack(side="left", padx=3)
        fe.focus_set(); d.bind("<Return>", find_next); d.bind("<Escape>", lambda e: d.destroy())

    def go_to_line(self):
        d = tk.Toplevel(self.root); d.title("Go to Line"); d.resizable(False,False); d.transient(self.root)
        tk.Label(d, text="Line number:").pack(padx=12, pady=(12,4))
        e = tk.Entry(d, width=14); e.pack(padx=12, pady=4); e.focus_set()
        def jump():
            try: self.ta.mark_set("insert",f"{int(e.get())}.0"); self.ta.see("insert"); self._status(); d.destroy()
            except (ValueError, tk.TclError): pass
        tk.Button(d, text="Go", command=jump, width=10).pack(pady=(4,12))
        d.bind("<Return>", lambda _: jump()); d.bind("<Escape>", lambda _: d.destroy())

    def _add_recent(self, path):
        if path in self.recent: self.recent.remove(path)
        self.recent.insert(0, path); self.recent = self.recent[:8]
        self.rec_menu.delete(0, tk.END)
        for p in self.recent:
            self.rec_menu.add_command(label=os.path.basename(p), command=lambda x=p: self._load(x))

    def new_file(self):
        if self._check():
            self.ta.delete("1.0",tk.END); self.file_path=None; self.root.title("Fennec — Untitled")

    def open_file(self):
        if not self._check(): return
        p = filedialog.askopenfilename(filetypes=[("Text","*.txt"),("Markdown","*.md"),("Python","*.py"),("All","*.*")])
        if p: self._load(p)

    def _load(self, path):
        try:
            with open(path,"r",encoding="utf-8") as f: content = f.read()
            self.ta.delete("1.0",tk.END); self.ta.insert(tk.END,content)
            self.ta.edit_modified(False); self.file_path = path
            self.root.title(f"Fennec — {os.path.basename(path)}")
            self._add_recent(path); self._status(); self._schedule_spell()
        except Exception as ex: messagebox.showerror("Error", str(ex))

    def save_file(self):
        if not self.file_path: return self.save_as()
        try:
            with open(self.file_path,"w",encoding="utf-8") as f: f.write(self.ta.get("1.0",tk.END))
            self.ta.edit_modified(False); self.root.title(f"Fennec — {os.path.basename(self.file_path)}")
        except Exception as ex: messagebox.showerror("Error", str(ex))

    def save_as(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt",
            filetypes=[("Text","*.txt"),("Markdown","*.md"),("Python","*.py"),("All","*.*")])
        if p: self.file_path=p; self.save_file(); self._add_recent(p)

    def _check(self):
        if not self.ta.edit_modified(): return True
        r = messagebox.askyesnocancel("Unsaved Changes","Save changes before proceeding?")
        if r is True: self.save_file()
        return r is not None

    def exit_app(self):
        if self._check(): self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    FennecNotepad(root)
    root.mainloop()