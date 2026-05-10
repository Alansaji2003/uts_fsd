"""GUIUniApp — modern CustomTkinter GUI wrapper.

Reads/writes the same `students.data` file as the CLI.
Login-only (no admin), max 4 subjects, exception popups for errors.

All screens run inside a single fullscreen window with back-button
navigation. Light mode. The login screen uses the UTS campus image as
its background; the enrolment and subjects screens use an animated
constellation particle background. Every card has a frosted-glass look
(stipple) so the underlying background shows through.

Run:
    python gui_app.py
"""
import os
import tkinter as tk
import customtkinter as ctk
import random
import math

from PIL import Image, ImageTk, ImageDraw

from models.database import Database
from models.subject import Subject
from utils.validators import is_valid_email, is_valid_password


# ---------------------------------------------------------------------- THEME
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Colours --------------------------------------------------------------------
PRIMARY = "#3b82f6"
PRIMARY_HOVER = "#2563eb"
DANGER = "#ef4444"
DANGER_HOVER = "#dc2626"
SUCCESS = "#10b981"

SURFACE = "#f5f7fa"
CARD = "#e8eef7"             # soft slate-tinted card (distinct from white surface)
NESTED = "#dbe4f0"           # slightly darker than card, also tinted
TEXT = "#0f172a"
MUTED = "#475569"            # slightly darker so it reads on the tinted card
BORDER = "#94a3b8"

NEUTRAL_BTN = "#cbd5e1"
NEUTRAL_BTN_HOVER = "#94a3b8"
GHOST_BTN_HOVER = "#cbd5e1"

# Layout ---------------------------------------------------------------------
CARD_WIDTH = 620
CARD_RADIUS = 20

# Fonts ----------------------------------------------------------------------
FONT_TITLE = ("Segoe UI", 28, "bold")
FONT_HEADING = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_MONO = ("Consolas", 13)


