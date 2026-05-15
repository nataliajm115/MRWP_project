import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import powerlaw
from pathlib import Path

# paths
INPUT_DIR = Path(__file__).parent / "datasets"
PLOTS_DIR = Path(__file__).parent / "results" / "plots"
OUTPUT_DATA_DIR = Path(__file__).parent / "results" / "data"

# Load data
G_as = nx.read_edgelist(INPUT_DIR / "oregon1_010331.txt",
                        nodetype=int, comments="#")
G_web = nx.read_edgelist(INPUT_DIR / "web-NotreDame.txt",
                         nodetype=int, comments="#")

print(f"AS:  {G_as.number_of_nodes()} nodes, {G_as.number_of_edges()} edges")
print(f"Web: {G_web.number_of_nodes()} nodes, {G_web.number_of_edges()} edges")


# Basic descriptors
def describe(G, name):
    n = G.number_of_nodes()
    m = G.number_of_edges()
    degrees = np.array([d for _, d in G.degree()])
    k_mean = degrees.mean()
    k2_mean = (degrees**2).mean()
    gcc = max(nx.connected_components(G), key=len)
    gcc_frac = len(gcc) / n

    print(f"\n{name}")
    print(f"  nodes: {n}")
    print(f"  edges: {m}")
    print(f"  <k>:   {k_mean:.3f}")
    print(f"  <k^2>: {k2_mean:.3f}")
    print(f"  <k^2>/<k>: {k2_mean/k_mean:.3f}")
    print(f"  giant component: {gcc_frac:.4f} of nodes")
    return degrees

deg_as = describe(G_as, "AS Internet")
deg_web = describe(G_web, "WWW Notre Dame")

# degree distribution plots
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for ax, deg, name in zip(axes, [deg_as, deg_web],
                          ["AS Internet", "WWW Notre Dame"]):
    values, counts = np.unique(deg, return_counts=True)
    ax.loglog(values, counts, 'o', markersize=3)
    ax.set_xlabel("degree k")
    ax.set_ylabel("count")
    ax.set_title(name)
plt.tight_layout()
plt.savefig(PLOTS_DIR / "fig1_degree_distributions.png", dpi=150)
plt.show()


# power-law fits
print("\nPower-law fits")
for deg, name in [(deg_as, "AS Internet"), (deg_web, "WWW Notre Dame")]:
    fit = powerlaw.Fit(deg, discrete=True, verbose=False)
    R, p = fit.distribution_compare('power_law', 'lognormal')
    print(f"{name}: alpha={fit.alpha:.3f}, xmin={fit.xmin:.1f}, "
          f"LR vs lognormal: R={R:.2f}, p={p:.3f}")