"""Анимированные фоны: снежинки, пузыри, дождь, звёзды, матрица,
светлячки, сакура, неон, частицы.

Размер окна отслеживается автоматически (auto_resize внутри цикла).
Метод stop() корректно завершает поток — вызывать при уходе с экрана.
"""

import math
import os
import random
import threading
import time
from typing import Optional

import flet as ft

from ui import theme


DEBUG = os.environ.get("VAGENT_DEBUG", "0") == "1"

TICK_MS = 60
LOG_INTERVAL_SEC = 60
MAX_ERRORS_BEFORE_OFF = 3


def _clamp(x, lo, hi, default=1.0):
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return default


def _read_page_size(page) -> tuple:
    w, h = 0, 0
    try:
        w = int(page.window.width or 0)
    except Exception:
        pass
    try:
        h = int(page.window.height or 0)
    except Exception:
        pass
    if w < 200:
        try:
            w = int(page.width or 0)
        except Exception:
            w = 0
    if h < 200:
        try:
            h = int(page.height or 0)
        except Exception:
            h = 0
    if w < 200:
        w = 1920
    if h < 200:
        h = 1080
    return w, h


class _BaseEffect:
    BASE_COUNT = 80
    SIZE_MIN = 10
    SIZE_MAX = 24

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        self.page = page
        self.count_scale = _clamp(count_scale, 0.2, 3.0)
        self.size_scale = _clamp(size_scale, 0.5, 2.0)

        w, h = _read_page_size(page)
        self.width = max(int(width or 0), w)
        self.height = max(int(height or 0), h)

        self.alive = False
        self._thread = None
        self._stack = ft.Stack(controls=[], expand=True)
        self._items: list = []
        self._last_log_ts = 0.0
        self._error_streak = 0
        self._paused = False

    @property
    def count(self) -> int:
        return max(20, int(self.BASE_COUNT * self.count_scale))

    def _size(self):
        lo = max(4, int(self.SIZE_MIN * self.size_scale))
        hi = max(lo + 2, int(self.SIZE_MAX * self.size_scale))
        return random.randint(lo, hi)

    def _spawn_x(self, size_hint=40):
        return random.uniform(-size_hint, self.width + size_hint)

    def _spawn_y(self, size_hint=40):
        return -size_hint - random.uniform(10, 150)

    def _spawn_y_bottom(self, size_hint=40):
        return self.height + size_hint + random.uniform(10, 150)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def resize(self, width: int, height: int) -> None:
        try:
            w = int(width or 0)
            h = int(height or 0)
        except Exception:
            return
        if w < 200 or h < 200:
            return

        old_w = max(1, self.width)
        old_h = max(1, self.height)
        if w == old_w and h == old_h:
            return

        self.width = w
        self.height = h
        rx = w / old_w
        ry = h / old_h
        for item in self._items:
            item["x"] = item["x"] * rx
            item["y"] = item["y"] * ry

    def build(self):
        return self._stack

    def start(self):
        if self.alive:
            return
        self.alive = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.alive = False
        self._paused = False

    def is_alive(self) -> bool:
        return bool(self.alive)

    def _auto_resize(self):
        try:
            w, h = _read_page_size(self.page)
        except Exception:
            return
        if w == self.width and h == self.height:
            return
        if w < 200 or h < 200:
            return

        old_w = max(1, self.width)
        old_h = max(1, self.height)
        self.width = w
        self.height = h
        rx = w / old_w
        ry = h / old_h
        for item in self._items:
            item["x"] = item["x"] * rx
            item["y"] = item["y"] * ry

    def _loop(self):
        while self.alive:
            time.sleep(TICK_MS / 1000)
            if not self.alive:
                break
            if self._paused:
                continue

            try:
                self._auto_resize()
            except Exception:
                pass

            try:
                self._tick()
            except Exception as ex:
                self._error_streak += 1
                now = time.time()
                if now - self._last_log_ts > LOG_INTERVAL_SEC:
                    self._last_log_ts = now
                    print(f"[FX] tick error: {ex}")
                if self._error_streak >= MAX_ERRORS_BEFORE_OFF:
                    print("[FX] эффект отключён")
                    self.alive = False
                    break
                continue

            self._error_streak = 0
            try:
                self._stack.update()
            except Exception:
                pass

    def _tick(self):
        raise NotImplementedError

    def _populate(self, maker):
        for _ in range(self.count):
            item = maker()
            self._items.append(item)
            self._stack.controls.append(item["ctrl"])