# ====================================================================== BACKGROUND CANVAS
class AnimatedBackground(tk.Canvas):
    """Canvas-based background. Two modes:

    * num_particles > 0  → constellation animation (default)
    * background_image   → renders an image, scaled-cover to fill canvas

    Either way it also hosts the frosted-card overlay so the constellation
    OR the image shows through the card.
    """

    CONNECT_DIST = 140
    DOT_COLOR = "#7c93b3"

    _FADE_TABLE: list[str] | None = None

    @classmethod
    def _build_fade_table(cls):
        if cls._FADE_TABLE is not None:
            return
        r1, g1, b1 = 0x55, 0x70, 0x95
        r2, g2, b2 = 0xf5, 0xf7, 0xfa
        table = []
        for i in range(101):
            ratio = i / 100.0
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            table.append(f"#{r:02x}{g:02x}{b:02x}")
        cls._FADE_TABLE = table

    def __init__(self, parent, *, num_particles=40, background_image=None):
        super().__init__(parent, bg=SURFACE, highlightthickness=0, bd=0)
        self._build_fade_table()

        # mode flags
        self._image_mode = background_image is not None

        # animation state
        self._particles: list[dict] = []
        self._line_pool: list[int] = []
        self._active_lines = 0
        self._num = num_particles if not self._image_mode else 0
        self._running = False
        self._initialized = False

        # image-mode state
        self._bg_pil = background_image       # may be None
        self._bg_photo = None                 # PhotoImage handle (must persist)
        self._bg_image_id = None
        self._bg_last_size = (0, 0)
        self._bg_resize_after = None

        # canvas dims
        self._cw = 1920
        self._ch = 1080

        # frosted card overlay (rendered as a single PIL RGBA image for
        # real alpha + smooth corners — no canvas-shape compositing seams)
        self._frost_photo = None
        self._frost_id = None
        self._frost_last_key = None  # (x, y, w, h) cache key

        self.bind("<Configure>", self._on_resize)

    # ---- lifecycle ---------------------------------------------------------
    def start(self):
        """Start animation if in particle mode. Image mode draws once and
        only on resize."""
        if not self._initialized:
            self._initialized = True
            self.update_idletasks()
            self._cw = max(self.winfo_width(), 800)
            self._ch = max(self.winfo_height(), 600)
            if self._image_mode:
                self._render_bg_image(force=True)
            else:
                self._create_particles()
        if not self._image_mode and not self._running:
            self._running = True
            self._tick()

    def stop(self):
        self._running = False

    # ---- resize handler ----------------------------------------------------
    def _on_resize(self, event):
        self._cw = event.width
        self._ch = event.height
        if self._image_mode:
            # debounce so LANCZOS doesn't run on every <Configure>
            if self._bg_resize_after is not None:
                try:
                    self.after_cancel(self._bg_resize_after)
                except Exception:
                    pass
            self._bg_resize_after = self.after(80, self._render_bg_image)

    # ---- image mode --------------------------------------------------------
    def _render_bg_image(self, force=False):
        self._bg_resize_after = None
        if self._bg_pil is None:
            return
        cw, ch = self._cw, self._ch
        if cw < 2 or ch < 2:
            return
        if not force and (cw, ch) == self._bg_last_size:
            return
        self._bg_last_size = (cw, ch)

        iw, ih = self._bg_pil.size
        scale = max(cw / iw, ch / ih)   # cover
        nw, nh = int(iw * scale), int(ih * scale)
        resized = self._bg_pil.resize((nw, nh), Image.LANCZOS)
        left = (nw - cw) // 2
        top = (nh - ch) // 2
        cropped = resized.crop((left, top, left + cw, top + ch))
        self._bg_photo = ImageTk.PhotoImage(cropped)

        if self._bg_image_id is None:
            self._bg_image_id = self.create_image(
                0, 0, anchor="nw", image=self._bg_photo,
            )
            self.tag_lower(self._bg_image_id)
        else:
            self.itemconfigure(self._bg_image_id, image=self._bg_photo)

        # frost should sit on top of the image
        if self._frost_id is not None:
            self.tag_raise(self._frost_id)

    # ---- particle setup ----------------------------------------------------
    def _create_particles(self):
        for _ in range(self._num):
            p = {
                'x': random.uniform(0, self._cw),
                'y': random.uniform(0, self._ch),
                'dx': random.uniform(-0.4, 0.4),
                'dy': random.uniform(-0.4, 0.4),
                'r': random.uniform(1.5, 3.0),
            }
            p['id'] = self.create_oval(
                p['x'] - p['r'], p['y'] - p['r'],
                p['x'] + p['r'], p['y'] + p['r'],
                fill=self.DOT_COLOR, outline=""
            )
            self._particles.append(p)

    # ---- frosted card ------------------------------------------------------
    def draw_frosted_card(self, x, y, w, h, radius=CARD_RADIUS):
        """Render the card as a single anti-aliased RGBA image and place it
        at (x, y) on the canvas. Real alpha — no stipple dots, no seams."""
        key = (int(x), int(y), int(w), int(h))
        if key == self._frost_last_key and self._frost_photo is not None:
            # already correct — just make sure it's on top
            if self._frost_id is not None:
                self.tag_raise(self._frost_id)
            return

        self._frost_last_key = key
        self._frost_photo = self._make_frost_image(int(w), int(h), radius)

        if self._frost_id is None:
            self._frost_id = self.create_image(
                int(x), int(y), anchor="nw", image=self._frost_photo,
            )
        else:
            self.coords(self._frost_id, int(x), int(y))
            self.itemconfigure(self._frost_id, image=self._frost_photo)

        self.tag_raise(self._frost_id)

    @staticmethod
    def _make_frost_image(w, h, radius):
        """Build the card image: translucent tinted fill + crisp border,
        with anti-aliased rounded corners.
        """
        # parse hex CARD/BORDER to RGB
        cr, cg, cb = int(CARD[1:3], 16), int(CARD[3:5], 16), int(CARD[5:7], 16)
        br, bg, bb = int(BORDER[1:3], 16), int(BORDER[3:5], 16), int(BORDER[5:7], 16)

        # alpha — 220/255 ≈ 86% opaque. Lower for more see-through.
        fill_alpha = 220
        border_alpha = 255

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # filled rounded rect (translucent)
        draw.rounded_rectangle(
            (0, 0, w - 1, h - 1),
            radius=radius,
            fill=(cr, cg, cb, fill_alpha),
            outline=(br, bg, bb, border_alpha),
            width=1,
        )
        return ImageTk.PhotoImage(img)

    # ---- animation loop ----------------------------------------------------
    def _tick(self):
        if not self._running:
            return

        particles = self._particles
        cw, ch = self._cw, self._ch
        coords = self.coords
        itemconfig = self.itemconfigure
        create_line = self.create_line
        pool = self._line_pool
        fade_table = self._FADE_TABLE
        sqrt = math.sqrt

        for p in particles:
            x = p['x'] + p['dx']
            y = p['y'] + p['dy']
            if x < -10:    x = cw + 10
            elif x > cw + 10: x = -10
            if y < -10:    y = ch + 10
            elif y > ch + 10: y = -10
            p['x'] = x; p['y'] = y
            r = p['r']
            coords(p['id'], x - r, y - r, x + r, y + r)

        cd = self.CONNECT_DIST
        cd_sq = cd * cd
        inv_cd = 1.0 / cd
        pool_len = len(pool)
        prev_active = self._active_lines
        n = len(particles)
        line_idx = 0

        for i in range(n):
            p1 = particles[i]
            x1 = p1['x']; y1 = p1['y']
            for j in range(i + 1, n):
                p2 = particles[j]
                dx = x1 - p2['x']
                dy = y1 - p2['y']
                dist_sq = dx * dx + dy * dy
                if dist_sq < cd_sq:
                    ratio = sqrt(dist_sq) * inv_cd
                    color = fade_table[int(ratio * 100)]
                    if line_idx < pool_len:
                        lid = pool[line_idx]
                        coords(lid, x1, y1, p2['x'], p2['y'])
                        itemconfig(lid, fill=color, state='normal')
                    else:
                        lid = create_line(
                            x1, y1, p2['x'], p2['y'],
                            fill=color, width=1,
                        )
                        pool.append(lid)
                        pool_len += 1
                    line_idx += 1

        if line_idx < prev_active:
            for k in range(line_idx, prev_active):
                itemconfig(pool[k], state='hidden')
        self._active_lines = line_idx

        if self._frost_id is not None:
            self.tag_raise(self._frost_id)

        self.after(33, self._tick)


