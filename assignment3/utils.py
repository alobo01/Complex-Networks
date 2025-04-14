from collections import defaultdict
from collections import defaultdict, Counter
from math import log
from networkx.algorithms.community.quality import modularity
from sklearn.metrics import normalized_mutual_info_score
import os
import shutil

# Parsing pajek inspired by: https://github.com/joaquincabezas/networkx_pajek_util/blob/master/example_read_clu.ipynb

def parse_pajek_communities(lines):
    """Parse Pajek format partition from iterable of lines.

    Parameters
    ----------
    lines : iterable of str
        Lines from a Pajek .clu file.

    Returns
    -------
    list of lists
        Communities as lists of vertex indices.
    """
    if isinstance(lines, str):
        lines = iter(lines.split('\n'))
    lines = iter([line.rstrip('\n') for line in lines])

    communities = defaultdict(list)
    while True:
        try:
            l = next(lines)
        except StopIteration:
            break
        if l.lower().startswith("*vertices"):
            _, nnodes = l.split()
            for vertex in range(int(nnodes)):
                l = next(lines)
                community = int(l)
                communities[community].append(vertex)
        else:
            break

    return list(communities.values())

def read_pajek_communities(path, encoding='UTF-8'):
    """Read communities in Pajek format (.clu) from path.

    Parameters
    ----------
    path : str
        File path to the .clu file.
    encoding : str
        Encoding used to decode the file.

    Returns
    -------
    list of lists
        Each inner list contains node indices in the same community.
    """
    with open(path, mode='rb') as f:
        lines = (line.decode(encoding) for line in f)
        return parse_pajek_communities(lines)

def generate_pajek_communities(communities):
    """Generate lines in Pajek .clu format.

    Parameters
    ----------
    communities : list of lists
        Communities as lists of vertex indices.

    Yields
    ------
    str
        Lines of the .clu file.
    """
    communities_list = [list(c) for c in communities]
    nnodes = sum(len(c) for c in communities_list)
    yield f"*Vertices {nnodes}"

    for _ in range(nnodes):
        vertex = min(min(c) for c in communities_list if c)
        community = next(i for i, c in enumerate(communities_list) if vertex in c)
        yield f"{community + 1}"
        communities_list[community].remove(vertex)

def write_pajek_communities(communities, path, encoding='UTF-8'):
    """Write partition in Pajek format (.clu) to path.

    Parameters
    ----------
    communities : list of lists
        Communities with vertex indices.
    path : str
        File path to write to.
    encoding : str
        Encoding used to encode the file.
    """
    with open(path, mode='wb') as f:
        for line in generate_pajek_communities(communities):
            f.write((line + '\r\n').encode(encoding))


def infomap_to_networkx_communities(mapping,infomap_partition):
    community_dict = defaultdict(set)
    for node, community in infomap_partition.items():
        community_dict[community].add(mapping[node])
    
    return list(community_dict.values())



def partition_to_labels(partition):
    """
    Convert a partition (list of sets) into a dictionary mapping each node to its community id.
    """
    labels = {}
    for label, community in enumerate(partition):
        for node in community:
            labels[node] = label
    return labels

def compute_entropy(labels):
    counts = Counter(labels)
    total = len(labels)
    return -sum((count/total) * log(count/total) for count in counts.values() if count/total > 0)

def compute_mutual_information(y_true, y_pred):
    total = len(y_true)
    counter_true = Counter(y_true)
    counter_pred = Counter(y_pred)
    joint_counts = Counter(zip(y_true, y_pred))
    mi = 0.0
    for (t, p), joint in joint_counts.items():
        p_tp = joint / total
        p_t = counter_true[t] / total
        p_p = counter_pred[p] / total
        mi += p_tp * log(p_tp / (p_t * p_p))
    return mi

