"""Example figures made with thesis.mplstyle, at the size they are printed (demy text width).

Produces, in Images/:
    example_burgers.pdf    full width   viscous Burgers solution at four times
    example_panels.pdf     full width   two panels with their letters: solution and interpolant,
                                        convergence of the errors in Table 2.2
    example_residual.pdf   half width   Picard residuals (illustrative)
    example_energy.pdf     half width   kinetic energy of the Burgers solution
    example_plot.pdf       full width   lift curves (illustrative data)
    snapshots/snap-01.pdf  ...  snap-12.pdf, colourbar.pdf:  a blob of dye carried round by a
                                        rotation, for a grid of panels (panels environment)
    grid/burgers-1.pdf ... burgers-8.pdf:  the Burgers solution at eight times, plots with shared
                                        axes, one file each (panels environment, option natural)

Run from the repository root:  python Python/example_figures.py [--maths auto|mathtime|newtx]
The text in the figures is set in the thesis's fonts (thesis_fonts.py): Times, with MathTime maths if
it is in Fonts/, otherwise newtx. The figures that come with the template are made with newtx.
Include each figure without scaling, e.g. \\includegraphics[scale=1]{Images/example_burgers.pdf},
so the text in it keeps its size. Copy this file as a starting point for your own plots.
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import thesis_fonts

HERE = Path(__file__).parent
OUT = HERE.parent / "Images"
plt.style.use(HERE / "thesis.mplstyle")
parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("--maths", choices=("auto", "mathtime", "newtx"), default="auto",
                    help="maths font in the figures (auto: MathTime if prepared in Fonts/)")
print("figure fonts:", thesis_fonts.setup(parser.parse_args().maths))

# Text widths of the book (mm), slightly under the nominal sizes because the class rounds the
# text width to whole points: demy 91.5, A5 99.5, Royal 104.5, TU Delft 112.5. Half width (two
# figures side by side): demy 44, A5 48, Royal 50, TU Delft 54. These examples use the demy
# sizes, the narrowest, so they fit every page size.
FULL_MM, HALF_MM = 91.5, 44.0
MM = 1 / 25.4


def plot_margins(fig, left=13.0, bottom=10.6, right=2.7, top=1.5):
    """Fix the plot area by its margins (mm) instead of matplotlib's automatic layout. Figures that
    sit side by side then have plot areas of the same size, on the same baseline."""
    w, h = fig.get_size_inches() * 25.4
    fig.set_layout_engine("none")
    for ax in fig.axes:
        ax.set_position([left / w, bottom / h, 1 - (left + right) / w, 1 - (bottom + top) / h])


def save(fig, name):
    thesis_fonts.save(fig, OUT / name)
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
ax1.legend(loc="lower left", handlelength=1.0, handletextpad=0.4, borderpad=0.2,
           borderaxespad=0.1)  # the empty corner, left of the shock

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
    ax2.text(n0 / 1.08, np.sqrt(y0 * y1), str(order), ha="right", va="center", fontsize=8)
ax2.set_xlabel(r"$N$")
ax2.set_ylabel("error")
ax2.set_xticks(N, [str(n) for n in N])
ax2.minorticks_off()
for ax, letter in ((ax1, "a"), (ax2, "b")):
    ax.text(-0.02, 1.02, f"({letter})", transform=ax.transAxes, ha="right", va="bottom")
save(fig, "example_panels.pdf")

# --- Two figures side by side: Picard residuals and kinetic energy ----------------------------
# Both with the same plot margins, so their plot areas line up next to each other.
fig, ax = plt.subplots(figsize=(HALF_MM * MM, 0.85 * HALF_MM * MM))
plot_margins(fig)
k = np.arange(0, 9)
for step, rate in ((1, 0.18), (10, 0.32), (40, 0.45)):    # illustrative contraction rates
    ax.semilogy(k, rate ** k, marker="o", markersize=2.5)
    ax.text(8.6, rate ** 8, f"step {step}", va="center", fontsize=8)
ax.axhline(1e-7, color="0.4", linewidth=0.6, linestyle="-")   # tolerance, below the curves
ax.set_xlabel("iteration")
ax.set_ylabel("residual")
ax.set_ylim(1e-8, 2)
ax.set_yticks([1, 1e-2, 1e-4, 1e-6])
ax.set_xlim(-0.5, 13)
ax.set_xticks([0, 4, 8])
ax.minorticks_off()
save(fig, "example_residual.pdf")

fig, ax = plt.subplots(figsize=(HALF_MM * MM, 0.85 * HALF_MM * MM))
plot_margins(fig)
tt = np.linspace(0, 1, 101)
xq = np.linspace(-1, 1, 4001)
energy = [0.5 * np.trapezoid(burgers(xq, t) ** 2, xq) for t in tt]
ax.plot(tt, energy)
ax.axvline(1 / np.pi, color="0.4", linewidth=0.6, linestyle="--")
ax.text(1 / np.pi + 0.03, 0.22, "shock", fontsize=8)
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
ax.legend(loc="upper left")  # the empty corner: the curves start low
save(fig, "example_plot.pdf")

# --- Snapshots for a grid of panels (panels environment): a blob of dye carried round by a solid-body
# rotation while it diffuses (an exact solution), one file per snapshot, without text, so the grid may
# scale them; and the colour bar as a file of its own, at its printed size.
SNAP_MM = 30.0                                   # drawn at about the size of a panel; scaled in the grid
n_snap, kappa = 12, 2e-3
xs = np.linspace(-1, 1, 161)
Xs, Ys = np.meshgrid(xs, xs)
snap_dir = OUT / "snapshots"
snap_dir.mkdir(exist_ok=True)
for k in range(n_snap):
    t = k / n_snap                               # one revolution in t = 1
    angle = 2 * np.pi * t
    x0, y0 = 0.5 * np.cos(angle), 0.5 * np.sin(angle)
    s2 = 0.15 ** 2 + 2 * kappa * t * 8
    c = 0.15 ** 2 / s2 * np.exp(-((Xs - x0) ** 2 + (Ys - y0) ** 2) / (2 * s2))
    fig = plt.figure(figsize=(SNAP_MM * MM, SNAP_MM * MM))
    fig.set_layout_engine("none")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(c, extent=(-1, 1, -1, 1), origin="lower", cmap="viridis", vmin=0, vmax=1,
              interpolation="none")
    ax.plot(0, 0, "+", color="w", markersize=4, markeredgewidth=0.6)   # the centre of rotation
    ax.set_aspect("equal")
    ax.set_axis_off()
    save(fig, f"snapshots/snap-{k + 1:02d}.pdf")
fig = plt.figure(figsize=(60 * MM, 13 * MM))
fig.set_layout_engine("none")
cax = fig.add_axes([0.08, 0.72, 0.84, 0.16])
mappable = plt.cm.ScalarMappable(norm=plt.Normalize(0, 1), cmap="viridis")
fig.colorbar(mappable, cax=cax, orientation="horizontal", ticks=[0, 0.5, 1])
cax.set_xlabel(r"concentration $c/c_0$", labelpad=1)
save(fig, "snapshots/colourbar.pdf")


# --- A grid of plots with shared axes, as panels -------------------------------------------------------
# For the panels environment with the option natural: every plot in a file of its own, all with the same
# plot area, so LaTeX can line them up and letter them; only the plots of the left column carry the
# y tick labels and those of the bottom row the x tick labels. The axis titles, letters and labels are
# set by LaTeX (xlabel=, ylabel= and the labels of \panel), so they are not drawn here.
#   \begin{panels}[columns=2, natural, labels=inside, xlabel={$x$}, ylabel={$u$}]
#       \panel{Images/grid/burgers-1.pdf}{$t = 0.125$}  ...
#   \end{panels}
PAD_MM = 2.0      # the margin round every plot area in the files (the panels option pad, 2 mm by default)
LEFT_MM = 6.0     # an estimate of the y tick labels' width, to size the plots (save_panels measures it)


def panel_grid(nrows, ncols, width_mm=FULL_MM - 6.0, aspect=1.6, gap_mm=2.0):
    """nrows x ncols plots with shared axes, sized so that the files of save_panels, set side by side
    with gap_mm between them (the panels default), are width_mm wide together. The 6 mm less than the
    text width leave room for the y axis title that LaTeX sets beside the grid."""
    pw = (width_mm - LEFT_MM - 2 * PAD_MM * ncols - gap_mm * (ncols - 1)) / ncols
    ph = pw / aspect
    space = 20.0                                 # the plots far apart: each file holds one plot only
    W = LEFT_MM + ncols * (pw + space)
    H = 6.0 + nrows * (ph + space)
    fig = plt.figure(figsize=(W * MM, H * MM))
    fig.set_layout_engine("none")
    axes = np.empty((nrows, ncols), dtype=object)
    for r in range(nrows):
        for c in range(ncols):
            x0 = LEFT_MM + space / 2 + c * (pw + space)
            y0 = 6.0 + space / 2 + (nrows - 1 - r) * (ph + space)
            ax = fig.add_axes([x0 / W, y0 / H, pw / W, ph / H],
                              sharex=axes[0, 0] if (r or c) else None, sharey=axes[0, 0] if (r or c) else None)
            ax.tick_params(labelbottom=(r == nrows - 1), labelleft=(c == 0))
            axes[r, c] = ax
    return fig, axes


def save_panels(fig, axes, stem):
    """Saves every plot of panel_grid in a file of its own: stem-1.pdf, stem-2.pdf, ... row by row.
    Each file is the plot area with PAD_MM round it; the files of the left column are wider by the width
    of the y tick labels, those of the bottom row higher by the height of the x tick labels, measured
    here (the widest and highest of each), so all files of a column, and of a row, are the same size.
    LaTeX finds those extra sizes from the file sizes."""
    from matplotlib.transforms import Bbox
    nrows, ncols = axes.shape
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inch = fig.dpi_scale_trans.inverted()
    plot = {ax: ax.get_position().transformed(fig.transFigure).transformed(inch) for ax in axes.flat}
    tight = {ax: ax.get_tightbbox(renderer).transformed(inch) for ax in axes.flat}
    pad = PAD_MM * MM
    # everything that sticks out of a plot area (ticks, a tick label at its edge) must fit in the pad,
    # except the tick labels on the left of the left column and under the bottom row
    for (r, c), ax in np.ndenumerate(axes):
        out = [tight[ax].x1 - plot[ax].x1, tight[ax].y1 - plot[ax].y1]
        if c:
            out.append(plot[ax].x0 - tight[ax].x0)
        if r < nrows - 1:
            out.append(plot[ax].y0 - tight[ax].y0)
        if max(out) > pad:
            raise ValueError(f"plot {r + 1},{c + 1} sticks out {max(out) / MM:.1f} mm: make PAD_MM larger")
    left = max(plot[ax].x0 - tight[ax].x0 for ax in axes[:, 0]) - pad + 0.3 * MM
    bottom = max(plot[ax].y0 - tight[ax].y0 for ax in axes[-1, :]) - pad + 0.3 * MM
    for k, ((r, c), ax) in enumerate(np.ndenumerate(axes), start=1):
        for other in axes.flat:
            other.set_visible(other is ax)
        b = plot[ax]
        box = Bbox([[b.x0 - pad - left * (c == 0), b.y0 - pad - bottom * (r == nrows - 1)],
                    [b.x1 + pad, b.y1 + pad]])
        thesis_fonts.save(fig, OUT / f"{stem}-{k}.pdf", bbox_inches=box)
        print(f"saved {OUT / stem}-{k}.pdf")
    for ax in axes.flat:
        ax.set_visible(True)
    plt.close(fig)


(OUT / "grid").mkdir(exist_ok=True)
fig, axes = panel_grid(4, 2)
for ax, t in zip(axes.flat, np.linspace(0.125, 1.0, 8)):
    ax.plot(x, burgers(x, t))
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1.15, 1.15)
    ax.set_xticks([-1, 0, 1])
    ax.set_yticks([-1, 0, 1])
save_panels(fig, axes, "grid/burgers")
