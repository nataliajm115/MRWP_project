"""
Step 2: Percolation on the two empirical networks.

Scope:
  - two node-removal strategies:
      1. random failure          - nodes removed in random order (stochastic);
      2. degree-targeted attack  - highest current-degree node removed each
                                   step (degree recalculated after every
                                   removal, following Holme et al. 2002);
  - one outcome variable: relative size of the largest connected component
    (largest component / original number of nodes);

Outputs:
  results/data/step2_percolation_curves.csv
  results/data/step2_percolation_thresholds.csv
  results/plots/fig2_percolation_curves.png
"""

from pathlib import Path
import heapq
import random

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from graph_io import load_graph, NETWORK_FILES

# Paths and settings
BASE_DIR = Path(__file__).resolve().parent
PLOTS_DIR = BASE_DIR / "results" / "plots"
OUTPUT_DATA_DIR = BASE_DIR / "results" / "data"

PLOTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)

# True  -> run AS only.
# False -> full run including the large Web graph.
AS_ONLY = False

N_RANDOM_RUNS = 20
RANDOM_SEED = 42

# Record the largest component at this many points along the removal axis.
N_STEPS = 100

# Empirical threshold: first fraction removed at which the largest component
# has fallen to or below this fraction of the original network size.
# The value is reported explicitly so the choice is transparent.
COLLAPSE_LEVEL = 0.05

# Helper functions
def largest_component_fraction(G: nx.Graph, original_n: int) -> float:
    """Size of the largest connected component / original number of nodes."""
    if G.number_of_nodes() == 0:
        return 0.0
    return len(max(nx.connected_components(G), key=len)) / original_n


def removal_checkpoints(n_nodes: int, n_steps: int) -> list[int]:
    """Removed-node counts at which we record the curve."""
    checkpoints = np.linspace(0, n_nodes, n_steps + 1, dtype=int)
    return sorted(set(checkpoints.tolist()))


def random_percolation(G: nx.Graph, seed: int, n_steps: int) -> pd.DataFrame:
    """Random node removal; record the largest-component curve."""
    rng = random.Random(seed)
    H = G.copy()
    original_n = H.number_of_nodes()
    nodes = list(H.nodes())
    rng.shuffle(nodes)

    checkpoints = removal_checkpoints(original_n, n_steps)
    rows = []
    removed = 0

    for target_removed in checkpoints:
        while removed < target_removed:
            H.remove_node(nodes[removed])
            removed += 1
        rows.append(
            {
                "fraction_removed": removed / original_n,
                "lcc_fraction": largest_component_fraction(H, original_n),
            }
        )
    return pd.DataFrame(rows)


def adaptive_degree_attack(G: nx.Graph, n_steps: int) -> pd.DataFrame:
    """
    Degree-targeted attack with recalculation after every removal. The highest current-degree node is removed each
    step. A lazy-update max-heap avoids re-sorting all nodes every removal.
    Ties between equal-degree nodes are broken by node id (heapq ordering)
    """
    H = G.copy()
    original_n = H.number_of_nodes()
    checkpoints = removal_checkpoints(original_n, n_steps)
    rows = []
    removed = 0

    heap = [(-deg, node) for node, deg in H.degree()]
    heapq.heapify(heap)

    for target_removed in checkpoints:
        while removed < target_removed:
            node = None
            while heap:
                neg_deg, candidate = heapq.heappop(heap)
                if candidate in H and -neg_deg == H.degree(candidate):
                    node = candidate
                    break
            if node is None:
                break  # graph empty

            neighbors = list(H.neighbors(node))
            H.remove_node(node)
            removed += 1
            for nb in neighbors:
                if nb in H:
                    heapq.heappush(heap, (-H.degree(nb), nb))

        rows.append(
            {
                "fraction_removed": removed / original_n,
                "lcc_fraction": largest_component_fraction(H, original_n),
            }
        )
    return pd.DataFrame(rows)


def empirical_threshold(curve: pd.DataFrame, level: float) -> float:
    """First removal fraction where the largest component <= level."""
    collapsed = curve[curve["lcc_fraction"] <= level]
    if collapsed.empty:
        return float("nan")
    return float(collapsed.iloc[0]["fraction_removed"])

