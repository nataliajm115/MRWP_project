import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import powerlaw

# Load data
G_as = nx.read_edgelist("datasets/oregon1_010331.txt",
                        nodetype=int, comments="#")
G_web = nx.read_edgelist("datasets/web-NotreDame.txt",
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