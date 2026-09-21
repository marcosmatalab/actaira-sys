import sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "motor" / "src"))
CATALOGO = RAIZ / "catalogo"
