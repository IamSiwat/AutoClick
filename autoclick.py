import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
import ctypes.wintypes
import struct
import sys
import os
import threading
import time
from pynput import keyboard, mouse

# ── Auto-elevate to Admin ──────────────────────────────
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not is_admin():
    # Re-run as admin
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 1
    )
    sys.exit(0)

# ── Windows API: SendInput (works with games) ─────────
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

user32 = ctypes.windll.user32


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT),
    ]


def get_cursor_pos():
    pt = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _send_mouse_event(flags):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp._input.mi.dwFlags = flags
    inp._input.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def win_click(x=None, y=None, button="left", clicks=1):
    """Click using SendInput API — works with games and elevated apps."""
    down_up = {
        "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    }
    down, up = down_up.get(button, down_up["left"])

    if x is not None and y is not None:
        user32.SetCursorPos(x, y)

    for _ in range(clicks):
        _send_mouse_event(down)
        _send_mouse_event(up)


class AutoClicker:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoClick")
        self.root.resizable(False, False)

        self.running = False
        self.mode = tk.StringVar(value="interval")
        self.click_thread = None
        self.recorded_points = []
        self.recording = False

        self._build_ui()
        self._setup_hotkey()

    # ── UI ──────────────────────────────────────────────

    def _build_ui(self):
        # Mode selector
        mode_frame = ttk.LabelFrame(self.root, text="โหมด")
        mode_frame.pack(padx=10, pady=5, fill="x")

        ttk.Radiobutton(
            mode_frame, text="คลิกซ้ำที่จุดเดิม (Interval)",
            variable=self.mode, value="interval", command=self._on_mode_change,
        ).pack(anchor="w", padx=5, pady=2)
        ttk.Radiobutton(
            mode_frame, text="คลิกตามจุดที่บันทึก (Sequence)",
            variable=self.mode, value="sequence", command=self._on_mode_change,
        ).pack(anchor="w", padx=5, pady=2)

        # ── Interval settings ──
        self.interval_frame = ttk.LabelFrame(self.root, text="ตั้งค่า Interval")
        self.interval_frame.pack(padx=10, pady=5, fill="x")

        row = ttk.Frame(self.interval_frame)
        row.pack(padx=5, pady=5, fill="x")

        ttk.Label(row, text="ความเร็ว:").pack(side="left")
        self.hours_var = tk.StringVar(value="0")
        self.mins_var = tk.StringVar(value="0")
        self.secs_var = tk.StringVar(value="0")
        self.ms_var = tk.StringVar(value="100")

        for var, label in [
            (self.hours_var, "ชม."),
            (self.mins_var, "นาที"),
            (self.secs_var, "วินาที"),
            (self.ms_var, "มิลลิวิ"),
        ]:
            e = ttk.Entry(row, textvariable=var, width=5, justify="center")
            e.pack(side="left", padx=2)
            ttk.Label(row, text=label).pack(side="left")

        row2 = ttk.Frame(self.interval_frame)
        row2.pack(padx=5, pady=5, fill="x")
        ttk.Label(row2, text="ปุ่มเมาส์:").pack(side="left")
        self.button_var = tk.StringVar(value="left")
        ttk.Combobox(
            row2, textvariable=self.button_var,
            values=["left", "right", "middle"], state="readonly", width=8,
        ).pack(side="left", padx=5)

        ttk.Label(row2, text="ประเภท:").pack(side="left", padx=(10, 0))
        self.click_type_var = tk.StringVar(value="single")
        ttk.Combobox(
            row2, textvariable=self.click_type_var,
            values=["single", "double"], state="readonly", width=8,
        ).pack(side="left", padx=5)

        # Repeat options
        row3 = ttk.Frame(self.interval_frame)
        row3.pack(padx=5, pady=5, fill="x")
        self.repeat_mode = tk.StringVar(value="infinite")
        ttk.Radiobutton(row3, text="ไม่จำกัด", variable=self.repeat_mode, value="infinite").pack(side="left")
        ttk.Radiobutton(row3, text="จำนวนครั้ง:", variable=self.repeat_mode, value="count").pack(side="left", padx=(10, 0))
        self.repeat_count_var = tk.StringVar(value="10")
        ttk.Entry(row3, textvariable=self.repeat_count_var, width=7, justify="center").pack(side="left", padx=2)

        # ── Sequence settings ──
        self.seq_frame = ttk.LabelFrame(self.root, text="จุดที่บันทึก (Sequence)")

        btn_row = ttk.Frame(self.seq_frame)
        btn_row.pack(padx=5, pady=5, fill="x")
        self.record_btn = ttk.Button(btn_row, text="⏺ เริ่มบันทึก (กดจุดบนหน้าจอ)", command=self._toggle_record)
        self.record_btn.pack(side="left")
        ttk.Button(btn_row, text="🗑 ล้างทั้งหมด", command=self._clear_points).pack(side="left", padx=5)

        self.points_listbox = tk.Listbox(self.seq_frame, height=8, width=50)
        self.points_listbox.pack(padx=5, pady=5, fill="both", expand=True)

        btn_row2 = ttk.Frame(self.seq_frame)
        btn_row2.pack(padx=5, pady=2, fill="x")
        ttk.Button(btn_row2, text="ลบจุดที่เลือก", command=self._delete_selected_point).pack(side="left")

        row_seq_delay = ttk.Frame(self.seq_frame)
        row_seq_delay.pack(padx=5, pady=5, fill="x")
        ttk.Label(row_seq_delay, text="หน่วงระหว่างจุด (ms):").pack(side="left")
        self.seq_delay_var = tk.StringVar(value="500")
        ttk.Entry(row_seq_delay, textvariable=self.seq_delay_var, width=7, justify="center").pack(side="left", padx=5)

        row_seq_repeat = ttk.Frame(self.seq_frame)
        row_seq_repeat.pack(padx=5, pady=5, fill="x")
        self.seq_repeat_mode = tk.StringVar(value="infinite")
        ttk.Radiobutton(row_seq_repeat, text="วนไม่จำกัด", variable=self.seq_repeat_mode, value="infinite").pack(side="left")
        ttk.Radiobutton(row_seq_repeat, text="วนรอบ:", variable=self.seq_repeat_mode, value="count").pack(side="left", padx=(10, 0))
        self.seq_repeat_count_var = tk.StringVar(value="1")
        ttk.Entry(row_seq_repeat, textvariable=self.seq_repeat_count_var, width=7, justify="center").pack(side="left", padx=2)

        # ── Controls ──
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(padx=10, pady=5, fill="x")

        self.start_btn = ttk.Button(ctrl_frame, text="▶ เริ่ม (F6)", command=self._toggle_clicking)
        self.start_btn.pack(side="left", padx=5)

        self.status_label = ttk.Label(ctrl_frame, text="⏸ หยุดอยู่", foreground="gray")
        self.status_label.pack(side="left", padx=10)

        # Coordinates display
        self.coord_label = ttk.Label(self.root, text="เมาส์: (-, -)")
        self.coord_label.pack(padx=10, pady=(0, 5), anchor="w")

        ttk.Label(self.root, text="กด F6 เพื่อเริ่ม/หยุด  |  กด ESC เพื่อหยุดฉุกเฉิน", foreground="gray").pack(pady=(0, 5))

        self._on_mode_change()
        self._update_coords()

    def _on_mode_change(self):
        if self.mode.get() == "interval":
            self.seq_frame.pack_forget()
            self.interval_frame.pack(padx=10, pady=5, fill="x", before=self.root.winfo_children()[-3])
        else:
            self.interval_frame.pack_forget()
            self.seq_frame.pack(padx=10, pady=5, fill="x", before=self.root.winfo_children()[-3])

    def _update_coords(self):
        try:
            x, y = get_cursor_pos()
            self.coord_label.config(text=f"เมาส์: ({x}, {y})")
        except Exception:
            pass
        self.root.after(50, self._update_coords)

    # ── Recording ───────────────────────────────────────

    def _toggle_record(self):
        if self.recording:
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        self.recording = True
        self.record_btn.config(text="⏹ หยุดบันทึก")
        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.mouse_listener.start()

    def _stop_record(self):
        self.recording = False
        self.record_btn.config(text="⏺ เริ่มบันทึก (กดจุดบนหน้าจอ)")
        if hasattr(self, "mouse_listener"):
            self.mouse_listener.stop()

    def _on_mouse_click(self, x, y, button, pressed):
        if pressed and self.recording:
            btn_name = button.name
            self.recorded_points.append((x, y, btn_name))
            self.root.after(0, lambda: self.points_listbox.insert(
                tk.END, f"#{len(self.recorded_points)}  ({x}, {y})  [{btn_name}]"
            ))

    def _clear_points(self):
        self.recorded_points.clear()
        self.points_listbox.delete(0, tk.END)

    def _delete_selected_point(self):
        sel = self.points_listbox.curselection()
        if sel:
            idx = sel[0]
            self.recorded_points.pop(idx)
            self._refresh_points_list()

    def _refresh_points_list(self):
        self.points_listbox.delete(0, tk.END)
        for i, (x, y, btn) in enumerate(self.recorded_points, 1):
            self.points_listbox.insert(tk.END, f"#{i}  ({x}, {y})  [{btn}]")

    # ── Hotkey ──────────────────────────────────────────

    def _setup_hotkey(self):
        self.hotkey_listener = keyboard.Listener(on_press=self._on_key_press)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

    def _on_key_press(self, key):
        if key == keyboard.Key.f6:
            self.root.after(0, self._toggle_clicking)
        elif key == keyboard.Key.esc:
            self.root.after(0, self._stop_clicking)

    # ── Clicking logic ──────────────────────────────────

    def _toggle_clicking(self):
        if self.running:
            self._stop_clicking()
        else:
            self._start_clicking()

    def _start_clicking(self):
        if self.running:
            return

        if self.mode.get() == "sequence" and not self.recorded_points:
            messagebox.showwarning("AutoClick", "ยังไม่ได้บันทึกจุดคลิก!")
            return

        # Stop recording if active
        if self.recording:
            self._stop_record()

        self.running = True
        self.start_btn.config(text="⏹ หยุด (F6)")
        self.status_label.config(text="▶ กำลังคลิก...", foreground="green")

        if self.mode.get() == "interval":
            self.click_thread = threading.Thread(target=self._interval_loop, daemon=True)
        else:
            self.click_thread = threading.Thread(target=self._sequence_loop, daemon=True)
        self.click_thread.start()

    def _stop_clicking(self):
        self.running = False
        self.start_btn.config(text="▶ เริ่ม (F6)")
        self.status_label.config(text="⏸ หยุดอยู่", foreground="gray")

    def _get_interval_seconds(self):
        try:
            h = int(self.hours_var.get() or 0)
            m = int(self.mins_var.get() or 0)
            s = int(self.secs_var.get() or 0)
            ms = int(self.ms_var.get() or 0)
            return h * 3600 + m * 60 + s + ms / 1000
        except ValueError:
            return 0.1

    def _interval_loop(self):
        interval = self._get_interval_seconds()
        if interval <= 0:
            interval = 0.001

        button = self.button_var.get()
        clicks = 2 if self.click_type_var.get() == "double" else 1
        is_infinite = self.repeat_mode.get() == "infinite"

        try:
            max_count = int(self.repeat_count_var.get()) if not is_infinite else 0
        except ValueError:
            max_count = 10

        count = 0
        while self.running:
            win_click(button=button, clicks=clicks)
            count += 1
            if not is_infinite and count >= max_count:
                break
            # Sleep in small chunks so we can stop quickly
            elapsed = 0
            while elapsed < interval and self.running:
                time.sleep(min(0.01, interval - elapsed))
                elapsed += 0.01

        self.root.after(0, self._stop_clicking)

    def _sequence_loop(self):
        try:
            delay = int(self.seq_delay_var.get() or 500) / 1000
        except ValueError:
            delay = 0.5

        is_infinite = self.seq_repeat_mode.get() == "infinite"
        try:
            max_rounds = int(self.seq_repeat_count_var.get()) if not is_infinite else 0
        except ValueError:
            max_rounds = 1

        rounds = 0
        while self.running:
            for x, y, btn in self.recorded_points:
                if not self.running:
                    break
                win_click(x, y, button=btn)
                elapsed = 0
                while elapsed < delay and self.running:
                    time.sleep(min(0.01, delay - elapsed))
                    elapsed += 0.01
            rounds += 1
            if not is_infinite and rounds >= max_rounds:
                break

        self.root.after(0, self._stop_clicking)


def main():
    root = tk.Tk()
    AutoClicker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