# ====================================================================== APP
class GUIUniApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GUIUniApp")
        self.configure(fg_color=SURFACE)

        self.attributes("-fullscreen", True)
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self._history: list[str] = []
        self._frames: dict[str, ctk.CTkFrame] = {}
        self.current_student = None

        self._create_frames()
        self.show_frame("login")

    def _create_frames(self):
        for FrameClass in (LoginFrame, EnrolmentFrame, SubjectFrame):
            name = FrameClass.NAME
            frame = FrameClass(parent=self.container, app=self)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._frames[name] = frame

    def show_frame(self, name: str, *, push_history: bool = True):
        if push_history:
            self._history.append(name)
        frame = self._frames[name]
        for f in self._frames.values():
            if hasattr(f, 'anim_bg'):
                f.anim_bg.stop()
        if hasattr(frame, 'anim_bg'):
            frame.anim_bg.start()
        if hasattr(frame, "on_show"):
            frame.on_show()
        frame.tkraise()

    def go_back(self):
        if len(self._history) > 1:
            self._history.pop()
            self.show_frame(self._history[-1], push_history=False)

    def navigate_to(self, name: str):
        self.show_frame(name, push_history=True)


# ====================================================================== HELPERS
class ExceptionWindow(ctk.CTkToplevel):
    def __init__(self, parent, title: str, message: str):
        super().__init__(parent)
        self.title(title)
        self.geometry("420x200")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=CARD)

        ctk.CTkLabel(self, text="⚠", font=("Segoe UI", 40),
                     text_color=DANGER).pack(pady=(20, 0))
        ctk.CTkLabel(self, text=title, font=FONT_HEADING,
                     text_color=TEXT).pack(pady=(4, 6))
        ctk.CTkLabel(self, text=message, font=FONT_BODY,
                     text_color=MUTED, wraplength=380).pack(pady=(0, 12))
        ctk.CTkButton(
            self, text="Dismiss", width=120,
            fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
            text_color="white", command=self.destroy,
        ).pack(pady=(0, 14))
        self.after(10, self._center, parent)

    def _center(self, parent):
        parent.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = 420, 200
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")


class ToastWindow(ctk.CTkToplevel):
    def __init__(self, parent, message: str):
        super().__init__(parent)
        self.overrideredirect(True)
        self.configure(fg_color=SUCCESS)
        self.attributes("-topmost", True)
        ctk.CTkLabel(
            self, text=f"  ✓  {message}  ",
            font=("Segoe UI", 12, "bold"), text_color="white",
        ).pack(padx=18, pady=10)
        parent.update_idletasks()
        x = parent.winfo_rootx() + parent.winfo_width() - 360
        y = parent.winfo_rooty() + 20
        self.geometry(f"+{max(x, 0)}+{y}")
        self.after(2200, self.destroy)


