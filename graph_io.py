# graph_io.py
from pathlib import Path
import networkx as nx

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "datasets"

NETWORK_FILES = {
    "AS Internet": INPUT_DIR / "oregon1_010331.txt",
    "WWW Notre Dame": INPUT_DIR / "web-NotreDame.txt",
}


def load_graph(path: Path) -> nx.Graph:
    """Load a SNAP edge list as an undirected simple graph.

    Collapses parallel edges and removes self-loops so that every
    script in the project analyses exactly the same graph.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. Put the SNAP .txt file inside datasets/."
        )
    G = nx.read_edgelist(path, nodetype=int, comments="#")
    G = nx.Graph(G)                       # collapse parallel edges
    G.remove_edges_from(nx.selfloop_edges(G))
    return G