def normalized_variation_of_information(y_true, y_pred):
    """
    Compute the Variation of Information (VI) and then normalize it.
    VI = H(true) + H(pred) - 2I(true, pred). The normalized VI is obtained by dividing by log(n)
    where n is the number of nodes.
    """
    H_true = compute_entropy(y_true)
    H_pred = compute_entropy(y_pred)
    I = compute_mutual_information(y_true, y_pred)
    VI = H_true + H_pred - 2 * I
    normalization = log(len(y_true))
    return VI / normalization if normalization != 0 else VI

def jaccard_index_partition(y_true, y_pred):
    """
    Compute a pair-count based Jaccard Index for two partitions.
    For all pairs of nodes, count a pair if the nodes are in the same community in one or both 
    partitions, and count an agreement if they are together in both.
    """
    n = len(y_true)
    agree = 0  # pairs that are in the same community in both partitions
    union = 0  # pairs that are in the same community in at least one partition
    for i in range(n):
        for j in range(i + 1, n):
            same_true = (y_true[i] == y_true[j])
            same_pred = (y_pred[i] == y_pred[j])
            if same_true or same_pred:
                union += 1
            if same_true and same_pred:
                agree += 1
    return agree / union if union != 0 else 0

def evaluate_partition(golden_partition, algorithm_partition, G, prr):
    """
    Evaluate a community partition against the golden standard.
    
    Arguments:
        golden_partition: List[Set] representing the true communities.
        algorithm_partition: List[Set] representing communities found by an algorithm.
        G: networkx graph for computing modularity.
        prr: A parameter (e.g., node removal probability) to track the evolution.
    
    Returns:
        dict: A dictionary containing:
            - 'prr': given prr value.
            - 'num_communities': number of communities in the algorithm partition.
            - 'modularity': modularity of the algorithm partition.
            - 'normalized_mutual_information': NMI between golden and algorithm partitions.
            - 'normalized_variation_of_information': normalized VI between partitions.
            - 'jaccard_index': Jaccard index for the partitions (pair-based).
    """
    metrics = {}
    metrics['prr'] = prr
    metrics['num_communities'] = len(algorithm_partition)
    
    # Compute modularity using networkx
    metrics['modularity'] = modularity(G, algorithm_partition)
    
    # Convert partitions to label assignments
    alg_labels_dict = partition_to_labels(algorithm_partition)
    golden_labels_dict = partition_to_labels(golden_partition)
    
    # Ensure both partitions cover the same set of nodes;
    # here we assume that golden_partition contains all nodes.
    common_nodes = list(golden_labels_dict.keys())
    
    y_true = [golden_labels_dict[node] for node in common_nodes]
    y_pred = [alg_labels_dict[node] for node in common_nodes]
    
    # Compute Normalized Mutual Information (using arithmetic normalization)
    metrics['normalized_mutual_information'] = normalized_mutual_info_score(
        y_true, y_pred, average_method='arithmetic'
    )
    
    # Compute Normalized Variation of Information
    metrics['normalized_variation_of_information'] = normalized_variation_of_information(y_true, y_pred)
    
    # Compute Jaccard Index for community partitions
    metrics['jaccard_index'] = jaccard_index_partition(y_true, y_pred)
    
    return metrics


def move_files_to_sbm_folder():
    """
    Move all Pajek files (.net and .clu) created by analyze_specific_prr_values
    to a subfolder named 'SBM'.
    """
    # Create SBM folder if it doesn't exist
    if not os.path.exists('SBM'):
        os.makedirs('SBM')
        print("Created SBM folder")
    
    # Find all .net and .clu files in the current directory
    pajek_files = []
    for file in os.listdir('.'):
        if file.endswith('.net') or file.endswith('.clu'):
            pajek_files.append(file)
    
    # Move files to SBM folder
    moved_count = 0
    for file in pajek_files:
        source = file
        destination = os.path.join('SBM', file)
        try:
            shutil.move(source, destination)
            moved_count += 1
            print(f"Moved: {file} → SBM/{file}")
        except Exception as e:
            print(f"Error moving {file}: {e}")
    
    print(f"\nMoved {moved_count} files to the SBM folder")

move_files_to_sbm_folder()
