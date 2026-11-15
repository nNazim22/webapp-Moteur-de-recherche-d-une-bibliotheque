import numpy as np

from app.jaccard_graph import build_graph, centralities, filter_vocabulary, jaccard_matrix


def test_filter_vocabulary_keeps_shared_terms_on_small_corpus():
    # Chaque livre est représenté par des identifiants de termes triés.
    cols, n_terms = filter_vocabulary(
        [np.array([1, 2, 3]), np.array([1, 2, 4]), np.array([1, 5])],
        df_min=2,
        df_max_ratio=0.5,
    )
    assert n_terms == 1
    assert [len(col) for col in cols] == [1, 1, 0]


def test_jaccard_graph_and_centralities_are_computed():
    # Ensembles {a,b}, {a,c}, {x}; le premier et le deuxième sont similaires.
    cols = [np.array([0, 1]), np.array([0, 2]), np.array([3])]
    matrix = jaccard_matrix(cols, 4)
    assert np.isclose(matrix[0, 1], 1 / 3)
    graph = build_graph([10, 20, 30], matrix, k=1)
    assert graph.has_edge(10, 20)
    assert graph[10][20]["dist"] > 0
    scores = centralities(graph, with_betweenness=True)
    assert set(scores) == {"pagerank", "closeness", "degree", "betweenness"}
    assert set(scores["pagerank"]) == {10, 20, 30}
