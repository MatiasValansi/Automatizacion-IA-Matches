"""
Configuración global de pytest.
Asegura que el path de la app esté disponible para imports.
"""

import sys
from pathlib import Path

# Agregar backend/ al path para que 'app.*' sea importable
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))