# ====================================================================== CHANGE PASSWORD
class ChangePasswordWindow(ctk.CTkToplevel):
    """Modal that lets a registered student change their password from the
    login screen. The student re-authenticates with their existing
    credentials, then provides a new password (validated against the same
    regex as registration) and confirms it.
    """

    WIDTH = 460
    HEIGHT = 600

    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("Change Password")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color=CARD)

        self.app = app

        # ---- header
        ctk.CTkLabel(
            self, text="🔑", font=("Segoe UI", 36),
            text_color=PRIMARY,
        ).pack(pady=(20, 0))
        ctk.CTkLabel(
            self, text="Change Password",
            font=FONT_HEADING, text_color=TEXT,
        ).pack(pady=(2, 4))
        ctk.CTkLabel(
            self,
            text="Verify your identity, then choose a new password.",
            font=FONT_SMALL, text_color=MUTED,
            wraplength=380, justify="center",
        ).pack(pady=(0, 14))

        # ---- form
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=36, pady=(0, 8))

        self._email_entry = self._field(
            form, "Email", "firstname.lastname@university.com",
        )
        self._current_entry = self._field(
            form, "Current Password", "••••••••••", show="*",
        )
        self._new_entry = self._field(
            form, "New Password", "••••••••••", show="*",
        )
        self._confirm_entry = self._field(
            form, "Confirm New Password", "••••••••••", show="*",
        )

        # ---- buttons
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=36, pady=(10, 18))

        ctk.CTkButton(
            btns, text="Cancel", height=42, corner_radius=10,
            fg_color=NEUTRAL_BTN, hover_color=NEUTRAL_BTN_HOVER,
            text_color=TEXT, command=self.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            btns, text="Update Password", height=42, corner_radius=10,
            font=("Segoe UI", 13, "bold"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color="white",
            command=self._submit,
        ).pack(side="right", expand=True, fill="x", padx=(6, 0))

        for entry in (self._email_entry, self._current_entry,
                      self._new_entry, self._confirm_entry):
            entry.bind("<Return>", lambda e: self._submit())

        self.after(10, self._center, parent)
        self._email_entry.focus()

    def _field(self, parent, label, placeholder, *, show=None):
        ctk.CTkLabel(
            parent, text=label, font=("Segoe UI", 12), text_color=MUTED,
        ).pack(anchor="w", pady=(6, 2))
        kwargs = dict(
            placeholder_text=placeholder, height=40, corner_radius=10,
            font=("Segoe UI", 13),
        )
        if show is not None:
            kwargs["show"] = show
        entry = ctk.CTkEntry(parent, **kwargs)
        entry.pack(fill="x", pady=(0, 4))
        return entry

    def _submit(self):
        email = self._email_entry.get().strip()
        current = self._current_entry.get().strip()
        new_pwd = self._new_entry.get().strip()
        confirm = self._confirm_entry.get().strip()

        if not email or not current or not new_pwd or not confirm:
            ExceptionWindow(self, "Empty fields",
                            "Please fill in all four fields.")
            return
        if not is_valid_email(email):
            ExceptionWindow(self, "Invalid email",
                            "Use the format firstname.lastname@university.com")
            return
        if not is_valid_password(new_pwd):
            ExceptionWindow(self, "Invalid new password",
                            "New password must start with an uppercase "
                            "letter, contain at least 6 letters, then 3+ digits.")
            return
        if new_pwd != confirm:
            ExceptionWindow(self, "Password mismatch",
                            "New password and confirmation do not match.")
            return

        student = Database.find_by_email(email)
        if student is None or student.password != current:
            ExceptionWindow(self, "Authentication failed",
                            "Incorrect email or current password.")
            return

        student.change_password(new_pwd)
        Database.update_student(student)
        ToastWindow(self.app, "Password updated successfully")
        self.destroy()

    def _center(self, parent):
        parent.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.WIDTH, self.HEIGHT
        self.geometry(f"{w}x{h}+{px + (pw - w) // 2}+{py + (ph - h) // 2}")


# ====================================================================== BASE FRAME
class FrostedFrame(ctk.CTkFrame):
    """Animated bg + frosted-glass card. Subclasses can override
    `_build_background()` to swap in image mode.
    """

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=SURFACE)
        self.app = app

        self.anim_bg = self._build_background()
        self.anim_bg.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.card = ctk.CTkFrame(self, fg_color="transparent", width=CARD_WIDTH)
        self.card.place(relx=0.5, rely=0.5, anchor="center")

        self.bind("<Configure>", self._redraw_frost)
        self.card.bind("<Configure>", self._redraw_frost)

    def _build_background(self):
        """Default: animated constellation. Override to use image mode."""
        return AnimatedBackground(self, num_particles=40)

    def _redraw_frost(self, event=None):
        self.update_idletasks()
        try:
            cw = self.card.winfo_width()
            ch = self.card.winfo_height()
            cx = self.card.winfo_x()
            cy = self.card.winfo_y()
        except tk.TclError:
            return
        if cw < 10 or ch < 10:
            return
        self.anim_bg.draw_frosted_card(cx, cy, cw, ch)


