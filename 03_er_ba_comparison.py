"""
Step 3 - Compare the empirical networks with matched ER and BA null models.

For each real network (AS Internet, WWW Notre Dame) we:
  1. build an Erdos-Renyi graph with the same N and edge probability
     p = E / C(N, 2) so the expected number of edges matches the real graph;
  2. build a Barabasi-Albert graph with the same N and m = round(E / N)
     so the average degree 2m matches the real graph;
  3. run the same two percolation experiments as step 2 on real / ER / BA:
       - random failure         (averaged over N_RANDOM_RUNS independent seeds)
       - degree-targeted attack (single deterministic run, adaptive)
  4. record the LCC-fraction curve and the empirical collapse threshold.


Outputs:
  results/data/step3_percolation_curves.csv
  results/data/step3_percolation_thresholds.csv
  results/plots/fig3_percolation_curves.png
"""

import importlib.util
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from graph_io import load_graph, NETWORK_FILES


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "results" / "data"
PLOTS_DIR = BASE_DIR / "results" / "plots"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# to impor the functios from 02_percolation.py 
_spec = importlib.util.spec_from_file_location(
    "step2", BASE_DIR / "02_percolation.py"
)
step2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(step2)

# Experiment settings (as for step 2) 
N_RANDOM_RUNS = 20      # independent random-failure runs to average over
RANDOM_SEED = 42        
N_STEPS = 100           # number of checkpoints along the removal axis
COLLAPSE_LEVEL = 0.05   # LCC fraction at which we declare the giant component has "collapsed"

# to do both AS internet and WWW
AS_ONLY = False


# ---------------------------------------------------------------------------
# Reference networks and two helpers
# ---------------------------------------------------------------------------
def generate_reference_networks(G, seed = RANDOM_SEED):
    """Return ER and BA graphs matched to G in size and density.

    ER: same N, edge probability p = E / C(N, 2)  -> matched edges.
    BA: same N, attachment parameter m = round(E / N) -> matched <k>
        (BA adds m edges per new node, so it ends up with ~m*N edges).
    """
    N, E = G.number_of_nodes(), G.number_of_edges()

    # ER
    # fast_gnp_random_graph is much faster when p is small (here p ~ 1e-4).
    p = E / (N * (N - 1) / 2)
    er = nx.fast_gnp_random_graph(n=N, p=p, seed=seed)

    # BA
    m = max(1, min(round(E / N), N - 1))
    ba = nx.barabasi_albert_graph(n=N, m=m, seed=seed)

    print(f"  ER:   N={er.number_of_nodes():,}, E={er.number_of_edges():,}, p={p:.2e}")
    print(f"  BA:   N={ba.number_of_nodes():,}, E={ba.number_of_edges():,}, m={m}")
    return er, ba



def average_curves(runs):
    """Point-wise mean/std across a list of percolation curves."""
    lcc = np.stack([r["lcc_fraction"].to_numpy() for r in runs])
    return pd.DataFrame({
        "fraction_removed": runs[0]["fraction_removed"].to_numpy(),
        "lcc_fraction": lcc.mean(axis=0),
        "lcc_std": lcc.std(axis=0),
    })


def threshold_row(network, model, strategy, values):
    """Build each row of the thresholds CSV """
    return {
        "network": network,
        "model": model,
        "strategy": strategy,
        "threshold_mean": float(np.nanmean(values)),
        "threshold_std": float(np.nanstd(values)),
        "n_runs": len(values),
        "collapse_level": COLLAPSE_LEVEL,
    }


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------
def main() -> None:
    networks = (
        {"AS Internet": NETWORK_FILES["AS Internet"]}
        if AS_ONLY else dict(NETWORK_FILES)
    )

    
    curve_rows: list[pd.DataFrame] = []
    threshold_rows: list[dict] = []

    for network_name, path in networks.items():
        print(f"\nLoading {network_name} from {path.name}")
        G = load_graph(path)
        print(f"  real: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

        er, ba = generate_reference_networks(G)

        # Same percolation suite on all three graphs (real, ER, BA).
        for model_name, H in [("real", G), ("ER", er), ("BA", ba)]:
            print(f"  Percolation on {network_name} / {model_name} ...")

            # random failure, 20 runs
            runs = [
                step2.random_percolation(H, seed=RANDOM_SEED + i, n_steps=N_STEPS)
                for i in range(N_RANDOM_RUNS)
            ]
            mean_curve = average_curves(runs)
            mean_curve[["network", "model", "strategy"]] = (
                network_name, model_name, "random failure"
            )
            curve_rows.append(mean_curve)
            threshold_rows.append(threshold_row(
                network_name, model_name, "random failure",
                [step2.empirical_threshold(r, COLLAPSE_LEVEL) for r in runs],
            ))

            # degree-targeted attack, one run
            targeted = step2.adaptive_degree_attack(H, n_steps=N_STEPS)
            targeted[["network", "model", "strategy", "lcc_std"]] = (
                network_name, model_name, "degree-targeted attack", 0.0
            )
            curve_rows.append(targeted)
            threshold_rows.append(threshold_row(
                network_name, model_name, "degree-targeted attack",
                [step2.empirical_threshold(targeted, COLLAPSE_LEVEL)],
            ))

    # Store outputs as CSV filess.
    curves = pd.concat(curve_rows, ignore_index=True)
    thresholds = pd.DataFrame(threshold_rows)
    curves.to_csv(DATA_DIR / "step3_percolation_curves.csv", index=False)
    thresholds.to_csv(DATA_DIR / "step3_percolation_thresholds.csv", index=False)

    #plots
    network_names = list(networks.keys())
    strategies = ["random failure", "degree-targeted attack"]
    colors = {"real": "C0", "ER": "C1", "BA": "C2"}

    fig, axes = plt.subplots(
        len(network_names), len(strategies),
        figsize=(5.5 * len(strategies), 4 * len(network_names)),
        sharey=True, squeeze=False,
    )

    for r, network_name in enumerate(network_names):
        for c, strategy in enumerate(strategies):
            ax = axes[r, c]
            for model_name, color in colors.items():
                sub = curves[
                    (curves["network"] == network_name)
                    & (curves["model"] == model_name)
                    & (curves["strategy"] == strategy)
                ].sort_values("fraction_removed")
                
                if sub.empty:
                    continue
                
                ax.plot(sub["fraction_removed"], sub["lcc_fraction"],
                        label=model_name, color=color)
                
                if strategy == "random failure":
                    std = sub["lcc_std"].fillna(0)
                    ax.fill_between(
                        sub["fraction_removed"],
                        sub["lcc_fraction"] - std,
                        sub["lcc_fraction"] + std,
                        color=color, alpha=0.2,
                    )
            ax.axhline(COLLAPSE_LEVEL, linestyle="--", linewidth=1, color="grey")
            ax.set_title(f"{network_name} - {strategy}")
            ax.set_xlabel("fraction of nodes removed")
            ax.grid(True, alpha=0.3)
        axes[r, 0].set_ylabel("largest component / original N")
    axes[0, -1].legend(frameon=False)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "fig3_percolation_curves.png", dpi=150)
    plt.show()

    print("\nSaved:")
    print(f"  {DATA_DIR / 'step3_percolation_curves.csv'}")
    print(f"  {DATA_DIR / 'step3_percolation_thresholds.csv'}")
    print(f"  {PLOTS_DIR / 'fig3_percolation_curves.png'}")
    print(f"\nEmpirical thresholds (LCC first <= {COLLAPSE_LEVEL} of N):")
    print(thresholds.to_string(index=False))


if __name__ == "__main__":
    main()