# Main experiment
def main() -> None:
    networks = dict(NETWORK_FILES)
    if AS_ONLY:
        networks = {"AS Internet": NETWORK_FILES["AS Internet"]}
        print("AS_ONLY = True  (smoke test; set False for the full run)\n")

    all_curves = []
    all_thresholds = []

    for network_name, path in networks.items():
        print(f"Loading {network_name} from {path.name}")
        G = load_graph(path)
        print(f"  {G.number_of_nodes():,} nodes; {G.number_of_edges():,} edges")

        # random failure (stochastic: repeat and average)
        print(f"  Random failure x{N_RANDOM_RUNS} ...")
        random_curves = []
        for run in range(N_RANDOM_RUNS):
            c = random_percolation(G, seed=RANDOM_SEED + run, n_steps=N_STEPS)
            c["run"] = run
            random_curves.append(c)

        random_df = pd.concat(random_curves, ignore_index=True)
        random_mean = (
            random_df.groupby("fraction_removed")
            .agg(
                lcc_fraction=("lcc_fraction", "mean"),
                lcc_std=("lcc_fraction", "std"),
            )
            .reset_index()
        )
        random_mean["network"] = network_name
        random_mean["strategy"] = "random failure"
        all_curves.append(random_mean)

        rand_thr = [empirical_threshold(c, COLLAPSE_LEVEL) for c in random_curves]
        all_thresholds.append(
            {
                "network": network_name,
                "strategy": "random failure",
                "threshold_mean": np.nanmean(rand_thr),
                "threshold_std": np.nanstd(rand_thr),
                "n_runs": N_RANDOM_RUNS,
                "collapse_level": COLLAPSE_LEVEL,
            }
        )

        # degree-targeted attack
        print("Degree-targeted attack (recalculated) ...")
        targeted = adaptive_degree_attack(G, n_steps=N_STEPS)
        targeted["network"] = network_name
        targeted["strategy"] = "degree-targeted attack"
        targeted["lcc_std"] = 0.0
        all_curves.append(targeted)
        all_thresholds.append(
            {
                "network": network_name,
                "strategy": "degree-targeted attack",
                "threshold_mean": empirical_threshold(targeted, COLLAPSE_LEVEL),
                "threshold_std": 0.0,
                "n_runs": 1,
                "collapse_level": COLLAPSE_LEVEL,
            }
        )

    curves = pd.concat(all_curves, ignore_index=True)
    thresholds = pd.DataFrame(all_thresholds)

    curves.to_csv(OUTPUT_DATA_DIR / "step2_percolation_curves.csv", index=False)
    thresholds.to_csv(
        OUTPUT_DATA_DIR / "step2_percolation_thresholds.csv", index=False
    )

    # plot
    plotted = list(networks.keys())
    fig, axes = plt.subplots(
        1, len(plotted), figsize=(5.5 * len(plotted), 4),
        sharey=True, squeeze=False,
    )
    axes = axes[0]
    for ax, network_name in zip(axes, plotted):
        sub = curves[curves["network"] == network_name]
        for strategy, group in sub.groupby("strategy"):
            group = group.sort_values("fraction_removed")
            line, = ax.plot(
                group["fraction_removed"],
                group["lcc_fraction"],
                label=strategy,
            )
            if strategy == "random failure" and "lcc_std" in group:
                lo = group["lcc_fraction"] - group["lcc_std"].fillna(0)
                hi = group["lcc_fraction"] + group["lcc_std"].fillna(0)
                ax.fill_between(
                    group["fraction_removed"], lo, hi,
                    color=line.get_color(),
                    alpha=0.2,)
        ax.axhline(COLLAPSE_LEVEL, linestyle="--", linewidth=1,
                   label=f"collapse level = {COLLAPSE_LEVEL}")
        ax.set_title(network_name)
        ax.set_xlabel("fraction of nodes removed")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("largest connected component / original N")
    axes[-1].legend(frameon=False)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "fig2_percolation_curves.png", dpi=150)
    plt.show()

    print("\nSaved:")
    print(f"  {OUTPUT_DATA_DIR / 'step2_percolation_curves.csv'}")
    print(f"  {OUTPUT_DATA_DIR / 'step2_percolation_thresholds.csv'}")
    print(f"  {PLOTS_DIR / 'fig2_percolation_curves.png'}")
    print("\nEmpirical threshold summary "
          f"(largest component first <= {COLLAPSE_LEVEL} of N):")
    print(thresholds.to_string(index=False))


if __name__ == "__main__":
    main()