# ====================================================================== LOGIN FRAME (image bg)
class LoginFrame(FrostedFrame):
    NAME = "login"

    def _build_background(self):
        """Use the UTS campus image as the static background."""
        img_path = os.path.join(os.path.dirname(__file__), "images", "uts.jpg")
        try:
            pil_img = Image.open(img_path)
        except Exception:
            # fallback to animation if the image is missing
            return AnimatedBackground(self, num_particles=40)
        return AnimatedBackground(self, background_image=pil_img)

    def __init__(self, parent, app: GUIUniApp):
        super().__init__(parent, app)

        spacer = ctk.CTkFrame(self.card, fg_color="transparent",
                              height=0, width=CARD_WIDTH)
        spacer.pack()
        spacer.pack_propagate(False)

        header = ctk.CTkFrame(self.card, fg_color="transparent")
        header.pack(pady=(28, 16))

        ctk.CTkLabel(header, text="🎓", font=("Segoe UI", 64)).pack()
        ctk.CTkLabel(
            header, text="GUIUniApp",
            font=("Segoe UI", 30, "bold"), text_color=TEXT,
        ).pack(pady=(8, 0))
        ctk.CTkLabel(
            header, text="Subject enrolment for students",
            font=("Segoe UI", 15), text_color=MUTED,
        ).pack(pady=(4, 0))

        ctk.CTkLabel(
            self.card, text="Sign in",
            font=("Segoe UI", 22, "bold"), text_color=TEXT,
        ).pack(anchor="w", padx=44, pady=(4, 16))

        ctk.CTkLabel(
            self.card, text="Email",
            font=("Segoe UI", 13), text_color=MUTED,
        ).pack(anchor="w", padx=44)
        self.email_entry = ctk.CTkEntry(
            self.card, placeholder_text="firstname.lastname@university.com",
            height=46, corner_radius=10, font=("Segoe UI", 14),
        )
        self.email_entry.pack(fill="x", padx=44, pady=(6, 16))

        ctk.CTkLabel(
            self.card, text="Password",
            font=("Segoe UI", 13), text_color=MUTED,
        ).pack(anchor="w", padx=44)
        self.password_entry = ctk.CTkEntry(
            self.card, placeholder_text="••••••••••", show="*",
            height=46, corner_radius=10, font=("Segoe UI", 14),
        )
        self.password_entry.pack(fill="x", padx=44, pady=(6, 22))

        ctk.CTkButton(
            self.card, text="Sign In", height=50, corner_radius=10,
            font=("Segoe UI", 15, "bold"),
            fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color="white",
            command=self._on_login,
        ).pack(fill="x", padx=44, pady=(0, 20))

        ctk.CTkLabel(
            self.card,
            text="Not registered? Use CLIUniApp to create an account.",
            font=("Segoe UI", 12), text_color=MUTED,
        ).pack(pady=(4, 4))

        ctk.CTkButton(
            self.card, text="Change password",
            fg_color="transparent", hover_color=GHOST_BTN_HOVER,
            text_color=PRIMARY, font=("Segoe UI", 12, "underline"),
            height=26, width=140, corner_radius=6,
            command=self._open_change_password,
        ).pack(pady=(0, 22))

        self.email_entry.bind("<Return>", lambda e: self._on_login())
        self.password_entry.bind("<Return>", lambda e: self._on_login())

    def on_show(self):
        self.email_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
        self.email_entry.focus()
        self.after(50, self._redraw_frost)

    def _on_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()

        if not email or not password:
            ExceptionWindow(self.app, "Empty fields",
                            "Please enter both email and password.")
            return
        if not is_valid_email(email):
            ExceptionWindow(self.app, "Invalid email",
                            "Use the format firstname.lastname@university.com")
            return
        if not is_valid_password(password):
            ExceptionWindow(self.app, "Invalid password",
                            "Password must start with an uppercase letter, "
                            "contain at least 6 letters, then 3+ digits.")
            return
        student = Database.find_by_email(email)
        if student is None or student.password != password:
            ExceptionWindow(self.app, "Login failed",
                            "Incorrect email or password. "
                            "Register first via CLIUniApp.")
            return
        self.app.current_student = student
        self.app.navigate_to("enrolment")

    def _open_change_password(self):
        ChangePasswordWindow(self.app, self.app)


