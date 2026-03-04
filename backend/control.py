# control.py
import threading
import time
import traceback
import socket
import sys
import pytz as _pytz
import datetime as _dt

from backend import config
from backend.database.dataframe_storage import get_storage
from pathlib import Path
from typing import Optional
import requests as _requests

_lock = threading.RLock()
_TZ_CL = _pytz.timezone('America/Santiago')

def _ts_cl():
    """Timestamp actual en hora de Santiago."""
    return _dt.datetime.now(_TZ_CL).strftime('%Y-%m-%d %H:%M:%S')

_server_thread: Optional[threading.Thread] = None
_server_obj = None
_status = {"state": "idle", "message": "", "last": None}
_logs = []
_max_logs = 2000


def _append_log(line: str):
    with _lock:
        for l in str(line).splitlines():
            ts = _ts_cl()
            entry = f"[{ts}] {l}"
            _logs.append(entry)
            if len(_logs) > _max_logs:
                del _logs[0: len(_logs) - _max_logs]


def get_logs(last: int = 500):
    with _lock:
        if last is None or last <= 0:
            return list(_logs)
        return _logs[-last:]

def _set_status(state: str, message: str = ""):
    with _lock:
        _status["state"] = state
        _status["message"] = message
        _status["last"] = time.time()
    try:
        # también registrar estados en el log
        _append_log(f"STATUS: {state} - {message}")
    except Exception:
        pass

def get_status():
    with _lock:
        return dict(_status)

def _uvicorn_runner():
    global _server_obj
    try:
        import uvicorn
        cfg = uvicorn.Config(
            "backend.main:app",
            host=config.BACKEND_HOST,
            port=int(config.BACKEND_PORT),
            log_level="info",
            reload=False,
        )
        _server_obj = uvicorn.Server(cfg)
        _server_obj.run()
    except Exception:
        _set_status("error", "uvicorn error: " + traceback.format_exc())

def start_backend():
    global _server_thread, _server_obj
    with _lock:
        if _server_thread and _server_thread.is_alive():
            return True
        _set_status("starting", "arrancando backend...")
        _server_thread = threading.Thread(target=_uvicorn_runner, daemon=True)
        _server_thread.start()
    # esperar disponibilidad
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            s = socket.create_connection((config.BACKEND_HOST, int(config.BACKEND_PORT)), timeout=1)
            s.close()
            _set_status("idle", "backend listo")
            return True
        except Exception:
            time.sleep(0.2)
    _set_status("error", "timeout al arrancar backend")
    return False

def stop_backend(timeout=10):
    global _server_obj, _server_thread
    with _lock:
        if not _server_thread or not _server_thread.is_alive():
            _set_status("idle", "backend no estaba corriendo")
            return True
        _set_status("stopping", "deteniendo backend...")
        try:
            if _server_obj:
                # pedir salida al server
                _server_obj.should_exit = True
        except Exception:
            pass
    # esperar a que thread termine
    start = time.time()
    while time.time() - start < timeout:
        if not _server_thread.is_alive():
            with _lock:
                _server_obj = None
                _server_thread = None
            _set_status("stopped", "backend detenido")
            return True
        time.sleep(0.2)
    _set_status("error", "timeout deteniendo backend")
    return False

def _do_sync(limit: int = 50, include_facebook=True, include_instagram=False):
    """Llama la API del backend para sincronizar todos los candidatos."""
    try:
        _set_status("running_sync", "obteniendo candidatos...")
        backend_url = config.BACKEND_URL

        # 1. Obtener lista de candidatos conectados
        resp = _requests.get(f"{backend_url}/api/candidatos", timeout=10)
        if not resp.ok:
            raise Exception(f"Error obteniendo candidatos: {resp.status_code} {resp.text}")

        candidatos = resp.json()
        if not candidatos:
            _set_status("finished", "No hay candidatos conectados para sincronizar")
            _append_log("No hay candidatos conectados.")
            return

        _append_log(f"Sincronizando {len(candidatos)} candidato(s)...")

        errores = []
        for i, candidato in enumerate(candidatos):
            cid = candidato.get("id")
            nombre = candidato.get("nombre", f"candidato {cid}")
            _set_status("running_sync", f"Sincronizando {nombre} ({i+1}/{len(candidatos)})...")
            _append_log(f"\n▶ Sincronizando {nombre}...")
            try:
                r = _requests.post(
                    f"{backend_url}/api/candidatos/{cid}/sincronizar",
                    params={
                        "limit": limit,
                        "sincronizar_facebook": include_facebook,
                        "sincronizar_instagram": include_instagram or include_facebook,
                    },
                    timeout=120,
                )
                if r.ok:
                    data = r.json()
                    _append_log(f"  ✓ {data.get('mensaje', 'OK')}")
                    if data.get("errores"):
                        for e in data["errores"]:
                            _append_log(f"  ⚠ {e}")
                else:
                    msg = f"Error {r.status_code}: {r.text[:200]}"
                    _append_log(f"  ✗ {msg}")
                    errores.append(f"{nombre}: {msg}")
            except Exception as exc:
                msg = str(exc)
                _append_log(f"  ✗ {msg}")
                errores.append(f"{nombre}: {msg}")

        if errores:
            _set_status("finished", f"Completado con {len(errores)} error(es)")
        else:
            _set_status("finished", "Sincronización completada")
        _append_log("\n✅ Sincronización completada")

    except Exception as e:
        _set_status("error", "sync error: " + str(e))
        _append_log("ERROR: " + str(e) + "\n" + traceback.format_exc())

def request_sync(password: str, limit: int = 50):
    """Public: iniciar sync en background si password coincide."""
    if not hasattr(config, "SYNC_PASSWORD") or not config.SYNC_PASSWORD:
        return {"ok": False, "msg": "SYNC_PASSWORD no está configurada"}
    if password != config.SYNC_PASSWORD:
        return {"ok": False, "msg": "Contraseña incorrecta"}

    def _worker():
        try:
            _do_sync(limit=limit)
        except Exception as e:
            _set_status("error", "sync error: " + str(e) + "\n" + traceback.format_exc())

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return {"ok": True, "msg": "Sync iniciado"}