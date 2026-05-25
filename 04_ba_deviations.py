"""
Step 4 - Deviations of the real networks from their matched null models.

We also report a summary quantity, the share of the real-vs-ER
threshold gap that is closed by moving from ER to BA and from BA to
CM. This makes it easy to read off, for each network and strategy,
how much explanatory work each successive null does.

Inputs:
  results/data/step3_percolation_curves.csv
  results/data/step3_percolation_thresholds.csv

Outputs:
  results/data/step4_null_deviations.csv          (point-wise curves)
  results/data/step4_threshold_deviations.csv     (per-null thresholds)
  results/data/step4_explained_shares.csv         (summary)
  results/plots/fig4_null_deviations.png
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

NULL_MODELS = ["ER", "BA", "CM"]
NULL_COLORS = {"ER": "#DC267F", "BA": "#FFB000", "CM": "#785EF0"}
NULL_LINESTYLES = {"ER": "--", "BA": ":", "CM": "-."}


# Curve deviations
def compute_curve_deviations(curves: pd.DataFrame) -> pd.DataFrame:
    """Delta(f) = S_real(f) - S_null(f), per (network, strategy, null model).

    The std on the deviation is propagated in quadrature from the
    real and null random-failure stds. For targeted attack both
    stds are zero, so the band collapses, as expected.
    """
    real = curves[curves["model"] == "real"].rename(
        columns={"lcc_fraction": "lcc_real", "lcc_std": "std_real"}
    )[["network", "strategy", "fraction_removed", "lcc_real", "std_real"]]

    rows = []
    for null in NULL_MODELS:
        nullc = curves[curves["model"] == null].rename(
            columns={
                "lcc_fraction": f"lcc_{null}",
                "lcc_std": f"std_{null}",
            }
        )[["network", "strategy", "fraction_removed",
           f"lcc_{null}", f"std_{null}"]]

        merged = real.merge(
            nullc, on=["network", "strategy", "fraction_removed"], how="inner"
        )
        merged["null_model"] = null
        merged["delta"] = merged["lcc_real"] - merged[f"lcc_{null}"]
        merged["delta_std"] = np.sqrt(
            merged["std_real"].fillna(0) ** 2
            + merged[f"std_{null}"].fillna(0) ** 2
        )
        rows.append(merged[[
            "network", "strategy", "null_model", "fraction_removed",
            "lcc_real", f"lcc_{null}", "delta", "delta_std",
        ]].rename(columns={f"lcc_{null}": "lcc_null"}))

    return pd.concat(rows, ignore_index=True)


# Threshold deviations
def compute_threshold_deviations(thresholds: pd.DataFrame) -> pd.DataFrame:
    # fc_real - fc_null per (network, strategy, null model)
    real = thresholds[thresholds["model"] == "real"].rename(
        columns={"threshold_mean": "fc_real", "threshold_std": "fc_real_std"}
    )[["network", "strategy", "fc_real", "fc_real_std"]]

    rows = []
    for null in NULL_MODELS:
        nullt = thresholds[thresholds["model"] == null].rename(
            columns={
                "threshold_mean": "fc_null",
                "threshold_std": "fc_null_std",
            }
        )[["network", "strategy", "fc_null", "fc_null_std"]]
        merged = real.merge(nullt, on=["network", "strategy"], how="inner")
        merged["null_model"] = null
        merged["delta_fc"] = merged["fc_real"] - merged["fc_null"]
        merged["delta_fc_std"] = np.sqrt(
            merged["fc_real_std"].fillna(0) ** 2
            + merged["fc_null_std"].fillna(0) ** 2
        )
        rows.append(merged)

    out = pd.concat(rows, ignore_index=True)
    return out[[
        "network", "strategy", "null_model",
        "fc_real", "fc_null", "delta_fc", "delta_fc_std",
    ]]


# Explained-share summary
def compute_explained_shares(threshold_devs: pd.DataFrame) -> pd.DataFrame:
    """How much of the real-vs-ER threshold gap is closed by BA and CM?

    For each (network, strategy):
      gap_ER  = |fc_real - fc_ER|         (total gap to the no-heavy-tail null)
      gap_BA  = |fc_real - fc_BA|         (gap remaining after a BA heavy tail)
      gap_CM  = |fc_real - fc_CM|         (gap remaining after fixing the exact degree sequence)

      explained_by_BA = 1 - gap_BA / gap_ER   share of the real-vs-ER gap closed by moving from ER to BA
      explained_by_CM = 1 - gap_CM / gap_ER   share closed by moving from ER all the way to CM

    A high explained_by_CM means the degree sequence is doing almost
    all the explanatory work; a low value means there is substantial
    fragility beyond the degree distribution itself.
    """
    pivot = threshold_devs.pivot_table(
        index=["network", "strategy"],
        columns="null_model",
        values="delta_fc",
    ).reset_index()

    pivot["gap_ER"] = pivot["ER"].abs()
    pivot["gap_BA"] = pivot["BA"].abs()
    pivot["gap_CM"] = pivot["CM"].abs()

    with np.errstate(divide="ignore", invalid="ignore"):
        pivot["explained_by_BA"] = 1.0 - pivot["gap_BA"] / pivot["gap_ER"]
        pivot["explained_by_CM"] = 1.0 - pivot["gap_CM"] / pivot["gap_ER"]

    return pivot[[
        "network", "strategy",
        "gap_ER", "gap_BA", "gap_CM",
        "explained_by_BA", "explained_by_CM",
    ]]


# Plot
def plot_deviations(deviations: pd.DataFrame, out_path: Path) -> None:
    """Grid: rows = networks, cols = strategies; each panel overlays
    Delta_ER, Delta_BA, Delta_CM vs fraction removed."""
    networks = sorted(deviations["network"].unique())
    strategies = ["random failure", "degree-targeted attack"]

    fig, axes = plt.subplots(
        len(networks), len(strategies),
        figsize=(5.5 * len(strategies), 4 * len(networks)),
        sharey="row", squeeze=False,
    )

    for r, network_name in enumerate(networks):
        for c, strategy in enumerate(strategies):
            ax = axes[r, c]
            for null in NULL_MODELS:
                sub = deviations[
                    (deviations["network"] == network_name)
                    & (deviations["strategy"] == strategy)
                    & (deviations["null_model"] == null)
                ].sort_values("fraction_removed")
                if sub.empty:
                    continue

                ax.plot(
                    sub["fraction_removed"], sub["delta"],
                    label=f"real - {null}",
                    color=NULL_COLORS[null],
                    linestyle=NULL_LINESTYLES[null],
                    linewidth=2,
                )
                std = sub["delta_std"].fillna(0)
                if (std > 0).any():
                    ax.fill_between(
                        sub["fraction_removed"],
                        sub["delta"] - std,
                        sub["delta"] + std,
                        color=NULL_COLORS[null], alpha=0.15,
                    )

            ax.axhline(0, linestyle="--", linewidth=1, color="grey",
                       label="null baseline (Δ = 0)")
            ax.set_title(f"{network_name} – {strategy}")
            ax.set_xlabel("fraction of nodes removed")
            ax.grid(True, alpha=0.3)
        axes[r, 0].set_ylabel(r"$\Delta$(LCC fraction) = real $-$ null")
    axes[0, -1].legend(frameon=False, loc="lower right")
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
    threshold_devs = compute_threshold_deviations(thresholds)
    shares = compute_explained_shares(threshold_devs)

    deviations.to_csv(DATA_DIR / "step4_null_deviations.csv", index=False)
    threshold_devs.to_csv(
        DATA_DIR / "step4_threshold_deviations.csv", index=False
    )
    shares.to_csv(DATA_DIR / "step4_explained_shares.csv", index=False)

    plot_deviations(deviations, PLOTS_DIR / "fig4_null_deviations.png")

    print("\nSaved:")
    print(f"  {DATA_DIR / 'step4_null_deviations.csv'}")
    print(f"  {DATA_DIR / 'step4_threshold_deviations.csv'}")
    print(f"  {DATA_DIR / 'step4_explained_shares.csv'}")
    print(f"  {PLOTS_DIR / 'fig4_null_deviations.png'}")

    print("\nThreshold deviations (fc_real - fc_null):")
    print(threshold_devs.to_string(index=False))

    print("\nShare of the real-vs-ER threshold gap closed by each null"
          " (1.00 = real and null collapse at the same point):")
    print(shares.to_string(index=False))

    print("\nCurve-deviation summary by network / strategy / null"
          " (negative mean = real more fragile than null on average):")
    summary = (
        deviations.groupby(["network", "strategy", "null_model"])["delta"]
        .agg(["mean", "min", "max"])
        .reset_index()
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()