# ====================================================================== ENROLMENT FRAME
class EnrolmentFrame(FrostedFrame):
    NAME = "enrolment"

    # 5-7 random subjects offered each time a fresh catalog is generated.
    CATALOG_MIN = 5
    CATALOG_MAX = 7

    def __init__(self, parent, app: GUIUniApp):
        super().__init__(parent, app)

        # Catalog state — list of Subject objects offered this session.
        # The Subject() constructor pre-generates id, mark, and grade, but
        # the UI shows only the id until the student clicks Enrol; the
        # mark/grade are revealed via the toast notification on enrolment.
        self._catalog: list[Subject] = []
        self._catalog_student_id: str | None = None

        topbar = ctk.CTkFrame(self, fg_color="transparent", height=60)
        topbar.place(relx=0, rely=0, relwidth=1)

        ctk.CTkButton(
            topbar, text="←  Sign Out", width=120, height=36,
            corner_radius=8, fg_color=NEUTRAL_BTN,
            text_color=TEXT, hover_color=NEUTRAL_BTN_HOVER,
            command=self._logout,
        ).pack(side="left", padx=28, pady=12)

        spacer = ctk.CTkFrame(self.card, fg_color="transparent",
                              height=0, width=CARD_WIDTH)
        spacer.pack()
        spacer.pack_propagate(False)

        # ---- welcome header
        head = ctk.CTkFrame(self.card, fg_color="transparent")
        head.pack(fill="x", padx=36, pady=(24, 0))

        self.welcome_label = ctk.CTkLabel(
            head, text="Welcome", font=FONT_TITLE, text_color=TEXT,
        )
        self.welcome_label.pack(anchor="w")
        self.id_label = ctk.CTkLabel(
            head, text="Student ID  ::  ...",
            font=FONT_BODY, text_color=MUTED,
        )
        self.id_label.pack(anchor="w", pady=(2, 0))

        # ---- progress card
        prog_card = ctk.CTkFrame(self.card, fg_color=NESTED, corner_radius=14)
        prog_card.pack(fill="x", padx=36, pady=(18, 12))

        ctk.CTkLabel(
            prog_card, text="Enrolment Progress",
            font=FONT_SMALL, text_color=MUTED,
        ).pack(anchor="w", padx=22, pady=(14, 2))

        self.count_label = ctk.CTkLabel(
            prog_card, text="", font=("Segoe UI", 22, "bold"),
            text_color=TEXT,
        )
        self.count_label.pack(anchor="w", padx=22)

        self.progress = ctk.CTkProgressBar(
            prog_card, height=8, corner_radius=6, progress_color=PRIMARY,
        )
        self.progress.pack(fill="x", padx=22, pady=(8, 4))

        self.hint_label = ctk.CTkLabel(
            prog_card, text="", font=FONT_SMALL, text_color=MUTED,
        )
        self.hint_label.pack(anchor="w", padx=22, pady=(2, 14))

        # ---- catalog header (title + refresh)
        cat_header = ctk.CTkFrame(self.card, fg_color="transparent")
        cat_header.pack(fill="x", padx=36, pady=(0, 6))

        ctk.CTkLabel(
            cat_header, text="Available Subjects",
            font=FONT_HEADING, text_color=TEXT,
        ).pack(side="left")

        ctk.CTkButton(
            cat_header, text="↻  Refresh", width=100, height=30,
            corner_radius=6, font=FONT_SMALL,
            fg_color=NEUTRAL_BTN, hover_color=NEUTRAL_BTN_HOVER,
            text_color=TEXT, command=self._refresh_catalog,
        ).pack(side="right")

        # ---- scrollable catalog list
        self.catalog_list = ctk.CTkScrollableFrame(
            self.card, fg_color="transparent", height=260,
        )
        self.catalog_list.pack(fill="x", padx=30, pady=(0, 12))

        # ---- bottom action: view enrolled subjects
        actions = ctk.CTkFrame(self.card, fg_color="transparent")
        actions.pack(fill="x", padx=36, pady=(0, 24))

        ctk.CTkButton(
            actions, text="📖  View My Subjects", height=42,
            corner_radius=10,
            fg_color=NEUTRAL_BTN, hover_color=NEUTRAL_BTN_HOVER,
            text_color=TEXT,
            command=self._open_subjects,
        ).pack(fill="x")

    # ---- lifecycle --------------------------------------------------------
    def on_show(self):
        student = self.app.current_student
        if student:
            self.welcome_label.configure(text=f"Welcome, {student.name}")
            self.id_label.configure(text=f"Student ID  ::  {student.id}")
            # Generate a fresh catalog the first time this student visits
            # the screen, or if a different student logged in.
            if (not self._catalog
                    or self._catalog_student_id != student.id):
                self._generate_catalog()
            self._refresh()
        self.after(50, self._redraw_frost)

    # ---- catalog generation -----------------------------------------------
    def _generate_catalog(self):
        """Create 5-7 random Subject candidates whose ids don't collide
        with each other or with the student's existing enrolment."""
        student = self.app.current_student
        if student is None:
            return
        self._catalog_student_id = student.id
        seen = {s.id for s in student.subjects}
        target = random.randint(self.CATALOG_MIN, self.CATALOG_MAX)
        catalog: list[Subject] = []
        # bounded loop in case of repeated id collisions
        for _ in range(500):
            if len(catalog) >= target:
                break
            sub = Subject()
            if sub.id in seen:
                continue
            seen.add(sub.id)
            catalog.append(sub)
        self._catalog = catalog

    def _refresh_catalog(self):
        """User-triggered: regenerate the offered subject list."""
        self._generate_catalog()
        self._refresh()

    # ---- rendering --------------------------------------------------------
    def _refresh(self):
        student = self.app.current_student
        if not student:
            return
        n = len(student.subjects)
        self.count_label.configure(text=f"{n} of 4 subjects enrolled")
        self.progress.set(n / 4)
        if n >= 4:
            self.hint_label.configure(
                text="You have reached the 4-subject limit."
            )
        else:
            self.hint_label.configure(
                text=f"You can enrol in {4 - n} more subject(s)."
            )
        self._render_catalog()

    def _render_catalog(self):
        # clear existing rows
        for w in self.catalog_list.winfo_children():
            w.destroy()

        if not self._catalog:
            ctk.CTkLabel(
                self.catalog_list,
                text='No subjects available.\n'
                     'Click "Refresh" to load a new set.',
                font=FONT_BODY, text_color=MUTED, justify="center",
            ).pack(pady=30)
            return

        for sub in self._catalog:
            row = ctk.CTkFrame(self.catalog_list, fg_color=NESTED,
                               corner_radius=10)
            row.pack(fill="x", pady=4, padx=2)

            ctk.CTkLabel(
                row, text=f"  Subject-{sub.id}",
                font=FONT_MONO, text_color=TEXT, anchor="w",
            ).pack(side="left", padx=14, pady=12, fill="x", expand=True)

            ctk.CTkButton(
                row, text="Enrol", width=90, height=30, corner_radius=6,
                fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                text_color="white",
                command=lambda s=sub: self._enrol_subject(s),
            ).pack(side="right", padx=12)

    # ---- actions ----------------------------------------------------------
    def _enrol_subject(self, subject: Subject):
        student = self.app.current_student
        if student is None:
            return
        # Cap check — fires the popup notification per the spec's
        # exception-handling requirement.
        if not student.can_enrol():
            ExceptionWindow(self.app, "Limit reached",
                            "Students are allowed to enrol in 4 subjects only.")
            return
        # Commit the chosen Subject to the student's enrolment list and
        # persist. The mark/grade were already random-generated when the
        # Subject object was constructed for the catalog.
        student.subjects.append(subject)
        Database.update_student(student)
        # remove the enrolled subject from the offered catalog so it
        # can't be enrolled twice.
        if subject in self._catalog:
            self._catalog.remove(subject)
        self._refresh()
        ToastWindow(
            self.app,
            f"Enrolled in Subject-{subject.id}  •  Mark {subject.mark}"
            f"  •  Grade {subject.grade}",
        )

    def _open_subjects(self):
        self.app.navigate_to("subjects")

    def _logout(self):
        self.app.current_student = None
        self._catalog = []
        self._catalog_student_id = None
        self.app._history.clear()
        self.app.show_frame("login")


