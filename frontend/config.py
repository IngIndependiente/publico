"""Configuracion del frontend - importa desde backend/config.py para evitar duplicacion."""
import os
import sys

# Asegurar que el directorio raiz esta en el path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Re-exportar toda la configuracion desde backend.config
from backend.config import *  # noqa: F401,F403