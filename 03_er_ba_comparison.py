"""
Step 3 - Compare the empirical networks with matched null models.

For each real network (AS Internet, WWW Notre Dame) we build three 
synthetic graphs:
  - Erdos-Renyi (ER):     same N, and edge probability p = E / C(N, 2);
  - Barabasi-Albert (BA): same N, and parameter m = round(E / N);
  - Configuration model (CM): same degree sequence as the real graph

On each of (real, ER, BA, CM) we then run the same two percolation
experiments used in step 2:
  - random failure         (averaged over N_RANDOM_RUNS independent seeds)
  - degree-targeted attack (single deterministic run, adaptive)
and record the LCC-fraction curve and the empirical collapse threshold.

We also produce a degree-distribution figure (real/ER/BA/CM overlaid, one
panel per real network) and a small comparison table with basic structural
metrics (N, E, <k>, <k^2>, <k^2>/<k>, average clustering, giant-component
fraction, density).

Outputs:
  results/data/step3_percolation_curves.csv
  results/data/step3_percolation_thresholds.csv
  results/data/step3_network_comparison.csv
  results/plots/fig3_percolation_curves.png
  results/plots/fig3_degree_distributions.png
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

# Color palette and linestyle, used by both percolation and degree-distribution plots.
MODEL_COLORS = {
    "real": "#648FFF",  # bright blue
    "ER":   "#DC267F",  # magenta
    "BA":   "#FFB000",  # gold
    "CM":   "#785EF0",  # purple
}
MODEL_LINESTYLES = {
    "real": "-",
    "ER":   "--",
    "BA":   ":",
    "CM":   "-.",
}
MODEL_MARKERS = {
    "real": "o",
    "ER":   "s",
    "BA":   "^",
    "CM":   "D",
}


# ---------------------------------------------------------------------------
# Reference networks and two helpers
# ---------------------------------------------------------------------------
def generate_reference_networks(G, seed = RANDOM_SEED):
    """Return ER and BA graphs matched to G in size and density.
    ER: same N, matched edges.
    BA: same N, matched <k>
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


def generate_configuration_model(G, seed=RANDOM_SEED):
    """Return a configuration-model graph with the same degree sequence as G."""
    degrees = [d for _, d in G.degree()]
    cm = nx.configuration_model(degrees, seed=seed)
    # This matches the degree sequence, yet it returns a random pseudograph. which can have
    # - parallel edges,
    # - self-loops.
    # Thus, need to remove them.
    cm = nx.Graph(cm)                      
    cm.remove_edges_from(nx.selfloop_edges(cm))
    print(f"  CM:   N={cm.number_of_nodes():,}, E={cm.number_of_edges():,} "
          f"(degree sequence matched; parallel/self-loops removed)")
    return cm


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
# Structural comparison: degree distributions and basic metrics
# ---------------------------------------------------------------------------
def network_summary(graphs):
    """One row per (network, model) graph with basic structural metrics.

    Metrics:
      nodes, edges          - N and E
      <k>, <k^2>            - first and second moments of the degree distribution
      <k^2>/<k>             - Molloy-Reed-like heterogeneity ratio
                              (large -> robust to random failure)
      avg_clustering        - global average local clustering coefficient
      giant_component_frac  - fraction of nodes in the largest component
      density               - 2E / (N*(N-1))
    """
    rows = []
    for (network_name, model_name), G in graphs.items():
        print(f"  metrics for {network_name} / {model_name} ...")
        N = G.number_of_nodes()
        E = G.number_of_edges()
        degrees = np.array([d for _, d in G.degree()])
        k_mean = float(degrees.mean())
        k2_mean = float((degrees ** 2).mean())
        gcc = max(nx.connected_components(G), key=len)
        rows.append({
            "network": network_name,
            "model": model_name,
            "nodes": N,
            "edges": E,
            "<k>": round(k_mean, 3),
            "<k^2>": round(k2_mean, 3),
            "<k^2>/<k>": round(k2_mean / k_mean, 3) if k_mean else 0.0,
            "avg_clustering": round(nx.average_clustering(G), 4),
            "giant_component_frac": round(len(gcc) / N, 4),
            "density": round(2 * E / (N * (N - 1)), 6),
        })
    return pd.DataFrame(rows)


