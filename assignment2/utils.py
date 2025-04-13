from collections import defaultdict


# Inspired by: https://github.com/joaquincabezas/networkx_pajek_util/blob/master/example_read_clu.ipynb

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
