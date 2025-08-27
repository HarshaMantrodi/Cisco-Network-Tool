import networkx as nx
import matplotlib.pyplot as plt

# Create a simple test network
G = nx.Graph()
G.add_edge("R1", "R2", bandwidth="1Gbps")
G.add_edge("R2", "R3", bandwidth="1Gbps")

# Draw the network
nx.draw(G, with_labels=True, node_color="lightblue", font_weight="bold")
plt.show()