# ====================================================================== SUBJECTS FRAME
class SubjectFrame(FrostedFrame):
    NAME = "subjects"

    def __init__(self, parent, app: GUIUniApp):
        super().__init__(parent, app)

        topbar = ctk.CTkFrame(self, fg_color="transparent", height=60)
        topbar.place(relx=0, rely=0, relwidth=1)

        ctk.CTkButton(
            topbar, text="←  Back", width=100, height=36,
            corner_radius=8, fg_color=NEUTRAL_BTN,
            text_color=TEXT, hover_color=NEUTRAL_BTN_HOVER,
            command=lambda: self.app.go_back(),
        ).pack(side="left", padx=28, pady=12)

        spacer = ctk.CTkFrame(self.card, fg_color="transparent",
                              height=0, width=CARD_WIDTH)
        spacer.pack()
        spacer.pack_propagate(False)

        ctk.CTkLabel(
            self.card, text="Enrolled Subjects",
            font=FONT_TITLE, text_color=TEXT,
        ).pack(anchor="w", padx=36, pady=(30, 0))
        ctk.CTkLabel(
            self.card, text="Marks are auto-generated upon enrolment.",
            font=FONT_BODY, text_color=MUTED,
        ).pack(anchor="w", padx=36, pady=(2, 16))

        self.summary = ctk.CTkLabel(
            self.card, text="", font=FONT_BODY, text_color=TEXT,
            fg_color=NESTED, corner_radius=10, height=44, anchor="w",
        )
        self.summary.pack(fill="x", padx=36, pady=(0, 16), ipadx=14)

        self.list_frame = ctk.CTkScrollableFrame(
            self.card, fg_color="transparent", height=300,
        )
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=(0, 30))

    def on_show(self):
        student = self.app.current_student
        if student:
            self._refresh(student)
        self.after(50, self._redraw_frost)

    def _refresh(self, student):
        for w in self.list_frame.winfo_children():
            w.destroy()

        if not student.subjects:
            self.summary.configure(text="  No subjects enrolled yet.",
                                   text_color=TEXT)
            ctk.CTkLabel(
                self.list_frame,
                text='You haven\'t enrolled in any subjects.\n'
                     'Go back and click "Enrol" to start.',
                font=FONT_BODY, text_color=MUTED, justify="center",
            ).pack(pady=40)
            return

        avg = student.average_mark
        status = "PASS" if student.passed else "FAIL"
        self.summary.configure(
            text=f"  Average: {avg:.2f}    •    Overall Grade:"
                 f" {student.overall_grade}    •    Status: {status}",
            text_color=TEXT if student.passed else DANGER,
        )

        for sub in student.subjects:
            row = ctk.CTkFrame(self.list_frame, fg_color=NESTED,
                               corner_radius=10)
            row.pack(fill="x", pady=4, padx=2)

            text = (f"  Subject-{sub.id}      Mark: {sub.mark:>3}"
                    f"      Grade: {sub.grade}")
            ctk.CTkLabel(
                row, text=text, font=FONT_MONO, text_color=TEXT,
                anchor="w",
            ).pack(side="left", padx=14, pady=12, fill="x", expand=True)

            ctk.CTkButton(
                row, text="Remove", width=90, height=30, corner_radius=6,
                fg_color=DANGER, hover_color=DANGER_HOVER, text_color="white",
                command=lambda sid=sub.id: self._remove(sid),
            ).pack(side="right", padx=12)

    def _remove(self, sid):
        student = self.app.current_student
        if student and student.remove_subject(sid):
            Database.update_student(student)
            self._refresh(student)


# ====================================================================== MAIN
if __name__ == "__main__":
    app = GUIUniApp()
    app.mainloop()