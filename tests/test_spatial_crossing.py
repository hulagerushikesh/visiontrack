from experiments.spatial_crossing import score_spatial_crossings


def event(frame, track_id, direction="right"):
    return {"frame": frame, "track_id": track_id, "direction": direction}


def score(predictions, references, tracks, episodes, window=1, stride=2):
    return score_spatial_crossings(
        predictions,
        references,
        tracks,
        episodes,
        frames_before=window,
        frames_after=window,
        stride=stride,
    )


def test_wrong_vehicle_is_replaced_with_same_frame_overlap():
    predicted = event(10, 1)
    nearest, actual = event(10, 2), event(11, 3)
    box = (0, 0, 10, 10)
    report = score(
        [predicted],
        [nearest, actual],
        {(10, 1): box},
        {(10, 2): (20, 0, 30, 10), (10, 3): box, (11, 3): (30, 0, 40, 10)},
    )
    assert [match["reference"] for match in report["matches"]] == [actual]
    assert report["missed_references"] == [nearest]


def test_missing_episode_box_is_distinct_from_zero_overlap():
    report = score(
        [event(10, 1)],
        [event(11, 2), event(10, 3)],
        {(10, 1): (0, 0, 10, 10)},
        {(11, 2): (0, 0, 10, 10), (10, 3): (20, 0, 30, 10)},
    )
    assert {row["reference"]["track_id"]: row["iou"] for row in report["candidate_audit"]} == {
        2: None,
        3: 0.0,
    }
    assert not report["matches"]


def test_assignment_prioritizes_cardinality_then_overlap():
    predictions = [event(10, 1), event(10, 2)]
    references = [event(10, 3), event(10, 4)]
    tracks = {(10, 1): (5, 0, 15, 10), (10, 2): (0, 0, 10, 10)}
    episodes = {(10, 3): (0, 0, 10, 10), (10, 4): (10, 0, 20, 10)}
    forward = score(predictions, references, tracks, episodes)
    reverse = score(predictions[::-1], references[::-1], tracks, episodes)
    assert forward == reverse
    assert [
        (match["predicted"]["track_id"], match["reference"]["track_id"])
        for match in forward["matches"]
    ] == [(1, 4), (2, 3)]

    # When both full assignments are feasible, select the better total IoU.
    tracks[10, 1] = (4, 0, 14, 10)
    tracks[10, 2] = (0, 0, 10, 10)
    episodes[10, 4] = (4, 0, 14, 10)
    report = score(predictions, references, tracks, episodes)
    assert [match["iou"] for match in report["matches"]] == [1, 1]


def test_late_crossing_remains_unmatched_and_competing_attributions_are_withheld():
    predicted, actual, opposite = event(12, 1), event(10, 2), event(12, 3, "left")
    box = (0, 0, 10, 10)
    tracks = {(12, 1): box}
    episodes = {(12, 2): box, (12, 3): box, (12, 4): box}
    report = score([predicted], [actual, opposite], tracks, episodes)
    assert report["matches"] == []
    assert report["unmatched_predictions"] == [predicted]
    assert report["missed_references"] == [actual, opposite]
    assert [row["frame_delta"] for row in report["offset_diagnostics"]] == [2]

    ambiguous = score([predicted], [actual, event(9, 4)], tracks, episodes)
    assert len(ambiguous["candidate_audit"]) == 2
    assert ambiguous["offset_diagnostics"] == []


def test_inclusive_window_and_iou_boundaries():
    report = score(
        [event(10, 1)],
        [event(9, 2)],
        {(10, 1): (0, 0, 10, 10)},
        {(10, 2): (0, 0, 3, 10)},
    )
    assert [row["iou"] for row in report["matches"]] == [0.30]


def test_empty_candidates_preserve_unmatched_events():
    assert score([event(10, 1)], [], {}, {})["unmatched_predictions"] == [event(10, 1)]
    assert score([], [event(10, 1)], {}, {})["missed_references"] == [event(10, 1)]
