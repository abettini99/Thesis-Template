"""Example figures made with thesis.mplstyle, at the size they are printed (Dover text width).

Produces, in Images/:
    example_burgers.pdf    full width   viscous Burgers solution at four times
    example_panels.pdf     full width   two panels with their letters: solution and interpolant,
                                        convergence of the errors in Table 2.2
    example_residual.pdf   half width   Picard residuals (illustrative)
    example_energy.pdf     half width   kinetic energy of the Burgers solution
    example_plot.pdf       full width   lift curves (illustrative data)

Run from the repository root:  python Python/example_figures.py
Include each figure without scaling, e.g. \\includegraphics[scale=1]{Images/example_burgers.pdf},
so the text in it keeps its size. Copy this file as a starting point for your own plots.
"""
from pathlib import Path

import matplotlib.text
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
OUT = HERE.parent / "Images"
plt.style.use(HERE / "thesis.mplstyle")

# Text widths of the book (mm), slightly under the nominal sizes because the class rounds the
# text width to whole points: Dover 91.5, A5 99.5, Royal 104.5, TU Delft 112.5. Half width (two
# figures side by side): Dover 44, A5 48, Royal 50, TU Delft 54. These examples use the Dover
# sizes, the narrowest, so they fit every page size.
FULL_MM, HALF_MM = 91.5, 44.0
MM = 1 / 25.4


def save(fig, name):
    # Matplotlib 3.11 and later join "ff", "fi", "fl" into ligatures, which its PDF output stores as a
    # missing glyph: the PDF/A check then fails and the text cannot be copied. Switch them off.
    for text in fig.findobj(matplotlib.text.Text):
        if hasattr(text, "set_fontfeatures"):
            text.set_fontfeatures(["-liga", "-clig"])
    fig.savefig(OUT / name)
    plt.close(fig)
    print(f"saved {OUT / name}")


# ---------------------------------------------------------------------------------------------
# Viscous Burgers equation  u_t + u u_x = nu u_xx  on (-1, 1), u(x, 0) = -sin(pi x), u(+-1) = 0.
# Exact solution by the Cole-Hopf transformation, evaluated with Gauss-Hermite quadrature
# (in log form, as the exponentials overflow for small nu).
# ---------------------------------------------------------------------------------------------
NU = 0.01 / np.pi
Z, W = np.polynomial.hermite.hermgauss(200)


def burgers(x, t):
    x = np.atleast_1d(x).astype(float)
    if t == 0:
        return -np.sin(np.pi * x)
    s = np.sqrt(4 * NU * t)
    y = x[:, None] - s * Z[None, :]                       # points x - eta
    a = -np.cos(np.pi * y) / (2 * np.pi * NU)             # log of f(x - eta)
    a -= a.max(axis=1, keepdims=True)
    e = W[None, :] * np.exp(a)
    return -(np.sin(np.pi * y) * e).sum(axis=1) / e.sum(axis=1)


x = np.linspace(-1, 1, 1601)

# --- Single figure: the solution at four times ------------------------------------------------
fig, ax = plt.subplots(figsize=(FULL_MM * MM, 0.55 * FULL_MM * MM))
for t in (0.0, 0.25, 0.5, 1.0):
    ax.plot(x, burgers(x, t), label=rf"$t = {t:g}$")
ax.set_xlabel(r"$x$")
ax.set_ylabel(r"$u$")
ax.set_xlim(-1, 1)
ax.set_ylim(-1.1, 1.1)
ax.set_xticks([-1, -0.5, 0, 0.5, 1])
ax.legend(loc="upper right")
save(fig, "example_burgers.pdf")

# --- Two panels, with the panel letters drawn in ----------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL_MM * MM, 0.46 * FULL_MM * MM))
t = 0.5
ax1.plot(x, burgers(x, t), label="exact")
xn = np.linspace(-1, 1, 17)                               # 16 linear elements
ax1.plot(xn, burgers(xn, t), marker="o", label="$N = 16$")
ax1.set_xlabel(r"$x$")
ax1.set_ylabel(r"$u$")
ax1.set_xlim(-1, 1)
ax1.legend(loc="upper right", handlelength=1.2, borderaxespad=0.2)

