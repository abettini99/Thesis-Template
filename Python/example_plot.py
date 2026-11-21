"""Example figure made with thesis.mplstyle; produces Images/example_plot.pdf.

Run from the repository root:  python Python/example_plot.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
plt.style.use(HERE / "thesis.mplstyle")

# Text widths of the book (mm), slightly under the nominal sizes because the class rounds the
# text width to whole points: Dover 91.5, A5 99.5, Royal 104.5, TU Delft 112.5.
# This example uses the narrowest, so it fits every page size.
TEXT_WIDTH_MM = 91.5
MM = 1 / 25.4

alpha = np.linspace(-4, 20, 200)
cl_theory = 2 * np.pi * np.radians(alpha)

fig, ax = plt.subplots(figsize=(TEXT_WIDTH_MM * MM, 0.62 * TEXT_WIDTH_MM * MM))
ax.plot(alpha, cl_theory, label="Thin-aerofoil theory")
for i, (thrust, label) in enumerate([(0.0, "Propeller off"), (0.1, r"$T_c = 0.1$"),
                                      (0.2, r"$T_c = 0.2$"), (0.3, r"$T_c = 0.3$")]):
    cl_max = 1.1 + 2.0 * thrust
    slope = 2 * np.pi * (1 + 1.5 * thrust)
    cl = 0.25 * thrust + cl_max * np.tanh(slope * np.radians(alpha) / cl_max) - 0.002 * np.maximum(alpha - 13, 0) ** 2
    ax.plot(alpha, cl, label=label)
ax.set_xlabel(r"Angle of attack $\alpha$ (deg)")
ax.set_ylabel(r"Lift coefficient $C_L$")
ax.set_xlim(-4, 20)
ax.set_ylim(-0.5, 2.2)
ax.legend(loc="lower right", ncols=2)

out = HERE.parent / "Images" / "example_plot.pdf"
fig.savefig(out)
print(f"saved {out}")
