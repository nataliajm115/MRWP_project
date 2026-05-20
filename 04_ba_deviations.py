"""
Step 4 - Compare the deviations of the two real networks from their
respective BA nulls.

Builds directly on the output of step 3: instead of plotting percolation
curves again, this script asks how much each real network departs from
its matched BA preferential-attachment null along the removal axis.

If the two real networks deviate from their BA nulls in the same way,
that points to a shared higher-order structural mechanism (e.g.
clustering, degree-degree correlations) acting on top of the heavy
tail. If they deviate differently, the fragility-beyond-scale-free
story is system-specific.

For each network and each strategy we compute:
  Delta(f) = S_real(f) - S_BA(f)
where S(f) is the largest-component fraction at removal fraction f.

Threshold deviations are also reported:
  Delta_fc = fc_real - fc_BA

Inputs:
  results/data/step3_percolation_curves.csv
  results/data/step3_percolation_thresholds.csv

Outputs:
  results/data/step4_ba_deviations.csv
  results/data/step4_threshold_deviations.csv
  results/plots/fig4_ba_deviations.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "results" / "data"
PLOTS_DIR = BASE_DIR / "results" / "plots"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

STEP3_CURVES = DATA_DIR / "step3_percolation_curves.csv"
STEP3_THRESHOLDS = DATA_DIR / "step3_percolation_thresholds.csv"


# Helpers
def compute_curve_deviations(curves: pd.DataFrame) -> pd.DataFrame:
    """Delta(f) = real - BA, point by point, per (network, strategy).

    The two random-failure curves are independent averages, so we
    propagate their std-deviations in quadrature to get a deviation
    band. The targeted-attack runs are deterministic (lcc_std = 0)
    so the propagated std collapses to zero, as expected.
    """
    # keep only real and BA; ER is not needed for step 4
    sub = curves[curves["model"].isin(["real", "BA"])].copy()

    wide = sub.pivot_table(
        index=["network", "strategy", "fraction_removed"],
        columns="model",
        values=["lcc_fraction", "lcc_std"],
    ).reset_index()

    # flatten the multi-index columns
    wide.columns = [
        f"{a}_{b}" if b else a for a, b in wide.columns
    ]

    wide["delta"] = wide["lcc_fraction_real"] - wide["lcc_fraction_BA"]
    wide["delta_std"] = np.sqrt(
        wide["lcc_std_real"].fillna(0) ** 2
        + wide["lcc_std_BA"].fillna(0) ** 2
    )

    return wide[[
        "network", "strategy", "fraction_removed",
        "lcc_fraction_real", "lcc_fraction_BA",
        "delta", "delta_std",
    ]]


def compute_threshold_deviations(thresholds: pd.DataFrame) -> pd.DataFrame:
    """fc_real - fc_BA per (network, strategy), with propagated std."""
    sub = thresholds[thresholds["model"].isin(["real", "BA"])].copy()

    wide = sub.pivot_table(
        index=["network", "strategy"],
        columns="model",
        values=["threshold_mean", "threshold_std"],
    ).reset_index()
    wide.columns = [f"{a}_{b}" if b else a for a, b in wide.columns]

    wide["delta_threshold"] = (
        wide["threshold_mean_real"] - wide["threshold_mean_BA"]
    )
    wide["delta_threshold_std"] = np.sqrt(
        wide["threshold_std_real"].fillna(0) ** 2
        + wide["threshold_std_BA"].fillna(0) ** 2
    )

    return wide[[
        "network", "strategy",
        "threshold_mean_real", "threshold_mean_BA",
        "delta_threshold", "delta_threshold_std",
    ]]


# Plot
def plot_deviations(deviations: pd.DataFrame, out_path: Path) -> None:
    """Two-panel figure: random failure on the left, targeted on the right.
    Both real networks overlaid as Delta(f) curves with shaded std bands.
    """
    strategies = ["random failure", "degree-targeted attack"]
    networks = sorted(deviations["network"].unique())
    colors = {"AS Internet": "C0", "WWW Notre Dame": "C3"}

    fig, axes = plt.subplots(
        1, len(strategies),
        figsize=(5.5 * len(strategies), 4),
        sharey=True, squeeze=False,
    )
    axes = axes[0]

    for ax, strategy in zip(axes, strategies):
        for network_name in networks:
            sub = deviations[
                (deviations["network"] == network_name)
                & (deviations["strategy"] == strategy)
            ].sort_values("fraction_removed")
            if sub.empty:
                continue

            color = colors.get(network_name, None)
            ax.plot(
                sub["fraction_removed"], sub["delta"],
                label=network_name, color=color,
            )
            std = sub["delta_std"].fillna(0)
            ax.fill_between(
                sub["fraction_removed"],
                sub["delta"] - std,
                sub["delta"] + std,
                color=color, alpha=0.2,
            )

        ax.axhline(0, linestyle="--", linewidth=1, color="grey")
        ax.set_title(strategy)
        ax.set_xlabel("fraction of nodes removed")
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel(r"$\Delta$(LCC fraction) = real $-$ BA")
    axes[-1].legend(frameon=False)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.show()


# Main
def main() -> None:
    if not STEP3_CURVES.exists() or not STEP3_THRESHOLDS.exists():
        raise FileNotFoundError(
            "Step 3 outputs not found. Run 03_er_ba_comparison.py first."
        )

    curves = pd.read_csv(STEP3_CURVES)
    thresholds = pd.read_csv(STEP3_THRESHOLDS)

    deviations = compute_curve_deviations(curves)
    threshold_deviations = compute_threshold_deviations(thresholds)

    deviations.to_csv(DATA_DIR / "step4_ba_deviations.csv", index=False)
    threshold_deviations.to_csv(
        DATA_DIR / "step4_threshold_deviations.csv", index=False
    )

    plot_deviations(deviations, PLOTS_DIR / "fig4_ba_deviations.png")

    print("\nSaved:")
    print(f"  {DATA_DIR / 'step4_ba_deviations.csv'}")
    print(f"  {DATA_DIR / 'step4_threshold_deviations.csv'}")
    print(f"  {PLOTS_DIR / 'fig4_ba_deviations.png'}")

    print("\nThreshold deviations (fc_real - fc_BA):")
    print(threshold_deviations.to_string(index=False))

    # quick sign-of-deviation summary to make the interpretation obvious
    print("\nMean curve deviation by network / strategy "
          "(negative = real more fragile than BA):")
    summary = (
        deviations.groupby(["network", "strategy"])["delta"]
        .agg(["mean", "min", "max"])
        .reset_index()
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
