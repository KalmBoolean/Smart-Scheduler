
import sys
import sqlite3
import math
import random
from datetime import datetime, timedelta

from Surrogate     import Objectivesurrogate, PerformanceSurrogate
from ScheduleUtils import Schedule, SchedGen
from DNAEncoder    import task, TaskType
from MonteCarlo    import MonteCarloStuff, CalculateActualUserPerformance

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QDateEdit, QTimeEdit, QSpinBox, QMessageBox, QFrame,
    QHeaderView, QStackedWidget, QSplitter, QGraphicsDropShadowEffect,
)
from PySide6.QtCore  import QDate, QTime, Qt, QTimer, QRect, QPropertyAnimation, QEasingCurve
from PySide6.QtGui   import (
    QPainter, QColor, QPen, QBrush,
    QLinearGradient, QConicalGradient,
    QFont, QPainterPath,
)

COLORS = {
    "bg":      "#080c14",
    "surface": "#0d1220",
    "card":    "#111827",
    "border":  "#1a2540",
    "accent":  "#00e5c0",
    "gold":    "#f59e0b",
    "purple":  "#818cf8",
    "text":    "#e2e8f0",
    "muted":   "#4b6280",
    "danger":  "#f43f5e",
    "success": "#34d399",
    "glow":    "#00e5c015",
}
MONO = "Courier New"

STYLESHEET = f"""
* {{ font-family: '{MONO}', monospace; }}
QWidget      {{ background:{COLORS['bg']};      color:{COLORS['text']}; font-size:13px; }}
QLineEdit, QSpinBox, QDateEdit, QTimeEdit {{
    background:{COLORS['surface']}; border:1px solid {COLORS['border']};
    border-radius:7px; padding:7px 11px; color:{COLORS['text']};
}}
QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QTimeEdit:focus {{
    border:1px solid {COLORS['accent']}; background:{COLORS['card']};
}}
QScrollBar:vertical   {{ background:{COLORS['surface']}; width:5px;  border-radius:2px; }}
QScrollBar:horizontal {{ background:{COLORS['surface']}; height:5px; border-radius:2px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background:{COLORS['accent']}; border-radius:2px; min-height:16px;
}}
QScrollBar::add-line:vertical,  QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{ height:0; width:0; }}
QHeaderView::section {{
    background:{COLORS['card']}; color:{COLORS['accent']}; border:none;
    border-bottom:1px solid {COLORS['border']}; padding:7px 6px;
    font-weight:bold; letter-spacing:1px; font-size:10px;
}}
QTableWidget {{
    background:{COLORS['surface']}; border:1px solid {COLORS['border']};
    border-radius:10px; gridline-color:{COLORS['border']}; outline:none;
}}
QTableWidget::item          {{ padding:5px; border-bottom:1px solid {COLORS['border']}; }}
QTableWidget::item:selected {{ background:{COLORS['glow']}; color:{COLORS['accent']}; }}
QTableWidget::item:alternate {{ background:{COLORS['card']}; }}
QSplitter::handle:horizontal {{ background:{COLORS['border']}; width:4px; }}
QSplitter::handle:horizontal:hover {{ background:{COLORS['accent']}; }}
"""