def degree_distribution_figure(graphs, save_path):
    """Log-log degree distribution per real network with real/ER/BA/CM overlaid."""
    network_names = sorted({n for n, _ in graphs})
    fig, axes = plt.subplots(
        1, len(network_names),
        figsize=(6 * len(network_names), 5),
        squeeze=False,
    )
    axes = axes[0]

    for ax, network_name in zip(axes, network_names):
        for model_name in MODEL_COLORS:
            G = graphs.get((network_name, model_name))
            if G is None:
                continue
            degrees = np.array([d for _, d in G.degree()])
            values, counts = np.unique(degrees, return_counts=True)
            ax.loglog(
                values, counts / G.number_of_nodes(),
                marker=MODEL_MARKERS[model_name],
                linestyle="None",
                color=MODEL_COLORS[model_name],
                alpha=0.7, label=model_name,
            )
        ax.set_title(network_name)
        ax.set_xlabel("degree k")
        ax.set_ylabel("P(k)")
        ax.grid(True, which="both", ls="--", alpha=0.3)
        ax.legend()

    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.show()


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
    graphs: dict[tuple[str, str], nx.Graph] = {}

    for network_name, path in networks.items():
        print(f"\nLoading {network_name} from {path.name}")
        G = load_graph(path)
        print(f"  real: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

        er, ba = generate_reference_networks(G)
        cm = generate_configuration_model(G)

        # Same percolation suite on all four graphs (real, ER, BA, CM).
        for model_name, H in [("real", G), ("ER", er), ("BA", ba), ("CM", cm)]:
            graphs[(network_name, model_name)] = H
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

    # Percolation curves plots
    network_names = list(networks.keys())
    strategies = ["random failure", "degree-targeted attack"]

    fig, axes = plt.subplots(
        len(network_names), len(strategies),
        figsize=(5.5 * len(strategies), 4 * len(network_names)),
        sharey=True, squeeze=False,
    )

    for r, network_name in enumerate(network_names):
        for c, strategy in enumerate(strategies):
            ax = axes[r, c]
            for model_name, color in MODEL_COLORS.items():
                sub = curves[
                    (curves["network"] == network_name)
                    & (curves["model"] == model_name)
                    & (curves["strategy"] == strategy)
                ].sort_values("fraction_removed")

                if sub.empty:
                    continue

                ax.plot(
                    sub["fraction_removed"], sub["lcc_fraction"],
                    label=model_name, color=color,
                    linestyle=MODEL_LINESTYLES[model_name], linewidth=2,
                )

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

    # Structural comparison
    print("\nComputing structural metrics (clustering may take a minute on WWW) ...")
    summary = network_summary(graphs)
    summary.to_csv(DATA_DIR / "step3_network_comparison.csv", index=False)
    degree_distribution_figure(
        graphs, PLOTS_DIR / "fig3_degree_distributions.png"
    )

    print("\nSaved:")
    print(f"  {DATA_DIR / 'step3_percolation_curves.csv'}")
    print(f"  {DATA_DIR / 'step3_percolation_thresholds.csv'}")
    print(f"  {DATA_DIR / 'step3_network_comparison.csv'}")
    print(f"  {PLOTS_DIR / 'fig3_percolation_curves.png'}")
    print(f"  {PLOTS_DIR / 'fig3_degree_distributions.png'}")
    print(f"\nEmpirical thresholds (LCC first <= {COLLAPSE_LEVEL} of N):")
    print(thresholds.to_string(index=False))
    print("\nNetwork comparison:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
