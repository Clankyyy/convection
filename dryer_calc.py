#!/usr/bin/env python3
"""Расчёт аппарата конвективной сушки."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import math


# ── физические функции ────────────────────────────────────────────

def sat_pressure(t: float) -> float:
    """Давление насыщенного пара воды при t °C, Па."""
    return 610.78 * math.exp(17.2694 * t / (t + 238.3))


def moisture_content(phi_pct: float, t: float, P: float = 101325.0) -> float:
    """Влагосодержание воздуха x, кг/кг с.в."""
    ps  = sat_pressure(t)
    phi = phi_pct / 100.0
    return 0.622 * phi * ps / (P - phi * ps)


def enthalpy(t: float, x: float) -> float:
    """Энтальпия влажного воздуха I, кДж/кг с.в."""
    return 1.006 * t + x * (2501.0 + 1.805 * t)


def relative_humidity_from_tx(t: float, x: float, P: float = 101325.0) -> float:
    """Относительная влажность φ, %."""
    ps = sat_pressure(t)
    pv = x * P / (0.622 + x)
    return min(pv / ps * 100.0, 100.0)


def dew_point(x: float, P: float = 101325.0) -> float:
    """Точка росы, °C."""
    pv = x * P / (0.622 + x)
    lnr = math.log(pv / 610.78)
    return 238.3 * lnr / (17.2694 - lnr)


def specific_volume(t: float, x: float, P: float = 101325.0) -> float:
    """Удельный объём влажного воздуха, м³/кг с.в."""
    return 287.1 * (t + 273.15) * (1.0 + x / 0.622) / P


# ── основной расчёт ───────────────────────────────────────────────

def run_calculation(p: dict) -> dict:
    G1          = p['G1']
    w1          = p['w1']
    w2          = p['w2']
    t0          = p['t0']
    phi0        = p['phi0']
    t1          = p['t1']
    t2          = p['t2']
    is_ideal    = p['ideal']
    q_loss_pct  = p['q_loss_pct']
    q_mat       = p['q_mat']       # кДж/кг испарённой влаги
    w_air       = p['w_air']
    P           = 101325.0

    # 1. Материальный баланс
    Gc = G1 * (1.0 - w1 / 100.0)
    G2 = Gc / (1.0 - w2 / 100.0)
    W  = G1 - G2

    # 2. Параметры воздуха — точка 0 (свежий воздух)
    ps0 = sat_pressure(t0)
    x0  = moisture_content(phi0, t0, P)
    I0  = enthalpy(t0, x0)
    v0  = specific_volume(t0, x0, P)

    # Точка 1 — после калорифера (x не меняется)
    x1 = x0
    I1 = enthalpy(t1, x1)
    v1 = specific_volume(t1, x1, P)

    # Точка 2 — на выходе из сушилки
    if is_ideal:
        # I1 = I2  →  x2 из энтальпии
        x2 = (I1 - 1.006 * t2) / (2501.0 + 1.805 * t2)
    else:
        # Итерация: L*(I1-I2) = Q_loss + q_mat*W
        x2 = (I1 - 1.006 * t2) / (2501.0 + 1.805 * t2)   # начальное приближение
        for _ in range(60):
            dx = x2 - x0
            if dx <= 0:
                break
            L_est   = W / dx
            Q_cal_e = L_est * (I1 - I0)
            Q_loss  = q_loss_pct / 100.0 * Q_cal_e
            Q_mat_t = q_mat * W
            I2_tgt  = I1 - (Q_loss + Q_mat_t) / L_est
            x2_new  = (I2_tgt - 1.006 * t2) / (2501.0 + 1.805 * t2)
            if abs(x2_new - x2) < 1e-9:
                x2 = x2_new
                break
            x2 = x2_new

    if x2 <= x0:
        raise ValueError(
            "Влагосодержание на выходе x₂ ≤ x₀.\n"
            "Проверьте данные: возможно, t₂ слишком мало или потери слишком велики."
        )

    I2   = enthalpy(t2, x2)
    v2   = specific_volume(t2, x2, P)
    phi2 = relative_humidity_from_tx(t2, x2, P)
    td2  = dew_point(x2, P)

    # 3. Расход воздуха
    l     = 1.0 / (x2 - x0)
    L     = l * W
    v_avg = (v0 + v2) / 2.0
    L_vol = L * v_avg

    # 4. Тепловой баланс
    Q_cal    = L * (I1 - I0)
    Q_cal_kW = Q_cal / 3600.0
    q_spec   = Q_cal / W
    Q_loss   = 0.0 if is_ideal else (q_loss_pct / 100.0 * Q_cal)

    # 5. Размеры
    F_cross = L_vol / 3600.0 / w_air if w_air > 0 else None
    D_equiv = math.sqrt(4.0 * F_cross / math.pi) if F_cross else None

    return dict(
        G1=G1, w1=w1, w2=w2, t0=t0, phi0=phi0,
        t1=t1, t2=t2, is_ideal=is_ideal,
        q_loss_pct=q_loss_pct, q_mat=q_mat, w_air=w_air,
        Gc=Gc, G2=G2, W=W,
        ps0=ps0, x0=x0, I0=I0, v0=v0,
        x1=x1, I1=I1, v1=v1,
        x2=x2, I2=I2, v2=v2, phi2=phi2, td2=td2,
        l=l, L=L, v_avg=v_avg, L_vol=L_vol,
        Q_cal=Q_cal, Q_cal_kW=Q_cal_kW, q_spec=q_spec, Q_loss=Q_loss,
        F_cross=F_cross, D_equiv=D_equiv,
    )


# ── GUI ──────────────────────────────────────────────────────────

class DryerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Расчёт аппарата конвективной сушки")
        self.geometry("1020x760")
        self.minsize(800, 600)
        self.resizable(True, True)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabelframe.Label", font=("Helvetica", 9, "bold"))
        style.configure("Header.TLabel", font=("Helvetica", 13, "bold"),
                        background="#2c3e50", foreground="white")

        self._init_vars()
        self._build_ui()

    # ── переменные ──────────────────────────────────────────────
    def _init_vars(self):
        self.v = {
            'G1':         tk.DoubleVar(value=1000.0),
            'w1':         tk.DoubleVar(value=50.0),
            'w2':         tk.DoubleVar(value=5.0),
            't0':         tk.DoubleVar(value=20.0),
            'phi0':       tk.DoubleVar(value=60.0),
            't1':         tk.DoubleVar(value=120.0),
            't2':         tk.DoubleVar(value=60.0),
            'ideal':      tk.BooleanVar(value=True),
            'q_loss_pct': tk.DoubleVar(value=5.0),
            'q_mat':      tk.DoubleVar(value=0.0),
            'w_air':      tk.DoubleVar(value=2.0),
        }

    # ── вспомогательный метод: строка поля ввода ─────────────
    def _field(self, parent, row, label, key, unit="", width=10):
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 6), pady=3)
        e = ttk.Entry(parent, textvariable=self.v[key], width=width)
        e.grid(row=row, column=1, sticky="w", pady=3)
        if unit:
            ttk.Label(parent, text=unit).grid(
                row=row, column=2, sticky="w", padx=(3, 0))
        return e

    # ── построение UI ───────────────────────────────────────────
    def _build_ui(self):
        # Заголовок
        hdr = tk.Frame(self, bg="#2c3e50")
        hdr.pack(fill=tk.X)
        tk.Label(
            hdr,
            text="  Расчёт аппарата конвективной сушки",
            font=("Helvetica", 13, "bold"),
            bg="#2c3e50", fg="white",
            padx=8, pady=8,
        ).pack(side=tk.LEFT)

        # Notebook
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tab_in  = ttk.Frame(self.nb)
        tab_res = ttk.Frame(self.nb)
        tab_ixd = ttk.Frame(self.nb)
        self.nb.add(tab_in,  text="  Исходные данные  ")
        self.nb.add(tab_res, text="  Результаты  ")
        self.nb.add(tab_ixd, text="  I–x диаграмма  ")

        self._build_input(tab_in)
        self._build_results(tab_res)
        self._build_diagram(tab_ixd)

        # Нижняя панель кнопок
        bar = tk.Frame(self, relief=tk.GROOVE, bd=1, bg="#ecf0f1")
        bar.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Button(bar, text="Рассчитать",
                   command=self.calculate).pack(side=tk.RIGHT, padx=6, pady=5)
        ttk.Button(bar, text="Сохранить результаты",
                   command=self.save_results).pack(side=tk.RIGHT, padx=2, pady=5)
        ttk.Button(bar, text="Очистить",
                   command=self.clear).pack(side=tk.RIGHT, padx=2, pady=5)

    # ── вкладка исходных данных ──────────────────────────────────
    def _build_input(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        # Материальный баланс
        fm = ttk.LabelFrame(parent, text=" Материальный баланс ", padding=12)
        fm.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._field(fm, 0, "Производительность по влажному материалу  G₁ =", "G1",  "кг/ч")
        self._field(fm, 1, "Начальная влажность материала (масс., влажн.)  w₁ =", "w1", "%")
        self._field(fm, 2, "Конечная влажность материала                   w₂ =", "w2", "%")

        # Параметры воздуха
        fa = ttk.LabelFrame(parent, text=" Параметры сушильного агента ", padding=12)
        fa.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self._field(fa, 0, "Температура окружающего воздуха  t₀ =",     "t0",   "°C")
        self._field(fa, 1, "Относительная влажность воздуха  φ₀ =",     "phi0", "%")
        self._field(fa, 2, "Температура после калорифера      t₁ =",    "t1",   "°C")
        self._field(fa, 3, "Температура на выходе из сушилки  t₂ =",    "t2",   "°C")

        # Тип сушилки
        ft = ttk.LabelFrame(parent, text=" Тип расчёта ", padding=12)
        ft.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        ttk.Radiobutton(ft, text="Идеальная сушилка  (без тепловых потерь)",
                        variable=self.v["ideal"], value=True,
                        command=self._toggle_losses).grid(
            row=0, columnspan=3, sticky="w", pady=2)
        ttk.Radiobutton(ft, text="Реальная сушилка   (с тепловыми потерями)",
                        variable=self.v["ideal"], value=False,
                        command=self._toggle_losses).grid(
            row=1, columnspan=3, sticky="w", pady=2)

        self._loss_frame = ttk.Frame(ft)
        self._loss_frame.grid(row=2, columnspan=3, sticky="w", padx=18, pady=4)
        self._e_loss = self._field(
            self._loss_frame, 0,
            "Тепловые потери (% от Q калорифера)  =", "q_loss_pct", "%")
        self._e_mat = self._field(
            self._loss_frame, 1,
            "Доп. затраты тепла на материал  Δq  =", "q_mat",
            "кДж/кг влаги")
        self._toggle_losses()

        # Размеры
        fd = ttk.LabelFrame(parent, text=" Расчёт поперечного сечения ", padding=12)
        fd.grid(row=1, column=1, sticky="nsew", padx=8, pady=4)
        self._field(fd, 0, "Рабочая скорость воздуха  w =", "w_air", "м/с")
        ttk.Label(fd, text="(используется для расчёта площади поперечного сечения канала)",
                  foreground="gray", font=("Helvetica", 9)).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _toggle_losses(self):
        state = tk.NORMAL if not self.v["ideal"].get() else tk.DISABLED
        self._e_loss.config(state=state)
        self._e_mat.config(state=state)

    # ── вкладка результатов ──────────────────────────────────────
    def _build_results(self, parent):
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self.txt = tk.Text(
            parent,
            font=("Courier New", 10),
            wrap=tk.NONE,
            bg="#f9f9f9",
            relief=tk.FLAT,
            padx=10, pady=6,
        )
        vsb = ttk.Scrollbar(parent, orient="vertical",   command=self.txt.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.txt.xview)
        self.txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.txt.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.txt.tag_configure("hdr",  font=("Courier New", 10, "bold"))
        self.txt.tag_configure("sec",  font=("Courier New", 10, "bold"),
                               foreground="#1a5276")
        self.txt.tag_configure("sep",  foreground="#aab7b8")

    # ── вкладка I–x диаграммы ────────────────────────────────────
    def _build_diagram(self, parent):
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(parent, bg="white", relief=tk.SUNKEN, bd=1)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.canvas.bind("<Configure>", lambda e: self._redraw_diagram())
        self._diagram_data = None

    # ── очистка ─────────────────────────────────────────────────
    def clear(self):
        self.txt.config(state=tk.NORMAL)
        self.txt.delete("1.0", tk.END)
        self.canvas.delete("all")
        self._diagram_data = None

    # ── валидация ────────────────────────────────────────────────
    def _validate(self) -> dict:
        try:
            vals = {k: self.v[k].get() for k in self.v}
        except tk.TclError as exc:
            raise ValueError(f"Ошибка в поле ввода: {exc}") from exc

        if vals["G1"] <= 0:
            raise ValueError("Производительность G₁ должна быть положительной.")
        if not (0 < vals["w1"] < 100):
            raise ValueError("Начальная влажность w₁ должна быть в диапазоне (0, 100) %.")
        if not (0 < vals["w2"] < 100):
            raise ValueError("Конечная влажность w₂ должна быть в диапазоне (0, 100) %.")
        if vals["w2"] >= vals["w1"]:
            raise ValueError("Конечная влажность w₂ должна быть меньше начальной w₁.")
        if not (0 < vals["phi0"] <= 100):
            raise ValueError("Относительная влажность φ₀ должна быть в диапазоне (0, 100] %.")
        if vals["t1"] <= vals["t0"]:
            raise ValueError("Температура t₁ (после калорифера) должна быть выше t₀.")
        if vals["t2"] >= vals["t1"]:
            raise ValueError("Температура на выходе t₂ должна быть ниже t₁.")
        if vals["t2"] <= 0:
            raise ValueError("Температура на выходе t₂ должна быть выше 0 °C.")
        if not vals["ideal"]:
            if not (0 <= vals["q_loss_pct"] < 100):
                raise ValueError("Тепловые потери должны быть в диапазоне [0, 100) %.")
        return vals

    # ── основной расчёт ──────────────────────────────────────────
    def calculate(self):
        try:
            vals = self._validate()
        except ValueError as exc:
            messagebox.showerror("Ошибка ввода", str(exc))
            return

        try:
            r = run_calculation(vals)
        except ValueError as exc:
            messagebox.showerror("Ошибка расчёта", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Неожиданная ошибка", str(exc))
            return

        self._display(r)
        self._diagram_data = r
        self._redraw_diagram()
        self.nb.select(1)

    # ── вывод результатов ────────────────────────────────────────
    def _display(self, r: dict):
        self.clear()
        t = self.txt
        W = "=" * 70
        D = "-" * 70

        def w(text, tag=None):
            t.insert(tk.END, text + "\n", tag or "")

        w(W, "sep")
        w("   РАСЧЁТ АППАРАТА КОНВЕКТИВНОЙ СУШКИ", "hdr")
        w(W, "sep")
        w("")
        w("ИСХОДНЫЕ ДАННЫЕ:", "sec")
        w(D, "sep")
        w(f"  Производительность по влажному материалу  G₁  = {r['G1']:.1f} кг/ч")
        w(f"  Начальная влажность материала             w₁  = {r['w1']:.2f} %")
        w(f"  Конечная влажность материала              w₂  = {r['w2']:.2f} %")
        w(f"  Температура окружающего воздуха           t₀  = {r['t0']:.1f} °C")
        w(f"  Относительная влажность воздуха           φ₀  = {r['phi0']:.1f} %")
        w(f"  Температура воздуха после калорифера      t₁  = {r['t1']:.1f} °C")
        w(f"  Температура воздуха на выходе             t₂  = {r['t2']:.1f} °C")
        mode = "идеальная (без потерь)" if r["is_ideal"] else f"реальная (потери {r['q_loss_pct']:.1f} %)"
        w(f"  Тип сушилки:                                    {mode}")
        w("")

        w("1. МАТЕРИАЛЬНЫЙ БАЛАНС", "sec")
        w(D, "sep")
        w(f"  Расход абсолютно сухого материала         Gс  = {r['Gc']:.2f} кг/ч")
        w(f"  Производительность по сухому материалу    G₂  = {r['G2']:.2f} кг/ч")
        w(f"  Количество испарённой влаги               W   = {r['W']:.2f} кг/ч")
        w(f"                                                = {r['W']/3600:.5f} кг/с")
        w("")

        w("2. ПАРАМЕТРЫ СУШИЛЬНОГО АГЕНТА (ВОЗДУХА)", "sec")
        w(D, "sep")
        w("  Точка 0 — свежий воздух:")
        w(f"    Давление насыщенного пара   ps₀  = {r['ps0']/1000:.4f} кПа")
        w(f"    Влагосодержание             x₀   = {r['x0']*1000:.3f} г/кг с.в.  "
          f"({r['x0']:.6f} кг/кг с.в.)")
        w(f"    Энтальпия                   I₀   = {r['I0']:.2f} кДж/кг с.в.")
        w(f"    Удельный объём              v₀   = {r['v0']:.4f} м³/кг с.в.")
        w("")
        w("  Точка 1 — после калорифера:")
        w(f"    Влагосодержание             x₁   = x₀ = {r['x1']*1000:.3f} г/кг с.в.")
        w(f"    Энтальпия                   I₁   = {r['I1']:.2f} кДж/кг с.в.")
        w(f"    Удельный объём              v₁   = {r['v1']:.4f} м³/кг с.в.")
        w("")
        w("  Точка 2 — на выходе из сушилки:")
        w(f"    Влагосодержание             x₂   = {r['x2']*1000:.3f} г/кг с.в.  "
          f"({r['x2']:.6f} кг/кг с.в.)")
        w(f"    Энтальпия                   I₂   = {r['I2']:.2f} кДж/кг с.в.")
        w(f"    Относительная влажность     φ₂   = {r['phi2']:.1f} %")
        w(f"    Точка росы                  td₂  = {r['td2']:.1f} °C")
        w(f"    Удельный объём              v₂   = {r['v2']:.4f} м³/кг с.в.")
        w("")

        w("3. РАСХОД ВОЗДУХА", "sec")
        w(D, "sep")
        w(f"  Удельный расход сухого воздуха   l   = 1/(x₂−x₀) = {r['l']:.2f} кг с.в./кг влаги")
        w(f"  Массовый расход сухого воздуха   L   = l·W        = {r['L']:.2f} кг с.в./ч")
        w(f"  Ср. удельный объём воздуха       v̄   =            = {r['v_avg']:.4f} м³/кг с.в.")
        w(f"  Объёмный расход воздуха          Lv  = L·v̄        = {r['L_vol']:.2f} м³/ч")
        w(f"                                                     = {r['L_vol']/3600:.5f} м³/с")
        w("")

        w("4. ТЕПЛОВОЙ БАЛАНС", "sec")
        w(D, "sep")
        w(f"  Уд. расход тепла в калорифере    q   = I₁−I₀      = {r['I1']-r['I0']:.2f} кДж/кг с.в.")
        w(f"  Тепловая нагрузка калорифера     Q   = L·(I₁−I₀)  = {r['Q_cal']:.2f} кДж/ч")
        w(f"                                                     = {r['Q_cal_kW']:.3f} кВт")
        w(f"  Уд. расход тепла на испарение    q′  = Q/W         = {r['q_spec']:.2f} кДж/кг влаги")
        if not r["is_ideal"]:
            w(f"  Тепловые потери                  Q_п              = {r['Q_loss']:.2f} кДж/ч")
            w(f"                                                     = {r['Q_loss']/3600:.3f} кВт")
        w("")

        w("5. РАСЧЁТ ПОПЕРЕЧНОГО СЕЧЕНИЯ", "sec")
        w(D, "sep")
        w(f"  Рабочая скорость воздуха         w   =            = {r['w_air']:.2f} м/с")
        if r["F_cross"]:
            w(f"  Площадь сечения                  F   = Lv/(3600w) = {r['F_cross']:.4f} м²")
            w(f"  Эквивалентный диаметр            D   =            = {r['D_equiv']:.4f} м"
              f"  (круглое сечение)")
        w("")

        w(W, "sep")
        w("  Расчёт успешно завершён.", "hdr")
        w(W, "sep")

    # ── I–x диаграмма ────────────────────────────────────────────
    def _redraw_diagram(self):
        c = self.canvas
        c.delete("all")
        r = self._diagram_data
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 100 or ch < 100:
            return
        if r is None:
            c.create_text(cw // 2, ch // 2,
                          text="Выполните расчёт, чтобы увидеть диаграмму",
                          fill="gray", font=("Helvetica", 11))
            return

        # Поля
        ml, mr, mt, mb = 70, 20, 30, 50
        pw = cw - ml - mr
        ph = ch - mt - mb

        # Диапазоны осей
        x_pts = [r["x0"], r["x1"], r["x2"]]
        I_pts = [r["I0"], r["I1"], r["I2"]]

        x_min = max(0.0, min(x_pts) * 0.85)
        x_max = max(x_pts) * 1.15
        I_min = min(I_pts) * 0.92
        I_max = max(I_pts) * 1.08

        def to_px(x, I):
            px = ml + (x - x_min) / (x_max - x_min) * pw
            py = mt + ph - (I - I_min) / (I_max - I_min) * ph
            return px, py

        # Сетка и оси
        for i in range(6):
            xi = x_min + i * (x_max - x_min) / 5
            px, _ = to_px(xi, I_min)
            c.create_line(px, mt, px, mt + ph, fill="#e0e0e0", dash=(2, 4))
            c.create_text(px, mt + ph + 14, text=f"{xi*1000:.1f}", font=("Helvetica", 8))

        for i in range(6):
            Ii = I_min + i * (I_max - I_min) / 5
            _, py = to_px(x_min, Ii)
            c.create_line(ml, py, ml + pw, py, fill="#e0e0e0", dash=(2, 4))
            c.create_text(ml - 8, py, text=f"{Ii:.0f}", font=("Helvetica", 8), anchor="e")

        # Рамка
        c.create_rectangle(ml, mt, ml + pw, mt + ph, outline="#555")

        # Подписи осей
        c.create_text(ml + pw // 2, ch - 8,
                      text="x, г/кг с.в.", font=("Helvetica", 9, "bold"))
        c.create_text(16, mt + ph // 2,
                      text="I, кДж/кг с.в.", font=("Helvetica", 9, "bold"),
                      angle=90)
        c.create_text(ml + pw // 2, 14,
                      text="I–x диаграмма (процесс сушки)",
                      font=("Helvetica", 10, "bold"), fill="#2c3e50")

        # Линия процесса нагрева в калорифере: 0 → 1 (x=const, I растёт)
        p0x, p0y = to_px(r["x0"], r["I0"])
        p1x, p1y = to_px(r["x1"], r["I1"])
        p2x, p2y = to_px(r["x2"], r["I2"])

        # Нагрев в калорифере (вертикальный отрезок на I-x)
        c.create_line(p0x, p0y, p1x, p1y, fill="#e74c3c", width=2, arrow=tk.LAST)
        # Процесс в сушилке
        c.create_line(p1x, p1y, p2x, p2y, fill="#2980b9", width=2, arrow=tk.LAST)

        # Точки и подписи
        R = 5
        for (px, py), lbl, col in [
            ((p0x, p0y), "0", "#16a085"),
            ((p1x, p1y), "1", "#e74c3c"),
            ((p2x, p2y), "2", "#2980b9"),
        ]:
            c.create_oval(px - R, py - R, px + R, py + R, fill=col, outline=col)
            c.create_text(px + 12, py - 10, text=lbl,
                          font=("Helvetica", 10, "bold"), fill=col)

        # Легенда
        ly = mt + 12
        for col, txt in [("#e74c3c", "0→1: нагрев в калорифере"),
                         ("#2980b9", "1→2: процесс сушки")]:
            c.create_line(ml + 10, ly, ml + 35, ly,
                          fill=col, width=2)
            c.create_text(ml + 40, ly, text=txt,
                          font=("Helvetica", 8), anchor="w")
            ly += 18

    # ── сохранение ───────────────────────────────────────────────
    def save_results(self):
        content = self.txt.get("1.0", tk.END)
        if not content.strip():
            messagebox.showinfo("Информация",
                                "Нет результатов для сохранения.\nСначала выполните расчёт.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовый файл", "*.txt"), ("Все файлы", "*.*")],
            title="Сохранить результаты расчёта",
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            messagebox.showinfo("Сохранено", f"Результаты сохранены:\n{path}")


if __name__ == "__main__":
    app = DryerApp()
    app.mainloop()
