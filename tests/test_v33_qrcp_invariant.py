from task5v33.diagnostics import parse_qrcp_input_trace


def test_parse_qrcp_input_trace():
    parsed = parse_qrcp_input_trace(
        "noise\nQRCP_INPUT_TRACE m=256 n=128 lda=256 storage=column-major "
        "calls=258 query=129 execute=129 unique_hashes=1 jpvt_seed_zero=1 "
        "hashes=0123456789abcdef\n")
    assert parsed == {
        "m": 256, "n": 128, "lda": 256, "storage": "column-major",
        "calls": 258, "query": 129, "execute": 129,
        "unique_hashes": 1, "jpvt_seed_zero": 1,
        "hashes": ["0123456789abcdef"],
    }