class GlowButton(QPushButton):
    """Outlined button with a subtle hover glow."""
    def __init__(self, label, color=None, parent=None):
        super().__init__(label, parent)
        c = color or COLORS["accent"]
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:1.5px solid {c};
                border-radius:7px; color:{c};
                font-weight:bold; letter-spacing:1px;
                padding:0 16px; font-size:11px;
            }}
            QPushButton:hover   {{ background:{c}20; color:white; }}
            QPushButton:pressed {{ background:{c}40; }}
            QPushButton:disabled {{ border-color:{COLORS['border']}; color:{COLORS['muted']}; }}
        """)


class PulsingDot(QWidget):
    """Small animated status indicator dot."""
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self._color = color or COLORS["accent"]
        self._phase = 0.0
        self.setFixedSize(12, 12)
        QTimer(self, timeout=self._tick, interval=40).start()

    def _tick(self):
        self._phase = (self._phase + 0.09) % (2 * math.pi)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2
        alpha  = int(80 + 80 * math.sin(self._phase))
        radius = int(2 + 1.5 * abs(math.sin(self._phase)))

        glow = QColor(self._color)
        glow.setAlpha(alpha // 3)
        p.setPen(Qt.NoPen); p.setBrush(glow)
        p.drawEllipse(cx - 5, cy - 5, 10, 10)

        dot = QColor(self._color)
        dot.setAlpha(min(255, alpha + 80))
        p.setBrush(dot)
        p.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)


class RingGauge(QWidget):
    """Animated arc gauge that smoothly animates toward a target value."""
    def __init__(self, label="", color=None, parent=None):
        super().__init__(parent)
        self._label   = label
        self._color   = color or COLORS["accent"]
        self._current = 0.0
        self._target  = 0.0
        self.setFixedSize(110, 110)
        QTimer(self, timeout=self._tick, interval=16).start()

    def set_value(self, v):
        self._target = max(0.0, min(1.0, v))

    def _tick(self):
        diff = self._target - self._current
        if abs(diff) > 0.001:
            self._current += diff * 0.07
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h   = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r, pw  = 42, 7

        # background ring
        p.setPen(QPen(QColor(COLORS["border"]), pw, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(cx - r, cy - r, r * 2, r * 2, 90 * 16, -360 * 16)

        # filled arc
        gradient = QConicalGradient(cx, cy, 90)
        gradient.setColorAt(0, QColor(self._color))
        gradient.setColorAt(1, QColor(COLORS["purple"]))
        p.setPen(QPen(QBrush(gradient), pw, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx - r, cy - r, r * 2, r * 2,
                  90 * 16, int(-self._current * 360 * 16))

        # percentage text
        p.setPen(QColor(COLORS["text"]))
        p.setFont(QFont(MONO, 15, QFont.Bold))
        p.drawText(QRect(0, cy - 12, w, 22), Qt.AlignCenter,
                   f"{int(self._current * 100)}%")

        # label below
        p.setFont(QFont(MONO, 8))
        p.setPen(QColor(COLORS["muted"]))
        p.drawText(QRect(0, cy + 10, w, 14), Qt.AlignCenter, self._label)


class Sparkline(QWidget):
    """Rolling line chart for tracking a value over time."""
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self._points = []
        self._color  = color or COLORS["accent"]
        self.setFixedHeight(44)
        self.setMinimumWidth(60)

    def push(self, value):
        self._points.append(float(value))
        if len(self._points) > 80:
            self._points.pop(0)
        self.update()

    def paintEvent(self, _):
        if len(self._points) < 2:
            return
        p   = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        lo   = min(self._points)
        hi   = max(self._points)
        span = hi - lo or 1

        def x_pos(i): return int(i / (len(self._points) - 1) * (w - 4)) + 2
        def y_pos(v): return int((1 - (v - lo) / span) * (h - 8)) + 4

        # filled area
        area = QPainterPath()
        area.moveTo(x_pos(0), h)
        area.lineTo(x_pos(0), y_pos(self._points[0]))
        for i in range(1, len(self._points)):
            area.lineTo(x_pos(i), y_pos(self._points[i]))
        area.lineTo(x_pos(len(self._points) - 1), h)
        gradient = QLinearGradient(0, 0, 0, h)
        fill = QColor(self._color); fill.setAlpha(55)
        fade = QColor(self._color); fade.setAlpha(0)
        gradient.setColorAt(0, fill); gradient.setColorAt(1, fade)
        p.setPen(Qt.NoPen); p.setBrush(QBrush(gradient)); p.drawPath(area)

        # line
        line = QPainterPath()
        line.moveTo(x_pos(0), y_pos(self._points[0]))
        for i in range(1, len(self._points)):
            line.lineTo(x_pos(i), y_pos(self._points[i]))
        p.setPen(QPen(QColor(self._color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush); p.drawPath(line)

        # dot at latest value
        lx = x_pos(len(self._points) - 1)
        ly = y_pos(self._points[-1])
        p.setBrush(QColor(self._color)); p.setPen(Qt.NoPen)
        p.drawEllipse(lx - 3, ly - 3, 6, 6)


class StatCard(QFrame):
    """Small info card with title, big value, subtitle and a sparkline."""
    def __init__(self, title, color=None, parent=None):
        super().__init__(parent)
        self._color = color or COLORS["accent"]
        self.setStyleSheet(
            f"QFrame{{background:{COLORS['card']};"
            f"border:1px solid {COLORS['border']};border-radius:12px;}}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(3)

        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(
            f"color:{COLORS['muted']};font-size:9px;letter-spacing:2px;"
            f"border:none;background:transparent;")
        layout.addWidget(title_lbl)

        self._value_lbl = QLabel("—")
        self._value_lbl.setStyleSheet(
            f"color:{self._color};font-size:22px;font-weight:bold;"
            f"border:none;background:transparent;")
        layout.addWidget(self._value_lbl)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setStyleSheet(
            f"color:{COLORS['muted']};font-size:10px;border:none;background:transparent;")
        layout.addWidget(self._sub_lbl)

        self._spark = Sparkline(self._color)
        layout.addWidget(self._spark)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18); shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.setGraphicsEffect(shadow)

    def update(self, value_str, sub_str="", push_to_sparkline=None):
        self._value_lbl.setText(value_str)
        self._sub_lbl.setText(sub_str)
        if push_to_sparkline is not None:
            self._spark.push(push_to_sparkline)


class CandidateBarChart(QWidget):
    """
    Bar chart showing the top-20 candidate schedules from the last optimise run.
    The golden bar is the MC winner; grey bars are the rest.
    Hovering shows the fitness value.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._candidates  = []   # list of {"norm", "is_best", "real", "tasks"}
        self._anim_heights = []  # animated bar heights (0→1)
        self._hovered      = -1
        self.setMinimumHeight(180)
        self.setMouseTracking(True)
        QTimer(self, timeout=self._tick, interval=16).start()

    def load(self, candidates):
        self._candidates   = candidates
        self._anim_heights = [0.0] * len(candidates)
        self.update()

    def _tick(self):
        changed = False
        for i, c in enumerate(self._candidates):
            diff = c["norm"] - self._anim_heights[i]
            if abs(diff) > 0.002:
                self._anim_heights[i] += diff * 0.1
                changed = True
        if changed:
            self.update()

    def mouseMoveEvent(self, e):
        if not self._candidates:
            self._hovered = -1; return
        bar_w = max(6, (self.width() - 20) // len(self._candidates) - 3)
        idx   = int((e.position().x() - 10) / (bar_w + 3))
        self._hovered = idx if 0 <= idx < len(self._candidates) else -1
        self.update()

    def leaveEvent(self, _):
        self._hovered = -1; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if not self._candidates:
            p.setPen(QColor(COLORS["muted"]))
            p.setFont(QFont(MONO, 10))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Press  ⚡ OPTIMISE  to see candidates")
            return

        n       = len(self._candidates)
        bar_w   = max(6, (w - 20) // n - 3)
        max_bar = h - 36

        for i, c in enumerate(self._candidates):
            x      = 10 + i * (bar_w + 3)
            bar_h  = max(2, int(self._anim_heights[i] * max_bar))
            y      = h - 20 - bar_h

            if c["is_best"]:
                grad = QLinearGradient(x, y + bar_h, x, y)
                grad.setColorAt(0, QColor(COLORS["gold"]))
                grad.setColorAt(1, QColor(COLORS["accent"]))
            elif i == self._hovered:
                grad = QLinearGradient(x, y + bar_h, x, y)
                grad.setColorAt(0, QColor(COLORS["purple"]))
                grad.setColorAt(1, QColor(COLORS["accent"]))
            else:
                grad = QLinearGradient(x, y + bar_h, x, y)
                grad.setColorAt(0, QColor(COLORS["purple"]))
                grad.setColorAt(1, QColor(COLORS["purple"]))

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            path = QPainterPath()
            path.addRoundedRect(x, y, bar_w, bar_h, 2, 2)
            p.drawPath(path)

            if c["is_best"]:
                glow = QColor(COLORS["gold"]); glow.setAlpha(25)
                p.setBrush(glow)
                p.drawRoundedRect(x - 2, y - 2, bar_w + 4, bar_h + 4, 3, 3)

        # baseline
        p.setPen(QPen(QColor(COLORS["border"]), 1))
        p.drawLine(10, h - 20, w - 10, h - 20)

        # hover tooltip
        if 0 <= self._hovered < n:
            c   = self._candidates[self._hovered]
            tip = f"#{self._hovered + 1}  penalty={c['real']:.1f}"
            bx  = 10 + self._hovered * (bar_w + 3)
            tx  = min(bx, w - 120)
            p.setFont(QFont(MONO, 9)); p.setPen(QColor(COLORS["text"]))
            bg = QColor(COLORS["card"]); bg.setAlpha(220)
            p.fillRect(QRect(tx, 2, 116, 18), bg)
            p.drawText(QRect(tx, 2, 116, 18), Qt.AlignCenter, tip)

        # winner label at bottom
        best = next((c for c in self._candidates if c["is_best"]), None)
        if best:
            p.setFont(QFont(MONO, 8)); p.setPen(QColor(COLORS["gold"]))
            p.drawText(QRect(0, h - 18, w, 16), Qt.AlignCenter,
                       f"▲ MC winner  penalty = {best['real']:.1f}")


class GenerationLogTable(QWidget):
    """Table that records one row per optimise run."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["RUN", "POP", "SURR BEST", "MC BEST", "TOP ORDER"])
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

    def add_row(self, run, pop_size, surr_best, mc_best, task_names):
        row = self._table.rowCount()
        self._table.insertRow(row)
        values  = [str(run), str(pop_size), f"{surr_best:.3f}", f"{mc_best:.1f}",
                   " → ".join(task_names[:6]) + (" …" if len(task_names) > 6 else "")]
        colours = [COLORS["accent"], COLORS["muted"], COLORS["gold"],
                   COLORS["success"], COLORS["text"]]
        for col, (val, col_color) in enumerate(zip(values, colours)):
            item = QTableWidgetItem(val)
            item.setForeground(QColor(col_color))
            item.setTextAlignment(
                Qt.AlignCenter if col < 4 else Qt.AlignLeft | Qt.AlignVCenter)
            self._table.setItem(row, col, item)
        self._table.scrollToBottom()

class TaskDatabase:
    """Simple SQLite wrapper for persisting user tasks."""

    def __init__(self):
        self.conn = sqlite3.connect("tasks.db")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id       INTEGER PRIMARY KEY,
                name     TEXT,
                deadline TEXT,
                duration INTEGER,
                priority INTEGER
            )""")
        self.conn.commit()

    def add(self, name, deadline, duration, priority):
        self.conn.execute(
            "INSERT INTO tasks (name, deadline, duration, priority) VALUES (?,?,?,?)",
            (name, deadline, duration, priority))
        self.conn.commit()

    def delete(self, task_id):
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def all_tasks(self):
        """Returns list of (id, name, deadline, duration, priority)."""
        return self.conn.execute(
            "SELECT id, name, deadline, duration, priority "
            "FROM tasks ORDER BY deadline ASC, priority DESC"
        ).fetchall()

    def find_id(self, name, deadline):
        """Look up a task's DB id by name + deadline (used after reordering)."""
        row = self.conn.execute(
            "SELECT id FROM tasks WHERE name=? AND deadline=? LIMIT 1",
            (name, deadline)).fetchone()
        return row[0] if row else None


class Optimiser:
    """
    Wraps the genetic + surrogate + Monte Carlo pipeline.

    Flow per run:
      1. Build a population of 50 schedules (evolve from previous or generate fresh).
      2. Score all 50 with the surrogate models (fast, approximate).
      3. Take the top 20 by surrogate score.
      4. Run Monte Carlo on those 20 (realistic but slower).
      5. The Monte Carlo winner is the recommended schedule.
      6. Store all 20 surrogate+MC results in objective.db so the
         surrogate can learn from them next time.
    """

    POPULATION_SIZE = 50
    TOP_N_FOR_MC    = 20

    def __init__(self):
        self.obj_surrogate  = Objectivesurrogate()
        self.perf_surrogate = PerformanceSurrogate()
        self.sched_gen      = SchedGen()
        self.population     = []   # kept between runs so we can evolve
        self.run_count      = 0

    def run(self, tasks):
        """Run one optimisation cycle and return result dict."""
        self.run_count += 1

        # ── 1. Retrain surrogates on accumulated data ─────────────────────
        self.obj_surrogate.Train()
        self.perf_surrogate.Train()

        # ── 2. Build population ───────────────────────────────────────────
        if not self.population:
            # First run — generate from scratch
            population = [
                self.sched_gen.generate(tasks)
                for _ in range(self.POPULATION_SIZE)
            ]
        else:
            # Subsequent runs — evolve the previous population
            population = self._evolve(tasks)

        # ── 3. Score every schedule with the surrogates ───────────────────
        for schedule in population:
            obj_score  = self.obj_surrogate.Predict(schedule)
            perf_score = self.perf_surrogate.Predict(schedule)
            schedule._fitness = (obj_score + perf_score) / 2

        # Sort best-first; use list index as tiebreaker (avoids comparing Schedules)
        population.sort(key=lambda s: s._fitness, reverse=True)
        surr_best = population[0]._fitness

        # ── 4. Run Monte Carlo on the top 20 ─────────────────────────────
        top20    = population[:self.TOP_N_FOR_MC]
        mc_scores = {}

        for schedule in top20:
            mc = MonteCarloStuff(schedule)
            mc_scores[id(schedule)] = mc
            # Store in objective.db so the objective surrogate can learn
            self.sched_gen.StoreObjectiveTrainingExample(schedule, mc)

        # ── 5. Pick the MC winner ─────────────────────────────────────────
        best_schedule = max(top20, key=lambda s: mc_scores[id(s)])
        best_mc       = mc_scores[id(best_schedule)]

        # ── 6. Keep population alive for next run ─────────────────────────
        self.population = population

        # ── Build chart data for the UI ───────────────────────────────────
        # MonteCarloStuff returns -avg_penalty (higher = better, always ≤ 0).
        # Negate here so the UI shows a positive penalty score where
        # 0 = perfect and larger = more missed deadlines / lateness.
        mc_display = {id(s): -mc_scores[id(s)] for s in top20}
        mc_lo      = min(mc_display.values())
        mc_hi      = max(mc_display.values())
        mc_range   = mc_hi - mc_lo or 1

        # Norm: best schedule (lowest penalty) gets the tallest bar.
        candidates = [
            {
                "norm":    1.0 - (mc_display[id(s)] - mc_lo) / mc_range,
                "is_best": s is best_schedule,
                "real":    mc_display[id(s)],
                "tasks":   [t.name for t in s.tasks],
            }
            for s in top20
        ]

        return {
            "run":           self.run_count,
            "pop_size":      len(population),
            "surr_best":     surr_best,
            "mc_best":       mc_display[id(best_schedule)],  # positive penalty
            "candidates":    candidates,
            "best_schedule": best_schedule,
            "population":    population,
        }

    def _evolve(self, tasks):
        """
        Breed a new population from the previous one.
        Tournament selection → crossover → mutate.
        10 % are fresh random schedules to maintain diversity.
        """
        prev = self.population
        children = []

        def tournament_pick():
            contenders = random.sample(prev, min(3, len(prev)))
            return max(contenders, key=lambda s: getattr(s, "_fitness", 0.0))

        while len(children) < self.POPULATION_SIZE:
            parent_a = tournament_pick()
            parent_b = tournament_pick()
            child    = self.sched_gen.Crossover(parent_a, parent_b)
            child    = self.sched_gen.Mutate(child)
            children.append(child)

        # Replace the last 10 % with fresh random schedules
        n_fresh = max(1, self.POPULATION_SIZE // 10)
        for i in range(n_fresh):
            children[-(i + 1)] = self.sched_gen.generate(tasks)

        return children

    def reset(self):
        """Call when the task set changes so we don't evolve a stale population."""
        self.population = []


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class SchedulerApp(QWidget):

    def __init__(self):
        super().__init__()
        self.db         = TaskDatabase()
        self.optimiser  = Optimiser()
        self.schedule   = Schedule()   # current ordered schedule shown in the table
        self.run_count  = 0

        self.setWindowTitle("◈  NEURAL SCHEDULER")
        self.setGeometry(60, 40, 1540, 900)
        self._build_ui()
        self.setStyleSheet(STYLESHEET)
        self._load_tasks()
        self._start_clock()
        self._fade_in()

    # ──────────────────────────────────────────────────────────────────────
    #  FADE-IN ANIMATION
    # ──────────────────────────────────────────────────────────────────────

    def _fade_in(self):
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(700)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        QTimer.singleShot(60, anim.start)
        self._fade_anim = anim   # keep reference so GC doesn't destroy it

    # ──────────────────────────────────────────────────────────────────────
    #  CLOCK
    # ──────────────────────────────────────────────────────────────────────

    def _start_clock(self):
        self._tick_clock()
        QTimer(self, timeout=self._tick_clock, interval=1000).start()

    def _tick_clock(self):
        now = datetime.now()
        self.clock_lbl.setText(now.strftime("%H:%M:%S"))
        self.date_lbl.setText(now.strftime("%a %d %b"))

    # ──────────────────────────────────────────────────────────────────────
    #  UI CONSTRUCTION
    # ──────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        # Right-hand main area
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)
        main_layout.addLayout(self._build_topbar())
        main_layout.addLayout(self._build_stat_cards())

        # Resizable split between task list and analytics panel
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_task_panel())
        splitter.addWidget(self._build_analytics_panel())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([860, 680])
        main_layout.addWidget(splitter, stretch=1)

        root.addWidget(main_widget, stretch=1)

    # ── SIDEBAR ────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(215)
        sidebar.setStyleSheet(
            f"QFrame{{background:{COLORS['surface']};"
            f"border-right:1px solid {COLORS['border']};}}")

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(14, 22, 14, 22)
        lay.setSpacing(5)

        # Logo
        logo = QLabel("◈ NEURAL\nSCHEDULER")
        logo.setStyleSheet(
            f"color:{COLORS['accent']};font-size:17px;font-weight:bold;"
            f"letter-spacing:2px;border:none;background:transparent;padding-bottom:12px;")
        lay.addWidget(logo)

        divider = QFrame(); divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(
            f"border:1px solid {COLORS['border']};background:transparent;")
        lay.addWidget(divider)
        lay.addSpacing(6)

        # Status row
        status_row = QHBoxLayout()
        self._status_dot = PulsingDot()
        self._status_lbl = QLabel("READY")
        self._status_lbl.setStyleSheet(
            f"color:{COLORS['accent']};font-size:10px;letter-spacing:2px;"
            f"border:none;background:transparent;")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_lbl)
        status_row.addStretch()
        lay.addLayout(status_row)
        lay.addSpacing(14)

        def section_label(text):
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(
                f"color:{COLORS['muted']};font-size:9px;letter-spacing:2px;"
                f"border:none;background:transparent;padding-top:6px;")
            return lbl

        # ── Add-task form ─────────────────────────────────────────────────
        lay.addWidget(section_label("add task"))

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Task name …")
        lay.addWidget(self.name_input)

        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        lay.addWidget(self.date_input)

        self.time_input = QTimeEdit()
        self.time_input.setTime(QTime.currentTime())
        lay.addWidget(self.time_input)

        for label_text, attr_name, suffix, val_range, default in [
            ("Duration",     "dur_spin",  " min", (1, 1440), 30),
            ("Priority",     "pri_spin",  "",     (1, 5),     3),
            ("Cog load ×10", "cog_spin",  "",     (1, 10),    1),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"color:{COLORS['muted']};font-size:10px;"
                f"border:none;background:transparent;")
            spin = QSpinBox()
            spin.setSuffix(suffix)
            spin.setRange(*val_range)
            spin.setValue(default)
            row.addWidget(lbl); row.addWidget(spin)
            lay.addLayout(row)
            setattr(self, attr_name, spin)

        add_btn = GlowButton("＋  ADD TASK", COLORS["accent"])
        add_btn.clicked.connect(self._add_task)
        lay.addWidget(add_btn)
        lay.addSpacing(12)

        # ── Action buttons ────────────────────────────────────────────────
        lay.addWidget(section_label("controls"))

        self._opt_btn = GlowButton("⚡  OPTIMISE", COLORS["gold"])
        self._opt_btn.clicked.connect(self._run_optimise)
        lay.addWidget(self._opt_btn)

        refresh_btn = GlowButton("↺  REFRESH", COLORS["purple"])
        refresh_btn.clicked.connect(self._load_tasks)
        lay.addWidget(refresh_btn)

        finish_btn = GlowButton("✓  FINISH", COLORS["success"])
        finish_btn.clicked.connect(self._finish_session)
        lay.addWidget(finish_btn)

        lay.addStretch()

        # Clock
        self.clock_lbl = QLabel("00:00:00")
        self.clock_lbl.setAlignment(Qt.AlignCenter)
        self.clock_lbl.setStyleSheet(
            f"color:{COLORS['accent']};font-size:20px;font-weight:bold;"
            f"letter-spacing:3px;border:none;background:transparent;")
        lay.addWidget(self.clock_lbl)

        self.date_lbl = QLabel("")
        self.date_lbl.setAlignment(Qt.AlignCenter)
        self.date_lbl.setStyleSheet(
            f"color:{COLORS['muted']};font-size:9px;"
            f"border:none;background:transparent;")
        lay.addWidget(self.date_lbl)

        return sidebar

    # ── TOPBAR ─────────────────────────────────────────────────────────────

    def _build_topbar(self):
        lay = QHBoxLayout()
        title = QLabel("SCHEDULE OVERVIEW")
        title.setStyleSheet(
            f"color:{COLORS['text']};font-size:18px;"
            f"font-weight:bold;letter-spacing:2px;border:none;")
        lay.addWidget(title)
        lay.addStretch()

        self._run_lbl = QLabel("RUN 0")
        self._run_lbl.setStyleSheet(
            f"color:{COLORS['muted']};font-size:11px;border:none;")
        lay.addWidget(self._run_lbl)

        self._mc_lbl = QLabel("MC PENALTY: —")
        self._mc_lbl.setStyleSheet(
            f"color:{COLORS['gold']};font-size:11px;"
            f"font-weight:bold;border:none;margin-left:14px;")
        lay.addWidget(self._mc_lbl)

        return lay

    # ── STAT CARDS ─────────────────────────────────────────────────────────

    def _build_stat_cards(self):
        lay = QHBoxLayout(); lay.setSpacing(10)
        self.card_tasks = StatCard("Total Tasks",     COLORS["accent"])
        self.card_mc    = StatCard("MC Penalty",      COLORS["gold"])
        self.card_runs  = StatCard("Optimise Runs",   COLORS["purple"])
        self.card_dur   = StatCard("Sched Duration",  COLORS["success"])
        for card in (self.card_tasks, self.card_mc, self.card_runs, self.card_dur):
            lay.addWidget(card)
        return lay

    # ── TASK LIST PANEL ────────────────────────────────────────────────────

    def _build_task_panel(self):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{COLORS['card']};"
            f"border:1px solid {COLORS['border']};border-radius:14px;}}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 14, 14, 14)

        header = QHBoxLayout()
        cap = QLabel("ACTIVE TASK LIST")
        cap.setStyleSheet(
            f"color:{COLORS['accent']};font-size:10px;letter-spacing:2px;"
            f"font-weight:bold;border:none;background:transparent;")
        header.addWidget(cap)
        header.addStretch()
        header.addWidget(PulsingDot(COLORS["purple"]))
        lay.addLayout(header)

        self.task_table = QTableWidget(0, 6)
        self.task_table.setHorizontalHeaderLabels(
            ["✓", "TASK", "DEADLINE", "DUR", "PRI", ""])
        self.task_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.Fixed)
        self.task_table.setColumnWidth(0, 30)
        self.task_table.setColumnWidth(5, 34)
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.task_table)

        return frame

    # ── ANALYTICS PANEL (tabs) ─────────────────────────────────────────────

    def _build_analytics_panel(self):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{COLORS['card']};"
            f"border:1px solid {COLORS['border']};border-radius:14px;}}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # Tab buttons
        tab_row = QHBoxLayout(); tab_row.setSpacing(4)
        self._tab_btns = []
        for i, name in enumerate(["CANDIDATES", "RUN LOG", "PERFORMANCE"]):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(27)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; border:none;
                    color:{COLORS['muted']};
                    font-size:9px; letter-spacing:1px;
                    font-weight:bold; padding:0 8px;
                }}
                QPushButton:checked {{
                    color:{COLORS['accent']};
                    border-bottom:2px solid {COLORS['accent']};
                }}
            """)
            self._tab_btns.append(btn)
            tab_row.addWidget(btn)
        tab_row.addStretch()
        lay.addLayout(tab_row)

        self._stack = QStackedWidget()

        # ── Tab 0: Candidate bar chart + fitness history ──────────────────
        p0  = QWidget()
        p0l = QVBoxLayout(p0); p0l.setContentsMargins(0, 0, 0, 0); p0l.setSpacing(8)

        self.candidate_chart = CandidateBarChart()
        p0l.addWidget(self.candidate_chart, stretch=3)

        surr_label = QLabel("SURROGATE PREDICTED BEST  (sparkline)")
        surr_label.setStyleSheet(
            f"color:{COLORS['muted']};font-size:9px;letter-spacing:2px;"
            f"border:none;background:transparent;")
        p0l.addWidget(surr_label)

        self.surr_sparkline = Sparkline(COLORS["purple"])
        self.surr_sparkline.setFixedHeight(40)
        p0l.addWidget(self.surr_sparkline)

        mc_label = QLabel("MC PENALTY  (sparkline — lower is better)")
        mc_label.setStyleSheet(
            f"color:{COLORS['muted']};font-size:9px;letter-spacing:2px;"
            f"border:none;background:transparent;")
        p0l.addWidget(mc_label)

        self.mc_sparkline = Sparkline(COLORS["gold"])
        self.mc_sparkline.setFixedHeight(40)
        p0l.addWidget(self.mc_sparkline)

        self._stack.addWidget(p0)

        # ── Tab 1: Run log table ──────────────────────────────────────────
        p1  = QWidget()
        p1l = QVBoxLayout(p1); p1l.setContentsMargins(0, 0, 0, 0)
        self.run_log = GenerationLogTable()
        p1l.addWidget(self.run_log)
        self._stack.addWidget(p1)

        # ── Tab 2: Performance gauges ─────────────────────────────────────
        p2  = QWidget()
        p2l = QVBoxLayout(p2); p2l.setContentsMargins(0, 0, 0, 0); p2l.setSpacing(10)

        top_row = QHBoxLayout()
        self.gauge_overall = RingGauge("overall", COLORS["accent"])
        top_row.addWidget(self.gauge_overall)
        self._perf_text = QLabel(
            "Tick off tasks you\ncompleted, then press\n✓ FINISH to score.")
        self._perf_text.setStyleSheet(
            f"color:{COLORS['muted']};font-size:11px;line-height:1.8;"
            f"border:none;background:transparent;")
        top_row.addWidget(self._perf_text, stretch=1)
        p2l.addLayout(top_row)

        gauge_row = QHBoxLayout(); gauge_row.setSpacing(8)
        self.gauge_completion  = RingGauge("completion",  COLORS["success"])
        self.gauge_efficiency  = RingGauge("efficiency",  COLORS["gold"])
        self.gauge_punctuality = RingGauge("punctuality", COLORS["accent"])
        for g in (self.gauge_completion, self.gauge_efficiency, self.gauge_punctuality):
            gauge_row.addWidget(g)
        p2l.addLayout(gauge_row)
        p2l.addStretch()

        self._stack.addWidget(p2)

        lay.addWidget(self._stack, stretch=1)
        self._switch_tab(0)
        return frame

    def _switch_tab(self, idx):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == idx)

    # ──────────────────────────────────────────────────────────────────────
    #  TASK OPERATIONS
    # ──────────────────────────────────────────────────────────────────────

    def _add_task(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Enter a task name.")
            return

        deadline = datetime.combine(
            self.date_input.date().toPython(),
            self.time_input.time().toPython()
        ).isoformat()

        self.db.add(name, deadline, self.dur_spin.value(), self.pri_spin.value())
        self.name_input.clear()
        self.optimiser.reset()   # task set changed — discard stale population
        self._load_tasks()
        self._set_status("TASK ADDED", COLORS["success"])

    def _delete_task(self, task_id):
        self.db.delete(task_id)
        self.optimiser.reset()
        self._load_tasks()
        self._set_status("TASK DELETED", COLORS["danger"])

    def _load_tasks(self):
        """Reload tasks from DB and repopulate the table."""
        self.task_table.setRowCount(0)
        self.schedule.tasks = []
        total_duration = 0
        cog_load = self.cog_spin.value() / 10.0

        for row_data in self.db.all_tasks():
            task_id, name, deadline, duration, priority = row_data

            t = task(TaskType.Classical, deadline, duration,
                     priority, cog_load, name)
            self.schedule.tasks.append(t)
            total_duration += duration

            row = self.task_table.rowCount()
            self.task_table.insertRow(row)
            self.task_table.setRowHeight(row, 32)

            # Checkbox
            cb = QTableWidgetItem()
            cb.setCheckState(Qt.Unchecked)
            cb.setTextAlignment(Qt.AlignCenter)
            self.task_table.setItem(row, 0, cb)

            # Text columns
            for col, (text, color) in enumerate(zip(
                [name, deadline, f"{duration} min", f"★{priority}"],
                [COLORS["text"], COLORS["gold"], COLORS["muted"], COLORS["purple"]]
            ), start=1):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                self.task_table.setItem(row, col, item)

            # Delete button
            del_btn = self._make_delete_button(task_id)
            self.task_table.setCellWidget(row, 5, del_btn)

        n = len(self.schedule.tasks)
        self.card_tasks.update(str(n), f"{n} task{'s' if n != 1 else ''}", n)
        self.card_dur.update(f"{total_duration}m", "scheduled", total_duration)

    def _make_delete_button(self, task_id):
        btn = QPushButton("✕")
        btn.setFixedSize(24, 24)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:1px solid {COLORS['danger']};
                border-radius:4px; color:{COLORS['danger']};
                font-size:10px; font-weight:bold;
            }}
            QPushButton:hover   {{ background:{COLORS['danger']}33; }}
            QPushButton:pressed {{ background:{COLORS['danger']}66; }}
        """)
        btn.clicked.connect(lambda _, tid=task_id: self._delete_task(tid))
        return btn

    def _reorder_table(self, best_schedule):
        """
        After optimisation, redisplay the task table in the recommended order
        without writing back to the DB (the DB order doesn't matter for optimisation).
        """
        self.schedule.tasks = list(best_schedule.tasks)
        self.task_table.setRowCount(0)

        for t in best_schedule.tasks:
            row = self.task_table.rowCount()
            self.task_table.insertRow(row)
            self.task_table.setRowHeight(row, 32)

            cb = QTableWidgetItem()
            cb.setCheckState(Qt.Unchecked)
            cb.setTextAlignment(Qt.AlignCenter)
            self.task_table.setItem(row, 0, cb)

            for col, (text, color) in enumerate(zip(
                [t.name, t.deadLine, f"{t.duration} min", f"★{t.priority}"],
                [COLORS["text"], COLORS["gold"], COLORS["muted"], COLORS["purple"]]
            ), start=1):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(color))
                self.task_table.setItem(row, col, item)

            task_id = self.db.find_id(t.name, t.deadLine)
            if task_id is not None:
                self.task_table.setCellWidget(row, 5, self._make_delete_button(task_id))

    # ──────────────────────────────────────────────────────────────────────
    #  OPTIMISE
    # ──────────────────────────────────────────────────────────────────────

    def _run_optimise(self):
        if not self.schedule.tasks:
            QMessageBox.warning(self, "No tasks", "Add some tasks first.")
            return

        self._opt_btn.setEnabled(False)
        self._set_status("OPTIMISING …", COLORS["gold"])
        QApplication.processEvents()   # repaint before we block the main thread

        result = self.optimiser.run(self.schedule.tasks)

        # ── Update all UI elements with the results ────────────────────────
        self.run_count += 1
        self.candidate_chart.load(result["candidates"])
        self.surr_sparkline.push(result["surr_best"])
        self.mc_sparkline.push(result["mc_best"])

        self.run_log.add_row(
            result["run"],
            result["pop_size"],
            result["surr_best"],
            result["mc_best"],
            [t.name for t in result["best_schedule"].tasks],
        )

        self.card_mc.update(
            f"{result['mc_best']:.1f}",
            "MC score",
            result["mc_best"],
        )
        self.card_runs.update(
            str(result["run"]),
            "optimise runs",
            result["run"],
        )
        self._run_lbl.setText(f"RUN {result['run']}")
        self._mc_lbl.setText(f"MC PENALTY: {result['mc_best']:.1f}")

        self._reorder_table(result["best_schedule"])
        self._opt_btn.setEnabled(True)
        self._set_status("OPTIMISED ✓", COLORS["success"])

    # ──────────────────────────────────────────────────────────────────────
    #  FINISH SESSION  —  score the user's actual execution
    # ──────────────────────────────────────────────────────────────────────

    def _finish_session(self):
        if not self.schedule.tasks:
            QMessageBox.warning(self, "No tasks", "Nothing to finish.")
            return

        execution_log = self._build_execution_log()

        # CalculateActualUserPerformance returns a 0-1 score
        performance = CalculateActualUserPerformance(self.schedule, execution_log)

        # Store in performance.db so the performance surrogate can learn
        self.schedule.encodeAsTensor()
        self.optimiser.sched_gen.StorePerformanceTrainingExample(
            self.schedule, performance)

        # Derive readable metrics from the log
        n              = len(execution_log)
        tasks_done     = sum(1 for e in execution_log if e["completed"])
        on_time_count  = sum(
            1 for e in execution_log
            if e["end"] <= datetime.fromisoformat(e["task"].deadLine)
        )
        late_names     = [
            e["task"].name for e in execution_log
            if e["end"] > datetime.fromisoformat(e["task"].deadLine)
        ]
        missed_names   = [
            e["task"].name for e in execution_log if not e["completed"]
        ]

        completion_rate  = tasks_done / n
        punctuality_rate = on_time_count / n
        score_pct        = round(performance * 100)

        # Update performance gauges
        self.gauge_overall.set_value(performance)
        self.gauge_completion.set_value(completion_rate)
        self.gauge_efficiency.set_value(
            # efficiency = how close actual time was to planned time
            sum(
                min(e["task"].duration /
                    max((e["end"] - e["start"]).total_seconds() / 60, 1), 1)
                for e in execution_log
            ) / n
        )
        self.gauge_punctuality.set_value(punctuality_rate)

        # Build the summary text
        lines = [
            f"Score:       {score_pct} / 100",
            f"Completed:   {tasks_done} of {n} tasks",
            f"On time:     {on_time_count} of {n} tasks",
        ]
        if late_names:
            lines.append(f"Late:        {', '.join(late_names)}")
        if missed_names:
            lines.append(f"Not done:    {', '.join(missed_names)}")

        self._perf_text.setText("\n".join(lines))
        self._perf_text.setStyleSheet(
            f"color:{COLORS['text']};font-size:11px;line-height:1.8;"
            f"border:none;background:transparent;")

        self._switch_tab(2)
        self._set_status(f"SCORE {score_pct}/100", COLORS["success"])
        QMessageBox.information(
            self, "Session complete",
            f"Score: {score_pct}/100\n"
            f"Completed: {tasks_done}/{n} tasks\n"
            f"On time: {on_time_count}/{n} tasks"
        )

    def _build_execution_log(self):
        """
        Build the execution log that MonteCarlo.CalculateActualUserPerformance
        expects:  list of {"task", "start", "end", "completed"}.

        We simulate sequential execution starting now, using each task's
        planned duration. The user's checkbox determines "completed".
        """
        log  = []
        now  = datetime.now()

        for i, t in enumerate(self.schedule.tasks):
            checkbox = self.task_table.item(i, 0)
            done     = checkbox is not None and checkbox.checkState() == Qt.Checked
            end_time = now + timedelta(minutes=t.duration)

            log.append({
                "task":      t,
                "start":     now,
                "end":       end_time,
                "completed": done,
            })
            now = end_time

        return log

    # ──────────────────────────────────────────────────────────────────────
    #  STATUS BAR  (auto-resets after 4 s)
    # ──────────────────────────────────────────────────────────────────────

    def _set_status(self, text, color=None):
        color = color or COLORS["accent"]
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"color:{color};font-size:10px;letter-spacing:2px;"
            f"border:none;background:transparent;")
        QTimer.singleShot(4000, self._reset_status)

    def _reset_status(self):
        self._status_lbl.setText("READY")
        self._status_lbl.setStyleSheet(
            f"color:{COLORS['accent']};font-size:10px;letter-spacing:2px;"
            f"border:none;background:transparent;")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SchedulerApp()
    win.show()
    sys.exit(app.exec())