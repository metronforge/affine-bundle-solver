from task5v31.benchmark import geometric_mean


def test_geometric_mean_of_speedups():
    assert geometric_mean([1.0, 4.0, 9.0]) == 3.3019272488946263