# ===========================================================================
# 1. SNOW — снежинки
# ===========================================================================

class SnowEffect(_BaseEffect):
    BASE_COUNT = 90
    SIZE_MIN = 8
    SIZE_MAX = 20
    CHARS = ["❄", "❅", "❆"]

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._populate(self._make)

    def _make(self):
        size = self._size()
        ctrl = ft.Container(
            content=ft.Text(
                random.choice(self.CHARS),
                size=size, color=ft.Colors.WHITE,
                opacity=random.uniform(0.25, 0.75),
            ),
            width=size + 4, height=size + 4,
            alignment=ft.alignment.center,
        )
        return {
            "ctrl": ctrl,
            "x": self._spawn_x(size),
            "y": random.uniform(-self.height, 0),
            "speed": random.uniform(0.5, 1.4),
            "drift": random.uniform(-0.15, 0.15),
        }

    def _tick(self):
        for f in self._items:
            f["y"] += f["speed"]
            f["x"] += f["drift"]
            if f["y"] > self.height:
                f["y"] = self._spawn_y(40)
                f["x"] = self._spawn_x()
                f["speed"] = random.uniform(0.5, 1.4)
                f["drift"] = random.uniform(-0.15, 0.15)
            if f["x"] < -30:
                f["x"] = self.width + 30
            elif f["x"] > self.width + 30:
                f["x"] = -30
            f["ctrl"].left = f["x"]
            f["ctrl"].top = f["y"]


# ===========================================================================
# 2. BUBBLES — пузыри
# ===========================================================================

class BubblesEffect(_BaseEffect):
    BASE_COUNT = 60
    SIZE_MIN = 10
    SIZE_MAX = 30

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._populate(self._make)

    def _make(self):
        size = self._size()
        ctrl = ft.Container(
            width=size, height=size, border_radius=size // 2,
            bgcolor=ft.Colors.with_opacity(random.uniform(0.08, 0.25), theme.PRIMARY),
            border=ft.border.all(1, ft.Colors.with_opacity(0.5, theme.PRIMARY)),
        )
        return {
            "ctrl": ctrl,
            "x": self._spawn_x(size),
            "y": random.uniform(0, self.height),
            "speed": random.uniform(0.4, 1.0),
            "drift": random.uniform(-0.3, 0.3),
        }

    def _tick(self):
        for b in self._items:
            b["y"] -= b["speed"]
            b["x"] += b["drift"]
            if b["y"] < -60:
                b["y"] = self._spawn_y_bottom(30)
                b["x"] = self._spawn_x()
                b["speed"] = random.uniform(0.4, 1.0)
                b["drift"] = random.uniform(-0.3, 0.3)
            if b["x"] < -60:
                b["x"] = self.width + 60
            elif b["x"] > self.width + 60:
                b["x"] = -60
            b["ctrl"].left = b["x"]
            b["ctrl"].top = b["y"]


# ===========================================================================
# 3. RAIN — дождь
# ===========================================================================

class RainEffect(_BaseEffect):
    BASE_COUNT = 110
    SIZE_MIN = 12
    SIZE_MAX = 24

    ANGLE = -0.20
    SPEED_MIN = 8.0
    SPEED_MAX = 14.0
    GRAVITY = 0.10

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._splashes: list = []
        self._populate(self._make)

    def _make(self):
        h = self._size()
        w = 1 if h <= 16 else 2
        ctrl = ft.Container(
            width=w, height=h,
            border_radius=max(1, w),
            bgcolor=ft.Colors.with_opacity(random.uniform(0.4, 0.8), "#CFE9FF"),
        )
        return {
            "ctrl": ctrl,
            "x": self._spawn_x(h),
            "y": random.uniform(-self.height, 0),
            "speed": random.uniform(self.SPEED_MIN, self.SPEED_MAX),
        }

    def _spawn_splash(self, x, y):
        if len(self._splashes) > 30:
            return
        for _ in range(random.randint(1, 2)):
            size = random.randint(2, 3)
            ctrl = ft.Container(
                width=size, height=size,
                border_radius=size // 2,
                bgcolor=ft.Colors.with_opacity(0.7, "#CFE9FF"),
            )
            life = random.randint(3, 6)
            splash = {
                "ctrl": ctrl, "x": x, "y": y,
                "vx": random.uniform(-2.0, 2.0),
                "vy": random.uniform(-1.5, -0.5),
                "life": life, "max_life": life,
            }
            self._splashes.append(splash)
            self._stack.controls.append(ctrl)

    def _tick(self):
        for d in self._items:
            d["speed"] = min(self.SPEED_MAX * 1.3, d["speed"] + self.GRAVITY)
            d["y"] += d["speed"]
            d["x"] += d["speed"] * self.ANGLE
            if d["y"] > self.height:
                self._spawn_splash(d["x"], self.height - 3)
                d["y"] = self._spawn_y(40)
                d["x"] = self._spawn_x()
                d["speed"] = random.uniform(self.SPEED_MIN, self.SPEED_MAX)
            if d["x"] < -150:
                d["x"] = self.width + 100
            elif d["x"] > self.width + 150:
                d["x"] = -100
            d["ctrl"].left = d["x"]
            d["ctrl"].top = d["y"]

        alive = []
        for s in self._splashes:
            s["life"] -= 1
            s["x"] += s["vx"]
            s["y"] += s["vy"]
            s["vy"] += 0.35
            s["vx"] *= 0.94
            progress = s["life"] / max(1, s["max_life"])
            if progress < 0:
                progress = 0
            try:
                s["ctrl"].left = s["x"]
                s["ctrl"].top = s["y"]
                s["ctrl"].opacity = max(0.0, progress)
            except Exception:
                pass
            if s["life"] > 0:
                alive.append(s)
            else:
                try:
                    if s["ctrl"] in self._stack.controls:
                        self._stack.controls.remove(s["ctrl"])
                except Exception:
                    pass
        self._splashes = alive


