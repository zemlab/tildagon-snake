import re
import sys
from pathlib import Path

TOML_PATH = Path(__file__).parent.parent / "tildagon.toml"


def main():
    version = sys.argv[1]
    text = TOML_PATH.read_text()
    new_text, count = re.subn(
        r'(?m)^version\s*=\s*".*"$',
        f'version = "{version}"',
        text,
    )
    if count != 1:
        raise SystemExit(f"expected exactly one version line in {TOML_PATH}, found {count}")
    TOML_PATH.write_text(new_text)


if __name__ == "__main__":
    main()
