# cunit-to-junit

Convert [CUnit](http://cunit.sourceforge.net/) XML test reports to JUnit XML format.

## Installation

```bash
pip install cunit-to-junit
```

## Usage

### Command line

```bash
cunit-to-junit input.xml output.xml
```

Use `-v` / `--verbose` for debug logging.

### Python API

```python
from pathlib import Path
from cunit_to_junit import cunit_to_junit

cunit_to_junit(Path("cunit-results.xml"), Path("junit-results.xml"))
```

## License

AGPL-3.0 — see [LICENSE](LICENSE) for details.