# ===========================================================================
# 4. STARS — мерцающие звёзды
# ===========================================================================

class StarsEffect(_BaseEffect):
    BASE_COUNT = 120
    SIZE_MIN = 2
    SIZE_MAX = 5

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._populate(self._make)

    def _make(self):
        size = self._size()
        base_op = random.uniform(0.2, 0.7)
        ctrl = ft.Container(
            width=size, height=size, border_radius=size // 2,
            bgcolor=ft.Colors.WHITE,
            opacity=base_op,
        )
        return {
            "ctrl": ctrl,
            "x": random.uniform(0, self.width),
            "y": random.uniform(0, self.height),
            "base_op": base_op,
            "phase": random.uniform(0, math.pi * 2),
            "speed": random.uniform(0.02, 0.08),
            "drift_x": random.uniform(-0.05, 0.05),
            "drift_y": random.uniform(-0.03, 0.03),
        }

    def _tick(self):
        for s in self._items:
            s["phase"] += s["speed"]
            op = s["base_op"] * (0.6 + 0.4 * (1 + math.sin(s["phase"])) / 2)
            s["x"] += s["drift_x"]
            s["y"] += s["drift_y"]
            if s["x"] < 0:
                s["x"] = self.width
            elif s["x"] > self.width:
                s["x"] = 0
            if s["y"] < 0:
                s["y"] = self.height
            elif s["y"] > self.height:
                s["y"] = 0
            try:
                s["ctrl"].opacity = op
                s["ctrl"].left = s["x"]
                s["ctrl"].top = s["y"]
            except Exception:
                pass


# ===========================================================================
# 5. MATRIX — падающие символы 0/1
# ===========================================================================

class MatrixEffect(_BaseEffect):
    BASE_COUNT = 60
    SIZE_MIN = 10
    SIZE_MAX = 16

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._populate(self._make)

    def _make(self):
        size = self._size()
        ch = random.choice("01")
        ctrl = ft.Container(
            content=ft.Text(
                ch, size=size, color=theme.PRIMARY,
                font_family="monospace",
                opacity=random.uniform(0.3, 0.9),
            ),
            width=size + 4, height=size + 4,
            alignment=ft.alignment.center,
        )
        return {
            "ctrl": ctrl,
            "x": random.uniform(0, self.width),
            "y": random.uniform(-self.height, 0),
            "speed": random.uniform(2.5, 6.0),
        }

    def _tick(self):
        for m in self._items:
            m["y"] += m["speed"]
            if m["y"] > self.height:
                m["y"] = -20
                m["x"] = random.uniform(0, self.width)
                m["speed"] = random.uniform(2.5, 6.0)
                try:
                    m["ctrl"].content.value = random.choice("01")
                except Exception:
                    pass
            try:
                m["ctrl"].left = m["x"]
                m["ctrl"].top = m["y"]
            except Exception:
                pass


# ===========================================================================
# 6. FIREFLIES — светлячки
# ===========================================================================

