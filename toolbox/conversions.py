import torch
import dgl
import numpy as np
from toolbox.utils import is_adj

def sparsify_adjacency(adjacency, sparsify, distances):
    assert is_adj(adjacency), "Matrix is not an adjacency matrix"
    assert isinstance(sparsify,int), f"Sparsify not recognized. Should be int (number of closest neighbors), got {sparsify=}"
    assert distances.shape == adjacency.shape, f"Distances of different shape than adjacency {distances.shape}!={adjacency.shape}"
    N,_ = adjacency.shape
    mask = torch.zeros_like(adjacency)
    if isinstance(distances, torch.Tensor): distances = distances.numpy()
    knns = np.argpartition(distances, kth=sparsify, axis=-1)[:, sparsify ::-1].copy()
    range_tensor = torch.tensor(range(N)).unsqueeze(-1)
    mask[range_tensor,knns] = 1
    mask = mask*(1-torch.eye(N)) #Remove the self value
    return adjacency*mask

def _adjacency_to_dgl(adj):
    assert is_adj(adj), "Matrix is not an adjacency matrix"
    N,_ = adj.shape
    mgrid = np.mgrid[:N,:N].transpose(1,2,0)
    edges = mgrid[torch.where(adj==1)]
    edges = edges.T #To have the shape (2,n_edges)
    src,dst = [elt for elt in edges[0]], [elt for elt in edges[1]] #DGLGraphs don't like Tensors as inputs...
    gdgl = dgl.graph((src,dst),num_nodes=N)
    return gdgl

def dense_tensor_to_edge_format(dense_tensor: torch.Tensor, dgl_graph: dgl.graph):
    assert dense_tensor.dim()==2 and dense_tensor.shape[0]==dense_tensor.shape[1], f"Dense Tensor isn't of shape (N,N)"
    N,_ = dense_tensor.shape
    src,rst = dgl_graph.edges()
    edge_tensor = dense_tensor[src,rst]
    return edge_tensor.unsqueeze(-1)

def edge_format_to_dense_tensor(edge_features: torch.Tensor, graph: dgl.graph):
    N = graph.num_nodes()
    if edge_features.dim()==1:
        N_edges = len(edge_features)
        dense_tensor = torch.zeros((N,N))
    else:
        N_edges, N_feats = edge_features.shape
        dense_tensor = torch.zeros((N,N,N_feats))
    dense_tensor = dense_tensor.type_as(edge_features)
    src, dst = graph.edges()
    assert len(src)==N_edges, f'edge_features tensor does not correspond to this graph (not the same number of edges: {len(src)} and {N_edges})'
    dense_tensor[src,dst] = edge_features
    return dense_tensor

def connectivity_to_dgl(connectivity_graph, sparsify=None, distances = None):
    assert connectivity_graph.dim()==3, "Tensor dimension not recognized. Should be (N_nodes, N_nodes, N_features)"
    N, _, N_feats = connectivity_graph.shape
    degrees = connectivity_graph[:,:,0]
    assert torch.all(degrees*(1-torch.eye(N))==0) and not torch.any(degrees.diag() != degrees.diag().to(int)), "Tensor first feature isn't degree. Not recognized."
    if N_feats == 2:
        edge_features = connectivity_graph[:,:,1]
        adjacency = (edge_features!=0).to(torch.float)
        if not sparsify in (None,0):
            if distances is None:
                distances = edge_features
            adjacency = sparsify_adjacency(adjacency, sparsify, distances)
        gdgl = _adjacency_to_dgl(adjacency)
        gdgl.ndata['feat'] = degrees.diagonal().reshape((N,1)) #Adding degrees to node features
        if not is_adj(edge_features):
            #src,rst = gdgl.edges() #For now only contains node features
            #efeats = edge_features[src,rst]
            efeats = dense_tensor_to_edge_format(edge_features, gdgl)
            gdgl.edata["feat"] = efeats
    else:
        raise NotImplementedError("Haven't implemented the function for more Features than one per edge (problem is how to check for the adjacency matrix).")
    return gdgl

def adjacency_matrix_to_tensor_representation(W):
    """ Create a tensor B[:,:,1] = W and B[i,i,0] = deg(i)"""
    degrees = W.sum(1)
    B = torch.zeros((len(W), len(W), 2))
    B[:, :, 1] = W
    indices = torch.arange(len(W))
    B[indices, indices, 0] = degrees
    return B

def dgl_dense_adjacency(graph: dgl.graph):
    N = graph.num_nodes()
    dense_adj = torch.zeros((N,N))
    src, dst = graph.edges()
    dense_adj[src,dst] = 1
    return dense_adj