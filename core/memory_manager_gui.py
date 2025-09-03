
"""
memory_manager_gui.py

Enhanced Memory Manager window for Igris OS.
Features:
- Live search filter
- Double-click to edit a memory
- Right-click context menu to Pin/Unpin entries
- Delete selected / Clear all
- Export filtered view to TXT or JSON

Drop this file next to your existing GUI scripts and call:
    from memory_manager_gui import open_memory_manager
    open_memory_manager(self)  # from a Tkinter app

Relies on memory_manager.py for storage.
"""

import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, scrolledtext
from datetime import datetime
from typing import List, Dict, Any

try:
    import memory_manager as mm
except Exception as e:
    raise RuntimeError(f"memory_manager_gui requires memory_manager.py. Import failed: {e}")


def _fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Invalid TS"


def _filtered_conversations(convos: List[Dict[str, Any]], q: str) -> List[Dict[str, Any]]:
    q = (q or "").strip().lower()
    if not q:
        return convos
    out = []
    for m in convos:
        blob = f"{m.get('user','')} {m.get('ai','')}".lower()
        if q in blob:
            out.append(m)
    return out


def _sort_conversations(convos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Pinned first, then newest first
    return sorted(convos, key=lambda m: (not m.get("pinned", False), -(m.get("timestamp") or 0)))


def open_memory_manager(parent: tk.Tk | tk.Toplevel):
    data = mm.load_memories()
    convos: List[Dict[str, Any]] = data.get(mm.CONVERSATION_MEMORY_KEY, [])

    top = tk.Toplevel(parent)
    top.title("Memory Manager")
    top.geometry("760x520")

    # Search bar
    search_var = tk.StringVar()
    search_entry = tk.Entry(top, textvariable=search_var)
    search_entry.pack(fill=tk.X, padx=10, pady=(10, 6))
    search_entry.insert(0, "")

    # Listbox (conversations)
    frame = tk.Frame(top)
    frame.pack(fill=tk.BOTH, expand=True, padx=10)

    listbox = tk.Listbox(frame, activestyle="dotbox")
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.config(yscrollcommand=scrollbar.set)

    # Details pane
    details = scrolledtext.ScrolledText(top, wrap=tk.WORD, height=10)
    details.pack(fill=tk.BOTH, expand=False, padx=10, pady=(6,10))

    # Buttons
    btn_frame = tk.Frame(top)
    btn_frame.pack(fill=tk.X, padx=10, pady=(0,10))

    btn_delete = tk.Button(btn_frame, text="Delete Selected")
    btn_clear = tk.Button(btn_frame, text="Clear All")
    btn_export_txt = tk.Button(btn_frame, text="Export TXT")
    btn_export_json = tk.Button(btn_frame, text="Export JSON")

    btn_delete.pack(side=tk.LEFT)
    btn_clear.pack(side=tk.LEFT, padx=(6,0))
    btn_export_txt.pack(side=tk.RIGHT)
    btn_export_json.pack(side=tk.RIGHT, padx=(6,0))

    # Context menu for Pin/Unpin + Edit
    menu = tk.Menu(top, tearoff=0)
    menu.add_command(label="Edit...", command=lambda: _edit_selected())
    menu.add_separator()
    menu.add_command(label="Pin", command=lambda: _set_pin(True))
    menu.add_command(label="Unpin", command=lambda: _set_pin(False))

    # Internal state
    current_view: List[Dict[str, Any]] = []  # filtered + sorted snapshot

    def refresh():
        nonlocal current_view, convos, data
        # Reload from disk to reflect external changes
        data = mm.load_memories()
        convos = data.get(mm.CONVERSATION_MEMORY_KEY, [])
        filt = _filtered_conversations(convos, search_var.get())
        current_view = _sort_conversations(filt)
        listbox.delete(0, tk.END)
        for m in current_view:
            ts = _fmt_ts(m.get("timestamp", 0))
            label = f"[{ts}] {'📌 ' if m.get('pinned') else ''}{m.get('user','')[:80]}"
            listbox.insert(tk.END, label)
        details.delete("1.0", tk.END)

    def on_search(*_):
        refresh()

    def on_select(_=None):
        idx = _get_index()
        details.delete("1.0", tk.END)
        if idx is None:
            return
        m = current_view[idx]
        blob = json.dumps(m, indent=2, ensure_ascii=False)
        details.insert(tk.END, blob)

    def _get_index():
        sel = listbox.curselection()
        if not sel:
            return None
        return int(sel[0])

    def _persist_and_refresh():
        # Save to disk and refresh list
        try:
            data[mm.CONVERSATION_MEMORY_KEY] = convos[-mm.MAX_CONVERSATION_MEMORIES:]
            mm.save_memories(data)
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
        refresh()

    def _edit_selected():
        idx = _get_index()
        if idx is None:
            return
        m = current_view[idx]

        # Resolve the real object within convos by identity (timestamp & text match)
        target = None
        for ref in convos:
            if ref is m or (
                ref.get("timestamp")==m.get("timestamp") and
                ref.get("user")==m.get("user") and
                ref.get("ai")==m.get("ai")
            ):
                target = ref
                break
        if target is None:
            return

        new_user = simpledialog.askstring("Edit - User", "User text:", initialvalue=target.get("user",""), parent=top)
        if new_user is None:
            return
        new_ai = simpledialog.askstring("Edit - AI", "AI text:", initialvalue=target.get("ai",""), parent=top)
        if new_ai is None:
            return

        target["user"] = new_user
        target["ai"] = new_ai
        _persist_and_refresh()

    def _set_pin(flag: bool):
        idx = _get_index()
        if idx is None:
            return
        m = current_view[idx]
        # locate original
        for ref in convos:
            if ref is m or (
                ref.get("timestamp")==m.get("timestamp") and
                ref.get("user")==m.get("user") and
                ref.get("ai")==m.get("ai")
            ):
                ref["pinned"] = bool(flag)
                break
        _persist_and_refresh()

    def delete_selected():
        idx = _get_index()
        if idx is None:
            return
        m = current_view[idx]
        # remove matching element
        convos[:] = [ref for ref in convos if not (
            ref.get("timestamp")==m.get("timestamp") and
            ref.get("user")==m.get("user") and
            ref.get("ai")==m.get("ai")
        )]
        _persist_and_refresh()

    def clear_all():
        if not messagebox.askyesno("Confirm", "Clear ALL conversation memories?"):
            return
        convos.clear()
        _persist_and_refresh()

    def export_txt():
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            for m in current_view:
                ts = _fmt_ts(m.get("timestamp", 0))
                f.write(f"[{ts}] {m.get('user','')}\n  {m.get('ai','')}\n\n")

    def export_json():
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(current_view, f, indent=2, ensure_ascii=False)

    # Bindings
    search_var.trace_add("write", on_search)
    listbox.bind("<<ListboxSelect>>", on_select)
    listbox.bind("<Double-1>", lambda e: _edit_selected())
    listbox.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    btn_delete.config(command=delete_selected)
    btn_clear.config(command=clear_all)
    btn_export_txt.config(command=export_txt)
    btn_export_json.config(command=export_json)

    refresh()
    top.transient(parent)
    top.grab_set()
    top.focus_set()
    top.wait_window()