class FirefliesEffect(_BaseEffect):
    BASE_COUNT = 40
    SIZE_MIN = 6
    SIZE_MAX = 12

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._populate(self._make)

    def _make(self):
        size = self._size()
        base_op = random.uniform(0.3, 0.8)
        ctrl = ft.Container(
            width=size, height=size, border_radius=size // 2,
            bgcolor=ft.Colors.with_opacity(base_op, "#FFD54F"),
            shadow=ft.BoxShadow(
                spread_radius=2,
                blur_radius=size,
                color=ft.Colors.with_opacity(0.5, "#FFD54F"),
            ),
        )
        return {
            "ctrl": ctrl,
            "x": random.uniform(0, self.width),
            "y": random.uniform(0, self.height),
            "vx": random.uniform(-0.8, 0.8),
            "vy": random.uniform(-0.5, 0.5),
            "phase": random.uniform(0, math.pi * 2),
            "pulse_speed": random.uniform(0.03, 0.08),
            "base_op": base_op,
        }

    def _tick(self):
        for f in self._items:
            f["x"] += f["vx"]
            f["y"] += f["vy"]
            f["vx"] += random.uniform(-0.05, 0.05)
            f["vy"] += random.uniform(-0.05, 0.05)
            f["vx"] = max(-1.2, min(1.2, f["vx"]))
            f["vy"] = max(-1.0, min(1.0, f["vy"]))

            if f["x"] < -20:
                f["x"] = self.width + 20
            elif f["x"] > self.width + 20:
                f["x"] = -20
            if f["y"] < -20:
                f["y"] = self.height + 20
            elif f["y"] > self.height + 20:
                f["y"] = -20

            f["phase"] += f["pulse_speed"]
            op = f["base_op"] * (0.4 + 0.6 * (1 + math.sin(f["phase"])) / 2)
            try:
                f["ctrl"].opacity = op
                f["ctrl"].left = f["x"]
                f["ctrl"].top = f["y"]
            except Exception:
                pass


# ===========================================================================
# 7. SAKURA — лепестки сакуры
# ===========================================================================

class SakuraEffect(_BaseEffect):
    BASE_COUNT = 60
    SIZE_MIN = 10
    SIZE_MAX = 18
    CHARS = ["🌸", "🌺", "❀", "✿"]

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._populate(self._make)

    def _make(self):
        size = self._size()
        ctrl = ft.Container(
            content=ft.Text(
                random.choice(self.CHARS),
                size=size,
                opacity=random.uniform(0.4, 0.85),
            ),
            width=size + 4, height=size + 4,
            alignment=ft.alignment.center,
        )
        return {
            "ctrl": ctrl,
            "x": self._spawn_x(size),
            "y": random.uniform(-self.height, 0),
            "speed": random.uniform(1.0, 2.2),
            "drift": random.uniform(-1.2, 1.2),
            "phase": random.uniform(0, math.pi * 2),
            "swing": random.uniform(0.5, 1.5),
        }

    def _tick(self):
        for s in self._items:
            s["y"] += s["speed"]
            s["phase"] += 0.05
            s["x"] += s["drift"] + math.sin(s["phase"]) * s["swing"] * 0.3
            if s["y"] > self.height:
                s["y"] = self._spawn_y(40)
                s["x"] = self._spawn_x()
                s["speed"] = random.uniform(1.0, 2.2)
                s["drift"] = random.uniform(-1.2, 1.2)
            if s["x"] < -40:
                s["x"] = self.width + 40
            elif s["x"] > self.width + 40:
                s["x"] = -40
            try:
                s["ctrl"].left = s["x"]
                s["ctrl"].top = s["y"]
                s["ctrl"].rotate = ft.transform.Rotate(
                    s["phase"] * 0.5, alignment=ft.alignment.center,
                )
            except Exception:
                pass


# ===========================================================================
# 8. NEON — светящиеся линии
# ===========================================================================

