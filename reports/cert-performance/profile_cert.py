"""Add timing scopes to a disposable source worktree, then use experiment.py --worker --trace."""
import importlib.util
from pathlib import Path
import sys

here=Path(__file__).resolve().parent
prior=here.parent/"ralph-30"
sys.path.insert(0,str(prior))
spec=importlib.util.spec_from_file_location("scopes",prior/"profile.py")
scopes=importlib.util.module_from_spec(spec)
spec.loader.exec_module(scopes)
scopes.FUNCTIONS={
    "certified_api.c":["bs_certify_candidate","run_unique_and_infinite_profiles",
        "run_inconsistent_profile","unique_witness_prepare","select_rows_qrcp",
        "right_null_vector_qrcp","smallest_right_vector_dgesdd","normalize_augmented_rows",
        "least_squares_x","left_null_qrcp_init","left_null_qrcp_projection"],
    "status_certificate.c":["bs_verify_unique","bs_verify_infinite","bs_verify_inconsistent"],
}
scopes.instrument(Path(sys.argv[1]))
