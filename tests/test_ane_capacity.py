def test_capacity_percentile():
    from benchmarks.quality.ane_capacity import percentile

    assert percentile([1, 2, 3], 0.5) == 2.0
    assert percentile([1, 3], 0.5) == 2.0