class NeonEffect(_BaseEffect):
    BASE_COUNT = 25
    SIZE_MIN = 60
    SIZE_MAX = 200

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._populate(self._make)

    def _make(self):
        length = self._size()
        horizontal = random.random() < 0.5
        color = random.choice([theme.PRIMARY, "#00E5FF", "#FF4081", "#76FF03"])

        if horizontal:
            ctrl = ft.Container(
                width=length, height=2,
                bgcolor=color,
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.8, color),
                ),
                opacity=random.uniform(0.4, 0.9),
            )
            return {
                "ctrl": ctrl,
                "horizontal": True,
                "x": random.uniform(-length, self.width),
                "y": random.uniform(0, self.height),
                "speed": random.uniform(1.5, 4.0) * random.choice([-1, 1]),
                "length": length,
                "phase": random.uniform(0, math.pi * 2),
            }
        else:
            ctrl = ft.Container(
                width=2, height=length,
                bgcolor=color,
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.8, color),
                ),
                opacity=random.uniform(0.4, 0.9),
            )
            return {
                "ctrl": ctrl,
                "horizontal": False,
                "x": random.uniform(0, self.width),
                "y": random.uniform(-length, self.height),
                "speed": random.uniform(1.5, 4.0) * random.choice([-1, 1]),
                "length": length,
                "phase": random.uniform(0, math.pi * 2),
            }

    def _tick(self):
        for n in self._items:
            if n["horizontal"]:
                n["x"] += n["speed"]
                if n["speed"] > 0 and n["x"] > self.width:
                    n["x"] = -n["length"]
                    n["y"] = random.uniform(0, self.height)
                elif n["speed"] < 0 and n["x"] < -n["length"]:
                    n["x"] = self.width
                    n["y"] = random.uniform(0, self.height)
                n["ctrl"].left = n["x"]
                n["ctrl"].top = n["y"]
            else:
                n["y"] += n["speed"]
                if n["speed"] > 0 and n["y"] > self.height:
                    n["y"] = -n["length"]
                    n["x"] = random.uniform(0, self.width)
                elif n["speed"] < 0 and n["y"] < -n["length"]:
                    n["y"] = self.height
                    n["x"] = random.uniform(0, self.width)
                n["ctrl"].left = n["x"]
                n["ctrl"].top = n["y"]

            n["phase"] += 0.05
            try:
                n["ctrl"].opacity = 0.4 + 0.5 * (1 + math.sin(n["phase"])) / 2
            except Exception:
                pass


# ===========================================================================
# 9. PARTICLES — частицы, соединяющиеся линиями
# ===========================================================================

class ParticlesEffect(_BaseEffect):
    BASE_COUNT = 40
    SIZE_MIN = 4
    SIZE_MAX = 8
    LINK_DIST = 120

    def __init__(self, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
        super().__init__(page, width, height, count_scale, size_scale)
        self._populate(self._make)

    def _make(self):
        size = self._size()
        ctrl = ft.Container(
            width=size, height=size, border_radius=size // 2,
            bgcolor=theme.PRIMARY,
            opacity=0.8,
        )
        return {
            "ctrl": ctrl,
            "x": random.uniform(0, self.width),
            "y": random.uniform(0, self.height),
            "vx": random.uniform(-0.8, 0.8),
            "vy": random.uniform(-0.8, 0.8),
            "size": size,
        }

    def _tick(self):
        for p in self._items:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["x"] < 0 or p["x"] > self.width:
                p["vx"] *= -1
                p["x"] = max(0, min(self.width, p["x"]))
            if p["y"] < 0 or p["y"] > self.height:
                p["vy"] *= -1
                p["y"] = max(0, min(self.height, p["y"]))
            try:
                p["ctrl"].left = p["x"]
                p["ctrl"].top = p["y"]
            except Exception:
                pass


# ===========================================================================
# 10. NONE — без эффекта
# ===========================================================================

class NoneEffect(_BaseEffect):
    def _tick(self):
        pass


# ===========================================================================
# Фабрика
# ===========================================================================

def create_effect(effect_key, page, width=0, height=0, count_scale=1.0, size_scale=1.0):
    if effect_key == "bubbles":
        return BubblesEffect(page, width, height, count_scale, size_scale)
    if effect_key == "rain":
        return RainEffect(page, width, height, count_scale, size_scale)
    if effect_key == "stars":
        return StarsEffect(page, width, height, count_scale, size_scale)
    if effect_key == "matrix":
        return MatrixEffect(page, width, height, count_scale, size_scale)
    if effect_key == "fireflies":
        return FirefliesEffect(page, width, height, count_scale, size_scale)
    if effect_key == "sakura":
        return SakuraEffect(page, width, height, count_scale, size_scale)
    if effect_key == "neon":
        return NeonEffect(page, width, height, count_scale, size_scale)
    if effect_key == "particles":
        return ParticlesEffect(page, width, height, count_scale, size_scale)
    if effect_key == "none":
        return NoneEffect(page, width, height, count_scale, size_scale)
    return SnowEffect(page, width, height, count_scale, size_scale)