N = np.array([8, 16, 32, 64, 128])                         # the errors of Table 2.2
e0 = np.array([3.41e-3, 8.80e-4, 2.23e-4, 5.62e-5, 1.41e-5])
e1 = np.array([1.08e-1, 5.46e-2, 2.74e-2, 1.37e-2, 6.87e-3])
ax2.loglog(N, e1, marker="o")
ax2.loglog(N, e0, marker="s")
# Lines labelled directly, which reads faster than a legend in a small panel.
ax2.text(70, 2.6e-2, r"$\Vert\nabla \boldsymbol{e}\Vert_\Omega$")
ax2.text(70, 1.0e-4, r"$\Vert \boldsymbol{e}\Vert_\Omega$")
for e, order in ((e1, 1), (e0, 2)):                        # slope triangles, below each line
    n0, n1 = 16, 32
    y0 = e[1] * 0.45
    y1 = y0 * (n0 / n1) ** order
    ax2.plot([n0, n1, n0, n0], [y0, y1, y1, y0], color="0.4", linewidth=0.6, linestyle="-")
    ax2.text(n0 / 1.08, np.sqrt(y0 * y1), str(order), ha="right", va="center", fontsize=7)
ax2.set_xlabel(r"$N$")
ax2.set_ylabel("error")
ax2.set_xticks(N, [str(n) for n in N])
ax2.minorticks_off()
for ax, letter in ((ax1, "a"), (ax2, "b")):
    ax.text(-0.02, 1.02, f"({letter})", transform=ax.transAxes, ha="right", va="bottom")
save(fig, "example_panels.pdf")

# --- Two figures side by side: Picard residuals and kinetic energy ----------------------------
fig, ax = plt.subplots(figsize=(HALF_MM * MM, 0.85 * HALF_MM * MM))
k = np.arange(0, 9)
for step, rate in ((1, 0.18), (10, 0.32), (40, 0.45)):    # illustrative contraction rates
    ax.semilogy(k, rate ** k, marker="o", markersize=2.5)
    ax.text(8.6, rate ** 8, f"step {step}", va="center", fontsize=7)
ax.axhline(1e-6, color="0.4", linewidth=0.6, linestyle="-")
ax.set_xlabel("iteration")
ax.set_ylabel("residual")
ax.set_ylim(1e-7, 2)
ax.set_xlim(-0.5, 13)
ax.set_xticks([0, 4, 8])
ax.minorticks_off()
save(fig, "example_residual.pdf")

fig, ax = plt.subplots(figsize=(HALF_MM * MM, 0.85 * HALF_MM * MM))
tt = np.linspace(0, 1, 101)
xq = np.linspace(-1, 1, 4001)
energy = [0.5 * np.trapezoid(burgers(xq, t) ** 2, xq) for t in tt]
ax.plot(tt, energy)
ax.axvline(1 / np.pi, color="0.4", linewidth=0.6, linestyle="--")
ax.text(1 / np.pi + 0.03, 0.22, "shock", fontsize=7)
ax.set_xlabel(r"$t$")
ax.set_ylabel(r"$E$")
ax.set_xlim(0, 1)
save(fig, "example_energy.pdf")

# --- Lift curves (illustrative data) -----------------------------------------------------------
alpha = np.linspace(-4, 20, 200)
fig, ax = plt.subplots(figsize=(FULL_MM * MM, 0.62 * FULL_MM * MM))
ax.plot(alpha, 2 * np.pi * np.radians(alpha), label="Thin-aerofoil theory")
for thrust, label in [(0.0, "Propeller off"), (0.1, r"$T_c = 0.1$"),
                      (0.2, r"$T_c = 0.2$"), (0.3, r"$T_c = 0.3$")]:
    cl_max = 1.1 + 2.0 * thrust
    slope = 2 * np.pi * (1 + 1.5 * thrust)
    cl = (0.25 * thrust + cl_max * np.tanh(slope * np.radians(alpha) / cl_max)
          - 0.002 * np.maximum(alpha - 13, 0) ** 2)
    ax.plot(alpha, cl, label=label)
ax.set_xlabel(r"Angle of attack $\alpha$ (deg)")
ax.set_ylabel(r"Lift coefficient $C_L$")
ax.set_xlim(-4, 20)
ax.set_ylim(-0.5, 2.2)
ax.legend(loc="lower right", ncols=2)
save(fig, "example_plot.pdf")
