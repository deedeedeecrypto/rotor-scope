"""The safety property this project sells: it cannot write to Sera."""
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "rotor_scope"
FORBIDDEN = [r"\.post\(", r"\.put\(", r"\.delete\(", r"\.patch\(",
             "private_key", "PRIVATE_KEY", "eth_account", "sign_message", "sign_typed"]


def test_no_write_paths():
    import re
    offenders = []
    for f in SRC.glob("*.py"):
        text = f.read_text()
        for pat in FORBIDDEN:
            if re.search(pat, text):
                offenders.append(f"{f.name}: {pat}")
    assert not offenders, f"rotor-scope must stay read-only: {offenders}"
