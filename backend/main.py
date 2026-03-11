"""API Backend con FastAPI."""
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response, BackgroundTasks, Header
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
import pandas as pd
from datetime import datetime
import json
import secrets

import json
import os
import sys

from backend import config
from backend.database.storage import get_db, init_db, PersonaService, ConversacionService, AnalisisService, EventoService, USE_DATAFRAMES, get_db_session
from backend.database.candidato_services import CandidatoService

# Importar agente con manejo de errores
try:
    from backend.agent.langgraph_agent import procesar_conversacion
    AGENTE_DISPONIBLE = True
except Exception as e:
    print(f"[ADVERTENCIA] No se pudo inicializar el agente: {e}")
    AGENTE_DISPONIBLE = False
    procesar_conversacion = None

from backend.integrations.meta_api import meta_client, crear_cliente_candidato
from backend.integrations.whatsapp_api import whatsapp_client
import requests
from urllib.parse import urlencode

# Imports condicionales para SQLAlchemy
if not USE_DATAFRAMES:
    from backend.database.models import Persona, Interes, Conversacion, Analisis, Evento

# Inicializar la base de datos
init_db()

# Crear la aplicación FastAPI
app = FastAPI(
    title="Agente Político API",
    description="API para el sistema de análisis de conversaciones políticas",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Modelos Pydantic ===

class MensajeCreate(BaseModel):
    """Modelo para crear un mensaje."""
    mensaje: str
    plataforma: str
    facebook_id: Optional[str] = None
    instagram_id: Optional[str] = None


class ReplyRequest(BaseModel):
    """Modelo para enviar una respuesta manual desde el dashboard."""
    texto: str


class PersonaResponse(BaseModel):
    """Modelo de respuesta para una sesión/persona."""
    id: int  # ID de la persona
    analisis_id: Optional[int]  # ID del análisis (sesión)
    nombre_completo: Optional[str]
    edad: Optional[int]
    genero: Optional[str]
    telefono: Optional[str]
    email: Optional[str]
    ocupacion: Optional[str]
    ubicacion: Optional[str]
    facebook_username: Optional[str]
    instagram_username: Optional[str]
    intereses: List[str]
    resumen_conversacion: Optional[str]
    fecha_primer_contacto: datetime
    fecha_ultimo_contacto: datetime
    evento_id: Optional[int] = None
    evento_nombre: Optional[str] = None
    
    class Config:
        from_attributes = True


class BusquedaRequest(BaseModel):
    """Modelo para búsqueda de personas."""
    genero: Optional[str] = None
    edad_min: Optional[int] = None
    edad_max: Optional[int] = None
    intereses: Optional[List[str]] = None
    ubicacion: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    facebook_user_id: Optional[str] = None
    page: int = 0
    page_size: int = 50


# === Modelos Pydantic para Admin Usuarios ===

class UsuarioCreate(BaseModel):
    """Modelo para crear usuario autorizado."""
    email: EmailStr
    nombre: str
    rol: str = "candidato"  # candidato, admin, equipo


class UsuarioUpdate(BaseModel):
    """Modelo para actualizar usuario autorizado."""
    nombre: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[int] = None


class UsuarioResponse(BaseModel):
    """Modelo de respuesta para usuario autorizado."""
    id: int
    email: str
    nombre: str
    rol: str
    activo: int
    fecha_registro: datetime
    ultimo_acceso: Optional[datetime]
    
    class Config:
        from_attributes = True


# === Configuración y Middleware de Admin ===

# Token de autenticación para endpoints de admin (configurar en variable de entorno)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "cambiar-este-token-en-produccion-urgente")


def get_admin_db():
    """
    Dependency para obtener sesión de BD para endpoints de admin.
    Siempre usa SQLAlchemy (SessionLocal), incluso si el sistema está en modo DataFrame.
    La tabla de usuarios autorizados siempre usa SQLAlchemy.
    """
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verificar_admin_token(authorization: str = Header(None)):
    """Middleware para verificar token de administrador."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autorización requerido")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato de token inválido. Use: Bearer <token>")
    
    token = authorization.replace("Bearer ", "")
    
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Token inválido")
    
    return True


# === Endpoints ===

@app.get("/")
def root():
    """Endpoint raíz."""
    return {
        "message": "Agente Político API",
        "version": "1.0.1",
        "endpoints": {
            "personas": "/api/personas",
            "buscar": "/api/personas/buscar",
            "procesar": "/api/mensajes/procesar",
            "exportar": "/api/personas/exportar",
            "intereses": "/api/intereses",
            "auth_facebook": "/auth/facebook/login",
            "candidatos": "/api/candidatos",
            "admin_usuarios": "/admin/usuarios",
            "docs": "/docs"
        }
    }


# === Facebook Login for Business (OAuth 2.0) ===

@app.get("/auth/facebook/login")
async def facebook_login(candidato_email: Optional[str] = Query(None)):
    """
    Iniciar flujo de Facebook Login for Business.
    
    Query Params:
        candidato_email: Email del candidato que está conectando su página
    """
    if not config.META_APP_ID:
        raise HTTPException(status_code=500, detail="META_APP_ID no configurado")
    
    # Scopes necesarios para multi-tenant
    # NOTE: business_management is intentionally excluded from the OAuth scope.
    # Including unapproved advanced permissions can silently suppress other permissions
    # (like pages_show_list) in Live mode. The tasks field is still requested at the
    # API call level; if business_management hasn't been granted, the field is simply omitted.
    scopes = [
        "pages_show_list",
        "pages_messaging",
        "pages_read_engagement",
        "instagram_basic",
        "instagram_manage_messages"
    ]
    
    # Estado (puede incluir el email del candidato)
    state = candidato_email if candidato_email else "default"
    
    # URL de autorización de Facebook
    # enable_profile_selector: forces the page-picker to appear so the user must
    #   explicitly select which Pages to share (prevents empty /me/accounts).
    # auth_type=rerequest: forces Facebook to show the full dialog even if the user
    #   has previously authorized the app, ensuring stale grants are refreshed.
    auth_url = "https://www.facebook.com/v18.0/dialog/oauth?" + urlencode({
        "client_id": config.META_APP_ID,
        "redirect_uri": config.OAUTH_REDIRECT_URI,
        "state": state,
        "scope": ",".join(scopes),
        "response_type": "code",
        "enable_profile_selector": "true",
        "auth_type": "rerequest"
    })
    
    # Redirigir al usuario a Facebook
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=auth_url)


@app.get("/auth/facebook/callback")
async def facebook_callback(
    code: str = Query(...),
    state: str = Query(None),
    db: Session = Depends(get_db_session)
):
    """
    Callback de Facebook OAuth.
    Recibe el código de autorización, obtiene todas las páginas y retorna para selección.
    VALIDACIÓN DE ACCESO: Solo usuarios en lista blanca pueden continuar.
    """
    if not config.META_APP_ID or not config.META_APP_SECRET:
        raise HTTPException(status_code=500, detail="META_APP_ID o META_APP_SECRET no configurados")
    
    try:
        # 1. Intercambiar código por access token
        token_url = "https://graph.facebook.com/v18.0/oauth/access_token?" + urlencode({
            "client_id": config.META_APP_ID,
            "client_secret": config.META_APP_SECRET,
            "redirect_uri": config.OAUTH_REDIRECT_URI,
            "code": code
        })
        
        token_response = requests.get(token_url)
        token_response.raise_for_status()
        token_data = token_response.json()
        
        user_access_token = token_data['access_token']
        
        # 2. OBTENER EMAIL DEL USUARIO DE FACEBOOK
        user_url = f"https://graph.facebook.com/v18.0/me?access_token={user_access_token}&fields=id,name,email"
        user_response = requests.get(user_url)
        user_response.raise_for_status()
        user_data = user_response.json()
        
        user_email = user_data.get('email')
        user_name = user_data.get('name')
        
        # 3. VALIDAR SI USUARIO ESTÁ AUTORIZADO (LISTA BLANCA)
        # Solo si config.VALIDAR_USUARIOS está activado (producción)
        if config.VALIDAR_USUARIOS:
            from backend.database.models import UsuarioAutorizado
            
            # Verificar si el email está en la lista de usuarios autorizados
            usuario_autorizado = db.query(UsuarioAutorizado).filter(
                UsuarioAutorizado.email == user_email,
                UsuarioAutorizado.activo == 1
            ).first()
            
            if not usuario_autorizado:
                # Usuario NO autorizado - Mostrar mensaje de acceso denegado
                from fastapi.responses import HTMLResponse
                html_denegado = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Acceso No Autorizado</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                        }}
                        .container {{
                            text-align: center;
                            padding: 60px 40px;
                            background: rgba(255,255,255,0.15);
                            border-radius: 20px;
                            backdrop-filter: blur(10px);
                        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                        max-width: 500px;
                    }}
                    .icon {{
                        font-size: 80px;
                        margin-bottom: 20px;
                    }}
                    h1 {{
                        margin: 0 0 20px 0;
                        font-size: 32px;
                    }}
                    p {{
                        font-size: 18px;
                        line-height: 1.6;
                        margin: 15px 0;
                        opacity: 0.9;
                    }}
                    .email {{
                        background: rgba(255,255,255,0.2);
                        padding: 10px 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                        font-family: monospace;
                        font-size: 16px;
                    }}
                    .contact {{
                        margin-top: 30px;
                        font-size: 16px;
                    }}
                    .contact a {{
                        color: #FFD700;
                        text-decoration: none;
                        font-weight: bold;
                    }}
                    .contact a:hover {{
                        text-decoration: underline;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="icon">🚫</div>
                    <h1>Acceso No Autorizado</h1>
                    <p>Tu cuenta no tiene permiso para acceder a esta aplicación.</p>
                    <div class="email">{user_email or 'Sin email'}</div>
                    <p>Esta plataforma está disponible solo para usuarios autorizados.</p>
                    <div class="contact">
                        Para solicitar acceso, contacta al administrador:<br>
                        <a href="mailto:admin@retarget.cl">admin@retarget.cl</a>
                    </div>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_denegado, status_code=403)
            
            # USUARIO AUTORIZADO - Actualizar último acceso
            usuario_autorizado.ultimo_acceso = datetime.utcnow()
            db.commit()
        
        # 4. Obtener lista de TODAS las páginas del usuario
        # First verify what permissions were actually granted
        perms_url = f"https://graph.facebook.com/v18.0/me/permissions?access_token={user_access_token}"
        perms_response = requests.get(perms_url)
        granted_perms = set()
        if perms_response.ok:
            for item in perms_response.json().get('data', []):
                if item.get('status') == 'granted':
                    granted_perms.add(item.get('permission'))
        print(f"[OAuth] Permisos otorgados: {granted_perms}")

        if 'pages_show_list' not in granted_perms:
            from urllib.parse import quote
            error_msg = quote(
                "The 'pages_show_list' permission was not granted. "
                "In the Facebook Login dialog, make sure to grant all requested permissions "
                "and select at least one Page to connect."
            )
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=f"{config.FRONTEND_URL}/?oauth_error={error_msg}")

        # tasks field (requires business_management): shows the user's role on each page.
        # We try with tasks first; if not available, fall back to basic fields.
        pages_with_tasks_url = (
            f"https://graph.facebook.com/v18.0/me/accounts?access_token={user_access_token}"
            f"&fields=id,name,access_token,tasks,instagram_business_account{{id,username}}"
        )
        pages_basic_url = (
            f"https://graph.facebook.com/v18.0/me/accounts?access_token={user_access_token}"
            f"&fields=id,name,access_token,instagram_business_account{{id,username}}"
        )

        pages_response = requests.get(pages_with_tasks_url)
        pages_response.raise_for_status()
        pages_data = pages_response.json()
        print(f"[OAuth] /me/accounts (with tasks) raw: {pages_data}")

        if 'error' in pages_data or not pages_data.get('data'):
            print(f"[OAuth] tasks field unavailable ({pages_data.get('error', {}).get('message', 'empty data')}), retrying without tasks.")
            pages_response = requests.get(pages_basic_url)
            pages_response.raise_for_status()
            pages_data = pages_response.json()
            print(f"[OAuth] /me/accounts (basic) raw: {pages_data}")

        pages = pages_data.get('data', [])

        if not pages:
            from urllib.parse import quote
            error_msg = quote(
                "No Facebook Pages were found for your account. "
                "During the Facebook Login, there is a step titled 'What can [App] access?' or "
                "'Choose Pages' where you must select which Pages to share. "
                "Please go to Facebook Settings > Security and Login > Business Integrations, "
                "remove this app, then reconnect and carefully select your Page in the login dialog."
            )
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=f"{config.FRONTEND_URL}/?oauth_error={error_msg}")
        
        # 6. Procesar información de cada página
        pages_info = []
        for page in pages:
            page_id = page['id']
            page_name = page['name']
            page_access_token = page['access_token']
            
            # Información de Instagram (si existe)
            instagram_account = page.get('instagram_business_account')
            instagram_id = instagram_account.get('id') if instagram_account else None
            instagram_username = instagram_account.get('username') if instagram_account else None

            # Verify admin role: MANAGE task indicates full administrator access
            page_tasks = page.get('tasks', [])
            is_admin = 'MANAGE' in page_tasks
            if not is_admin:
                print(f"[OAuth] ⚠️  Page '{page_name}' ({page_id}): user lacks MANAGE task. Tasks: {page_tasks}")

            pages_info.append({
                "page_id": page_id,
                "page_name": page_name,
                "page_access_token": page_access_token,
                "instagram_id": instagram_id,
                "instagram_username": instagram_username,
                "tasks": page_tasks,
                "is_admin": is_admin
            })
        
        # 4. Retornar HTML que envía las páginas al dashboard para selección
        from fastapi.responses import HTMLResponse
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Conectando...</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                .container {{
                    text-align: center;
                    padding: 40px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 10px;
                    backdrop-filter: blur(10px);
                }}
                .spinner {{
                    border: 4px solid rgba(255,255,255,0.3);
                    border-top: 4px solid white;
                    border-radius: 50%;
                    width: 50px;
                    height: 50px;
                    animation: spin 1s linear infinite;
                    margin: 20px auto;
                }}
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="spinner"></div>
                <h2>Conexión exitosa!</h2>
                <p>Redirigiendo al dashboard para seleccionar páginas...</p>
            </div>
            <script>
                // Guardar páginas en sessionStorage
                const pagesData = {json.dumps(pages_info)};
                sessionStorage.setItem('facebook_pages', JSON.stringify(pagesData));
                
                // Redirigir al dashboard después de 1 segundo
                setTimeout(() => {{
                    window.location.href = '{config.FRONTEND_URL}/?show_pages_modal=true';
                }}, 1000);
            </script>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
    
    except requests.HTTPError as e:
        print(f"❌ Error en OAuth Facebook: {e}")
        print(f"   Respuesta: {e.response.text if hasattr(e, 'response') else 'N/A'}")
        from urllib.parse import quote
        from fastapi.responses import RedirectResponse
        error_msg = quote(f"Facebook connection error: {e.response.status_code if hasattr(e, 'response') else str(e)}")
        return RedirectResponse(url=f"{config.FRONTEND_URL}/?oauth_error={error_msg}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error procesando callback: {e}")
        import traceback
        traceback.print_exc()
        from urllib.parse import quote
        from fastapi.responses import RedirectResponse
        error_msg = quote("Unexpected error during login. Please try again.")
        return RedirectResponse(url=f"{config.FRONTEND_URL}/?oauth_error={error_msg}")


# =============================================================================
# === ENDPOINTS DE ADMINISTRACIÓN DE USUARIOS ===
# =============================================================================


@app.get("/admin/usuarios", response_model=List[UsuarioResponse], tags=["Admin"])
async def listar_usuarios(
    db: Session = Depends(get_admin_db),
    _: bool = Depends(verificar_admin_token)
):
    """Lista todos los usuarios autorizados."""
    from backend.database.models import UsuarioAutorizado
    
    usuarios = db.query(UsuarioAutorizado).order_by(UsuarioAutorizado.fecha_registro.desc()).all()
    return usuarios


@app.post("/admin/usuarios", response_model=UsuarioResponse, status_code=201, tags=["Admin"])
async def crear_usuario(
    usuario: UsuarioCreate,
    db: Session = Depends(get_admin_db),
    _: bool = Depends(verificar_admin_token)
):
    """Crea un nuevo usuario autorizado."""
    from backend.database.models import UsuarioAutorizado
    
    # Verificar si ya existe
    existe = db.query(UsuarioAutorizado).filter(
        UsuarioAutorizado.email == usuario.email
    ).first()
    
    if existe:
        raise HTTPException(status_code=400, detail=f"Usuario {usuario.email} ya existe")
    
    # Validar rol
    if usuario.rol not in ["candidato", "admin", "equipo"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Use: candidato, admin o equipo")
    
    # Crear usuario
    nuevo_usuario = UsuarioAutorizado(
        email=usuario.email,
        nombre=usuario.nombre,
        rol=usuario.rol,
        activo=1,
        fecha_registro=datetime.utcnow()
    )
    
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    
    return nuevo_usuario


@app.get("/admin/usuarios/{usuario_id}", response_model=UsuarioResponse, tags=["Admin"])
async def obtener_usuario(
    usuario_id: int,
    db: Session = Depends(get_admin_db),
    _: bool = Depends(verificar_admin_token)
):
    """Obtiene un usuario por ID."""
    from backend.database.models import UsuarioAutorizado
    
    usuario = db.query(UsuarioAutorizado).filter(
        UsuarioAutorizado.id == usuario_id
    ).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return usuario


@app.patch("/admin/usuarios/{usuario_id}", response_model=UsuarioResponse, tags=["Admin"])
async def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Session = Depends(get_admin_db),
    _: bool = Depends(verificar_admin_token)
):
    """Actualiza un usuario (nombre, rol, estado activo)."""
    from backend.database.models import UsuarioAutorizado
    
    usuario = db.query(UsuarioAutorizado).filter(
        UsuarioAutorizado.id == usuario_id
    ).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Actualizar campos
    if datos.nombre is not None:
        usuario.nombre = datos.nombre
    
    if datos.rol is not None:
        if datos.rol not in ["candidato", "admin", "equipo"]:
            raise HTTPException(status_code=400, detail="Rol inválido")
        usuario.rol = datos.rol
    
    if datos.activo is not None:
        usuario.activo = datos.activo
    
    db.commit()
    db.refresh(usuario)
    
    return usuario


@app.delete("/admin/usuarios/{usuario_id}", status_code=204, tags=["Admin"])
async def eliminar_usuario(
    usuario_id: int,
    db: Session = Depends(get_admin_db),
    _: bool = Depends(verificar_admin_token)
):
    """Desactiva un usuario (no lo elimina, solo lo marca como inactivo)."""
    from backend.database.models import UsuarioAutorizado
    
    usuario = db.query(UsuarioAutorizado).filter(
        UsuarioAutorizado.id == usuario_id
    ).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    usuario.activo = 0
    db.commit()
    
    return None


@app.post("/admin/usuarios/generar-token", tags=["Admin"])
async def generar_token_admin():
    """
    Genera un nuevo token de administrador.
    ⚠️ USAR SOLO UNA VEZ al configurar la app.
    Luego eliminar este endpoint por seguridad.
    """
    nuevo_token = secrets.token_urlsafe(32)
    
    return {
        "token": nuevo_token,
        "mensaje": "Guarda este token en variable de entorno ADMIN_TOKEN",
        "ejemplo": f"heroku config:set ADMIN_TOKEN={nuevo_token}",
        "advertencia": "Elimina este endpoint /generar-token después de configurar el token"
    }


# =============================================================================
# === ENDPOINTS DE CANDIDATOS ===
# =============================================================================


@app.post("/api/candidatos/conectar-paginas")
async def conectar_paginas_seleccionadas(request: Request):
    """
    Crear candidatos para las páginas seleccionadas por el usuario.
    
    Body: {
        "pages": [
            {
                "page_id": "123",
                "page_name": "Mi Página",
                "page_access_token": "token",
                "instagram_id": "456",
                "instagram_username": "mi_usuario"
            }
        ],
        "email_base": "usuario@ejemplo.com"  // Opcional
    }
    """
    try:
        body = await request.json()
        pages = body.get("pages", [])
        email_base = body.get("email_base", "user")
        instagram_access_token = body.get("instagram_access_token")  # User-level token for Instagram Messaging API
        owner_facebook_user_id = body.get("facebook_user_id")  # Propietario del usuario OAuth
        
        if not pages:
            raise HTTPException(status_code=400, detail="No se proporcionaron páginas para conectar")
        
        candidatos_creados = []
        candidatos_actualizados = []
        errores = []
        
        for page_data in pages:
            try:
                page_id = page_data.get("page_id")
                page_name = page_data.get("page_name")
                page_access_token = page_data.get("page_access_token")
                instagram_id = page_data.get("instagram_id")
                instagram_username = page_data.get("instagram_username")
                
                if not page_id or not page_name or not page_access_token:
                    errores.append(f"Datos incompletos para página {page_name or 'desconocida'}")
                    continue
                
                # Buscar si ya existe candidato con este page_id
                candidato_existente = CandidatoService.obtener_candidato_por_page_id(page_id)
                
                if candidato_existente:
                    # Actualizar tokens existentes
                    candidato = CandidatoService.actualizar_tokens_facebook(
                        candidato_id=candidato_existente['id'],
                        facebook_page_id=page_id,
                        facebook_page_name=page_name,
                        facebook_page_access_token=page_access_token,
                        facebook_token_expiration=datetime.now(),
                        instagram_business_account_id=instagram_id,
                        instagram_username=instagram_username,
                        instagram_access_token=instagram_access_token,
                        owner_facebook_user_id=owner_facebook_user_id
                    )
                    candidatos_actualizados.append({
                        "id": candidato['id'],
                        "nombre": page_name,
                        "facebook_page_name": page_name,
                        "instagram_username": instagram_username
                    })
                else:
                    # Crear nuevo candidato
                    candidato_email = f"{page_id}@facebook.page"
                    
                    candidato = CandidatoService.crear_candidato(
                        nombre=page_name,
                        email=candidato_email,
                        facebook_page_id=page_id,
                        facebook_page_name=page_name,
                        facebook_page_access_token=page_access_token,
                        facebook_token_expiration=datetime.now(),
                        instagram_business_account_id=instagram_id,
                        instagram_username=instagram_username,
                        instagram_access_token=instagram_access_token,
                        owner_facebook_user_id=owner_facebook_user_id
                    )
                    candidatos_creados.append({
                        "id": candidato['id'],
                        "nombre": page_name,
                        "facebook_page_name": page_name,
                        "instagram_username": instagram_username
                    })
                    
            except Exception as e:
                errores.append(f"Error procesando {page_data.get('page_name', 'página')}: {str(e)}")
                print(f"❌ Error creando candidato para página {page_data.get('page_name')}: {e}")
                import traceback
                traceback.print_exc()
        
        return {
            "success": True,
            "message": f"Se procesaron {len(candidatos_creados) + len(candidatos_actualizados)} páginas",
            "candidatos_creados": candidatos_creados,
            "candidatos_actualizados": candidatos_actualizados,
            "errores": errores,
            "total_creados": len(candidatos_creados),
            "total_actualizados": len(candidatos_actualizados),
            "total_errores": len(errores)
        }
        
    except Exception as e:
        print(f"❌ Error en conectar-paginas: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    except requests.HTTPError as e:
        print(f"❌ Error en OAuth Facebook: {e}")
        print(f"   Respuesta: {e.response.text if hasattr(e, 'response') else 'N/A'}")
        raise HTTPException(status_code=400, detail=f"Error conectando con Facebook: {str(e)}")
    except Exception as e:
        print(f"❌ Error procesando callback: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/api/candidatos")
def listar_candidatos(owner_facebook_user_id: Optional[str] = Query(None)):
    """Listar candidatos registrados, opcionalmente filtrados por propietario."""
    try:
        candidatos = CandidatoService.listar_candidatos(owner_facebook_user_id=owner_facebook_user_id)
        return candidatos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Sync job tracker ───────────────────────────────────────────────────────
import threading as _threading
_sync_jobs: dict = {}
_sync_jobs_lock = _threading.Lock()

def _sync_job_update(candidato_id: int, **kwargs):
    with _sync_jobs_lock:
        if candidato_id not in _sync_jobs:
            _sync_jobs[candidato_id] = {"state": "idle", "progress": 0, "total": 0, "message": "", "errors": [], "phase": "", "fb_total": 0, "fb_progress": 0, "ig_total": 0, "ig_progress": 0}
        _sync_jobs[candidato_id].update(kwargs)

def _sync_job_progress_inc(candidato_id: int, plataforma: str):
    """Incrementa el progreso general y el específico de plataforma."""
    with _sync_jobs_lock:
        _sync_jobs[candidato_id]["progress"] = _sync_jobs[candidato_id].get("progress", 0) + 1
        pk = "fb_progress" if plataforma == "facebook" else "ig_progress"
        _sync_jobs[candidato_id][pk] = _sync_jobs[candidato_id].get(pk, 0) + 1

def _sync_job_get(candidato_id: int) -> dict:
    with _sync_jobs_lock:
        return dict(_sync_jobs.get(candidato_id, {"state": "idle"}))
# ───────────────────────────────────────────────────────────────────────────


@app.get("/api/candidatos/{candidato_id}/sync-status")
def get_sync_status(candidato_id: int):
    """Retorna el estado actual del job de sincronización para un candidato."""
    return _sync_job_get(candidato_id)


@app.post("/api/candidatos/{candidato_id}/sincronizar")
def sincronizar_candidato(
    candidato_id: int,
    sincronizar_facebook: bool = Query(True),
    sincronizar_instagram: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    force_reprocess: bool = Query(False),
    meses_historico: int = Query(3, ge=1, le=24),
    desde_fecha: Optional[str] = Query(None),
):
    """
    Inicia la sincronización en un hilo de fondo y retorna inmediatamente.
    Usa GET /api/candidatos/{id}/sync-status para consultar el progreso.
    """
    from datetime import timedelta
    try:
        candidato = CandidatoService.obtener_candidato_por_id(candidato_id)
        if not candidato:
            raise HTTPException(status_code=404, detail="Candidato no encontrado")

        if not candidato.get('facebook_page_access_token'):
            raise HTTPException(
                status_code=400,
                detail="Candidato no tiene token de acceso. Debe conectar su cuenta primero."
            )

        job = _sync_job_get(candidato_id)
        if job.get("state") == "running":
            return {"ok": False, "message": "Ya hay una sincronización en curso para este candidato."}

        # Always use the per-candidato page_access_token for Facebook.
        # Using a global ENV token (META_ACCESS_TOKEN) across multiple candidatos causes
        # error #10 "Requested Page Does Not Match Page Access Token" because each
        # page_access_token is scoped to a specific Page.
        _fb_token = candidato.get('facebook_page_access_token')
        cliente = crear_cliente_candidato(
            _fb_token,
            instagram_token=candidato.get('instagram_access_token')
        )
        _ig_db = candidato.get('instagram_access_token')
        _ig_valid = isinstance(_ig_db, str) and bool(_ig_db.strip())
        token_source = "DB" if _ig_valid else "PAGE_TOKEN_FALLBACK"
        print(f"   🔑 Facebook token source: DB(facebook_page_access_token) | prefix={(_fb_token or '')[:12]}...")
        print(f"   🔑 Instagram token source: {token_source} | db_raw={repr(_ig_db)[:30]} | prefix={(cliente.instagram_token or '')[:12]}...")
        if desde_fecha:
            try:
                fecha_desde = datetime.strptime(desde_fecha, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Formato de fecha inválido: {desde_fecha}. Use YYYY-MM-DD.")
        else:
            fecha_desde = datetime.utcnow() - timedelta(days=30 * meses_historico)

        _sync_job_update(candidato_id, state="running", progress=0, total=0,
                         message="Iniciando...", errors=[],
                         phase="", fb_total=0, fb_progress=0, ig_total=0, ig_progress=0)

        def _run():
            plataformas = []
            if sincronizar_facebook and candidato.get('facebook_page_id'):
                plataformas.append(("facebook", candidato['facebook_page_id']))
            # Instagram Messaging API via Messenger Platform uses the Facebook Page ID with platform=instagram
            if sincronizar_instagram and candidato.get('facebook_page_id'):
                plataformas.append(("instagram", candidato['facebook_page_id']))

            if not plataformas:
                _sync_job_update(candidato_id, state="done", message="No hay cuentas configuradas para sincronizar.")
                return

            for plataforma, page_id in plataformas:
                sincronizar_conversaciones_tarea(
                    cliente=cliente,
                    page_id=page_id,
                    plataforma=plataforma,
                    limit=limit,
                    candidato_id=candidato_id,
                    force_reprocess=force_reprocess,
                    fecha_desde=fecha_desde,
                )

            job = _sync_job_get(candidato_id)
            if job.get("state") != "error":
                _sync_job_update(candidato_id, state="done",
                                 message=f"✅ Sincronización completada — {job.get('progress', 0)} conversaciones procesadas.")

        t = _threading.Thread(target=_run, daemon=True)
        t.start()
        return {"ok": True, "message": "Sincronización iniciada en segundo plano."}

    except HTTPException:
        raise
    except Exception as e:
        _sync_job_update(candidato_id, state="error", message=str(e))
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def sincronizar_conversaciones_tarea(
    cliente,
    page_id: str,
    plataforma: str,
    limit: int,
    candidato_id: int,
    force_reprocess: bool = False,
    fecha_desde: datetime = None,
):
    from datetime import timedelta
    if fecha_desde is None:
        fecha_desde = datetime.utcnow() - timedelta(days=90)

    try:
        print(f"\n🔄 Iniciando sincronización de {plataforma} para candidato {candidato_id}")
        print(f"   Page/Account ID: {page_id}")
        print(f"   Límite: {limit} conversaciones | Histórico desde: {fecha_desde.date()}")
        import calendar as _calendar
        since_ts = int(_calendar.timegm(fecha_desde.timetuple()))
        print(f"   Filtrando desde Unix timestamp: {since_ts} ({fecha_desde.date()})")
        _sync_job_update(candidato_id, message=f"Obteniendo conversaciones de {plataforma}…")

        if plataforma == "facebook":
            conversaciones = cliente.obtener_conversaciones_facebook(page_id, limit, since=since_ts)
        else:
            conversaciones = cliente.obtener_conversaciones_instagram(page_id, limit, since=since_ts)

        if not conversaciones:
            print(f"⚠️ No se encontraron conversaciones de {plataforma}")
            _sync_job_update(candidato_id, message=f"Sin conversaciones en {plataforma}.")
            return

        print(f"✅ Se encontraron {len(conversaciones)} conversaciones")
        total = len(conversaciones)

        with _sync_jobs_lock:
            prev_total = _sync_jobs.get(candidato_id, {}).get("total", 0)
            _sync_jobs[candidato_id]["total"] = prev_total + total
            _sync_jobs[candidato_id]["phase"] = plataforma
            if plataforma == "facebook":
                _sync_jobs[candidato_id]["fb_total"] = total
            else:
                _sync_jobs[candidato_id]["ig_total"] = total

        from sync_conversations import procesar_mensajes_usuario

        with get_db() as db:
            for i, conv in enumerate(conversaciones, 1):
                conv_id = conv.get("id")
                _sync_job_update(candidato_id, message=f"{plataforma}: procesando conversación {i}/{total}…")
                print(f"   📨 Procesando conversación {i}/{total}: {conv_id}")

                if plataforma == "facebook":
                    mensajes = cliente.obtener_mensajes_conversacion_facebook(conv_id)
                else:
                    mensajes = cliente.obtener_mensajes_conversacion_instagram(conv_id)

                if not mensajes:
                    print(f"      ⚠️ Sin mensajes")
                    _sync_job_progress_inc(candidato_id, plataforma)
                    continue

                import dateutil.parser as _dp
                mensajes = [
                    m for m in mensajes
                    if _dp.isoparse(m.get("created_time", "1970-01-01")).replace(tzinfo=None) >= fecha_desde
                ]
                if not mensajes:
                    print(f"      ⏩ Mensajes anteriores a {fecha_desde.date()}, saltando")
                    _sync_job_progress_inc(candidato_id, plataforma)
                    continue

                participants = conv.get("participants", {}).get("data", [])
                user_participant = next((p for p in participants if p["id"] != page_id), None)

                if not user_participant and mensajes:
                    first_msg_from = mensajes[0].get("from", {})
                    if first_msg_from.get("id") != page_id:
                        user_participant = first_msg_from

                if not user_participant:
                    print(f"      ⚠️ No se pudo identificar usuario")
                    _sync_job_progress_inc(candidato_id, plataforma)
                    continue

                user_id = user_participant.get("id")
                username = user_participant.get("name") or user_participant.get("username")

                procesar_mensajes_usuario(
                    db=db,
                    user_id=user_id,
                    username=username,
                    plataforma=plataforma,
                    mensajes=mensajes,
                    ignorar_id=page_id,
                    force_reprocess=force_reprocess,
                    candidato_id=candidato_id,
                )

                print(f"      ✅ Procesado: {username or user_id} ({len(mensajes)} mensajes)")
                _sync_job_progress_inc(candidato_id, plataforma)

        print(f"✅ Sincronización de {plataforma} completada para candidato {candidato_id}\n")

    except Exception as e:
        print(f"❌ Error en sincronización de {plataforma}: {e}")
        import traceback
        traceback.print_exc()
        _sync_job_update(candidato_id, state="error", message=f"Error {plataforma}: {str(e)}")


@app.post("/api/candidatos/{candidato_id}/configurar-whatsapp")
async def configurar_whatsapp_candidato(
    candidato_id: int,
    whatsapp_phone_number_id: str = Query(..., description="ID del número de teléfono de WhatsApp"),
    whatsapp_business_account_id: str = Query(..., description="ID de la cuenta de negocio de WhatsApp"),
    whatsapp_phone_number: str = Query(..., description="Número de teléfono en formato internacional"),
    whatsapp_access_token: Optional[str] = Query(None, description="Token de acceso (opcional, usa el de Facebook si no se provee)")
):
    """
    Configurar WhatsApp Business para un candidato.
    
    Args:
        candidato_id: ID del candidato
        whatsapp_phone_number_id: ID del número de WhatsApp (obtén de Meta Business Manager)
        whatsapp_business_account_id: ID de la cuenta de negocio
        whatsapp_phone_number: Número en formato +56912345678
        whatsapp_access_token: Token de acceso (opcional)
    """
    try:
        # Obtener candidato
        candidato = CandidatoService.obtener_candidato_por_id(candidato_id)
        if not candidato:
            raise HTTPException(status_code=404, detail="Candidato no encontrado")
        
        # Actualizar configuración de WhatsApp
        candidato_actualizado = CandidatoService.actualizar_whatsapp(
            candidato_id=candidato_id,
            whatsapp_phone_number_id=whatsapp_phone_number_id,
            whatsapp_business_account_id=whatsapp_business_account_id,
            whatsapp_phone_number=whatsapp_phone_number,
            whatsapp_access_token=whatsapp_access_token
        )
        
        return {
            "success": True,
            "message": "WhatsApp configurado correctamente",
            "candidato": {
                "id": candidato_actualizado['id'],
                "nombre": candidato_actualizado.get('nombre'),
                "whatsapp_phone_number": candidato_actualizado['whatsapp_phone_number'],
                "whatsapp_phone_number_id": candidato_actualizado['whatsapp_phone_number_id']
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"❌ Error configurando WhatsApp: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/candidatos/{candidato_id}/instagram-token")
async def actualizar_instagram_token(candidato_id: int, request: Request):
    """Actualizar el token de acceso de Instagram para un candidato."""
    try:
        body = await request.json()
        instagram_access_token = (body.get("instagram_access_token") or "").strip()
        if not instagram_access_token:
            raise HTTPException(status_code=400, detail="Token vacío")

        if config.ENV == "local":
            from backend.database.dataframe_storage import get_storage
            storage = get_storage()
            mask = storage.candidatos_df['id'] == candidato_id
            if not mask.any():
                raise HTTPException(status_code=404, detail="Candidato no encontrado")
            if 'instagram_access_token' not in storage.candidatos_df.columns:
                storage.candidatos_df['instagram_access_token'] = None
            storage.candidatos_df.loc[mask, 'instagram_access_token'] = instagram_access_token
            storage.save_candidatos()
        else:
            from backend.database.models import Candidato as CandidatoModel
            with get_db() as db:
                candidato_obj = db.query(CandidatoModel).filter(CandidatoModel.id == candidato_id).first()
                if not candidato_obj:
                    raise HTTPException(status_code=404, detail="Candidato no encontrado")
                candidato_obj.instagram_access_token = instagram_access_token
                db.commit()

        return {"success": True, "message": "Token de Instagram actualizado correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error actualizando token de Instagram: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/intereses")
def listar_intereses():
    """Listar todas las categorías de intereses disponibles."""
    if USE_DATAFRAMES:
        from backend.database.dataframe_storage import get_storage
        storage = get_storage()
        return storage.intereses_df[['id', 'categoria']].to_dict('records')
    else:
        from backend.database.models import Interes
        with get_db() as db:
            intereses = db.query(Interes).all()
            return [{"id": i.id, "categoria": i.categoria} for i in intereses]


@app.get("/api/personas", response_model=List[PersonaResponse])
def listar_personas(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin: Optional[str] = Query(None)
):
    """Listar todas las sesiones de conversación (análisis)."""
    
    # Parsear fechas si existen
    dt_inicio = None
    dt_fin = None
    if fecha_inicio:
        try:
            dt_inicio = datetime.fromisoformat(fecha_inicio)
        except:
            pass
    if fecha_fin:
        try:
            dt_fin = datetime.fromisoformat(fecha_fin)
        except:
            pass

    # Obtenemos los análisis más recientes
    analisis_list = AnalisisService.buscar_analisis(
        fecha_inicio=dt_inicio,
        fecha_fin=dt_fin,
        limit=limit
    )
    
    resultado = []
    
    if USE_DATAFRAMES:
        # Modo DataFrames
        from backend.database.dataframe_storage import get_storage
        storage = get_storage()
        
        for analisis in analisis_list:
            persona_id = analisis['persona_id']
            persona = PersonaService.obtener_persona_por_id(persona_id)
            
            if not persona:
                continue
            
            # Obtener intereses
            intereses = []
            try:
                if analisis.get('categorias'):
                    intereses = json.loads(analisis['categorias'])
                else:
                    # Buscar intereses de la persona
                    rel_mask = storage.persona_interes_df['persona_id'] == persona_id
                    if rel_mask.any():
                        interes_ids = storage.persona_interes_df[rel_mask]['interes_id'].values
                        intereses_mask = storage.intereses_df['id'].isin(interes_ids)
                        intereses = storage.intereses_df[intereses_mask]['categoria'].tolist()
            except:
                intereses = []
            
            # Obtener evento si existe
            evento_nombre = None
            if analisis.get('evento_id') and pd.notna(analisis['evento_id']):
                evento = EventoService.obtener_por_id(int(analisis['evento_id']))
                if evento:
                    evento_nombre = evento['nombre']
            
            resultado.append({
                "id": persona['id'],
                "analisis_id": analisis['id'],
                "nombre_completo": persona.get('nombre_completo'),
                "edad": int(persona['edad']) if pd.notna(persona.get('edad')) else None,
                "genero": persona.get('genero'),
                "telefono": persona.get('telefono'),
                "email": persona.get('email'),
                "ocupacion": persona.get('ocupacion'),
                "ubicacion": persona.get('ubicacion'),
                "facebook_username": persona.get('facebook_username'),
                "instagram_username": persona.get('instagram_username'),
                "intereses": intereses,
                "resumen_conversacion": analisis.get('resumen'),
                "fecha_primer_contacto": persona['fecha_primer_contacto'],
                "fecha_ultimo_contacto": analisis.get('start_conversation') or analisis.get('fecha_analisis'),
                "evento_id": int(analisis['evento_id']) if analisis.get('evento_id') and pd.notna(analisis['evento_id']) else None,
                "evento_nombre": evento_nombre
            })
    else:
        # Modo SQLAlchemy
        for analisis in analisis_list:
            persona = analisis.persona
            intereses = []
            try:
                if analisis.categorias:
                     intereses = json.loads(analisis.categorias)
                elif persona.intereses:
                     intereses = [i.categoria for i in persona.intereses]
            except:
                intereses = []

            resultado.append({
                "id": persona.id,
                "analisis_id": analisis.id,
                "nombre_completo": persona.nombre_completo,
                "edad": persona.edad,
                "genero": persona.genero,
                "telefono": persona.telefono,
                "email": persona.email,
                "ocupacion": persona.ocupacion,
                "ubicacion": persona.ubicacion,
                "facebook_username": persona.facebook_username,
                "instagram_username": persona.instagram_username,
                "intereses": intereses,
                "resumen_conversacion": analisis.resumen,
                "fecha_primer_contacto": persona.fecha_primer_contacto,
                "fecha_ultimo_contacto": analisis.start_conversation or analisis.fecha_analisis,
                "evento_id": analisis.evento_id,
                "evento_nombre": analisis.evento.nombre if analisis.evento else None
            })
    
    return resultado


@app.get("/api/personas/{persona_id}")
def obtener_persona(persona_id: int):
    """Obtener una persona específica."""
    with get_db() as db:
        if USE_DATAFRAMES:
            persona = PersonaService.obtener_persona_por_id(persona_id)
        else:
            persona = PersonaService.obtener_persona_por_id(db, persona_id)
        
        if not persona:
            raise HTTPException(status_code=404, detail="Persona no encontrada")
        
        if USE_DATAFRAMES:
            from backend.database.dataframe_storage import get_storage
            storage = get_storage()
            rel_mask = storage.persona_interes_df['persona_id'] == persona_id
            interes_ids = storage.persona_interes_df[rel_mask]['interes_id'].values
            intereses_mask = storage.intereses_df['id'].isin(interes_ids)
            intereses = storage.intereses_df[intereses_mask]['categoria'].tolist()
            
            # Cantidad de conversaciones
            conv_mask = storage.conversaciones_df['persona_id'] == persona_id
            cant_conv = conv_mask.sum()

            return {
                "id": persona['id'],
                "nombre_completo": persona.get('nombre_completo'),
                "edad": persona.get('edad'),
                "genero": persona.get('genero'),
                "telefono": persona.get('telefono'),
                "email": persona.get('email'),
                "ocupacion": persona.get('ocupacion'),
                "ubicacion": persona.get('ubicacion'),
                "facebook_id": persona.get('facebook_id'),
                "instagram_id": persona.get('instagram_id'),
                "intereses": intereses,
                "fecha_primer_contacto": persona['fecha_primer_contacto'],
                "fecha_ultimo_contacto": persona['fecha_ultimo_contacto'],
                "cantidad_conversaciones": int(cant_conv)
            }
        else:
            return {
                "id": persona.id,
                "nombre_completo": persona.nombre_completo,
                "edad": persona.edad,
                "genero": persona.genero,
                "telefono": persona.telefono,
                "email": persona.email,
                "ocupacion": persona.ocupacion,
                "ubicacion": persona.ubicacion,
                "facebook_id": persona.facebook_id,
                "instagram_id": persona.instagram_id,
                "intereses": [i.categoria for i in persona.intereses],
                "fecha_primer_contacto": persona.fecha_primer_contacto,
                "fecha_ultimo_contacto": persona.fecha_ultimo_contacto,
                "cantidad_conversaciones": len(persona.conversaciones)
            }


from collections import Counter


@app.get("/api/personas")
def listar_personas(limit: int = 100, db: Session = Depends(get_db_session)):
    """Listar todas las personas."""
    try:
        if USE_DATAFRAMES:
            from backend.database.dataframe_storage import get_storage
            storage = get_storage()
            personas_list = storage.personas_df.head(limit).to_dict('records')
            
            resultado = []
            for persona in personas_list:
                persona_id = persona['id']
                rel_mask = storage.persona_interes_df['persona_id'] == persona_id
                interes_ids = storage.persona_interes_df[rel_mask]['interes_id'].values
                intereses_mask = storage.intereses_df['id'].isin(interes_ids)
                intereses = storage.intereses_df[intereses_mask]['categoria'].tolist()
                
                resultado.append({
                    "id": persona['id'],
                    "nombre_completo": persona.get('nombre_completo'),
                    "edad": persona.get('edad'),
                    "genero": persona.get('genero'),
                    "ubicacion": persona.get('ubicacion'),
                    "intereses": intereses,
                    "fecha_primer_contacto": persona['fecha_primer_contacto'],
                    "fecha_ultimo_contacto": persona['fecha_ultimo_contacto']
                })
            return resultado
        else:
            # Modo SQLAlchemy
            personas = db.query(Persona).limit(limit).all()
            return [
                {
                    "id": p.id,
                    "nombre_completo": p.nombre_completo,
                    "edad": p.edad,
                    "genero": p.genero,
                    "ubicacion": p.ubicacion,
                    "intereses": [i.categoria for i in p.intereses] if p.intereses else [],
                    "fecha_primer_contacto": p.fecha_primer_contacto,
                    "fecha_ultimo_contacto": p.fecha_ultimo_contacto
                }
                for p in personas
            ]
    except Exception as e:
        # Retornar lista vacía si hay error
        print(f"[ERROR] /api/personas: {e}")
        return []


def _get_candidato_ids_por_owner(facebook_user_id: Optional[str]) -> Optional[set]:
    """Retornar el conjunto de IDs de candidatos del usuario, o None si no se filtra."""
    if not facebook_user_id:
        return None
    ids = CandidatoService.listar_candidatos_por_owner(facebook_user_id)
    return set(ids)


@app.post("/api/personas/buscar")
def buscar_personas(busqueda: BusquedaRequest):
    """Buscar sesiones/personas según criterios."""
    # 1. Parsear fechas
    dt_inicio = None
    dt_fin = None
    if busqueda.fecha_inicio:
        try:
             dt_inicio = datetime.fromisoformat(busqueda.fecha_inicio)
        except: pass
    if busqueda.fecha_fin:
        try:
             dt_fin = datetime.fromisoformat(busqueda.fecha_fin)
        except: pass

    page = max(0, busqueda.page or 0)
    page_size = max(1, min(busqueda.page_size or 50, 200))
    candidato_ids_owner = _get_candidato_ids_por_owner(busqueda.facebook_user_id)

    # 2. Modo DataFrames: vectorizado, arrancando desde personas_df para incluir WhatsApp
    if USE_DATAFRAMES:
        import numpy as np
        from backend.database.dataframe_storage import get_storage
        storage = get_storage()

        personas_df = storage.personas_df.copy()
        for col in ('fecha_ultimo_contacto', 'fecha_primer_contacto'):
            if col in personas_df.columns and not pd.api.types.is_datetime64_any_dtype(personas_df[col]):
                personas_df[col] = pd.to_datetime(personas_df[col], errors='coerce')

        adf = storage.analisis_df.copy()
        if not adf.empty and 'start_conversation' in adf.columns:
            if not pd.api.types.is_datetime64_any_dtype(adf['start_conversation']):
                adf['start_conversation'] = pd.to_datetime(adf['start_conversation'], errors='coerce')

        ft_inicio = dt_inicio.replace(tzinfo=None) if (dt_inicio and dt_inicio.tzinfo) else dt_inicio
        ft_fin = dt_fin.replace(tzinfo=None) if (dt_fin and dt_fin.tzinfo) else dt_fin

        # Filtro de fecha: personas con analisis en el rango O (WhatsApp) con último contacto en rango
        persona_ids_en_rango = None
        if ft_inicio or ft_fin:
            adf_rango = adf.copy() if not adf.empty else pd.DataFrame(columns=['persona_id', 'start_conversation'])
            if ft_inicio:
                adf_rango = adf_rango[adf_rango['start_conversation'] >= ft_inicio]
            if ft_fin:
                adf_rango = adf_rango[adf_rango['start_conversation'] <= ft_fin]
            ids_via_analisis = set(adf_rango['persona_id'].tolist())

            # WhatsApp-only personas: sin facebook_id ni instagram_id, con teléfono
            wa_mask = (
                personas_df['telefono'].notna() &
                (personas_df['facebook_id'].isna() | (personas_df['facebook_id'].astype(str) == '')) &
                (personas_df['instagram_id'].isna() | (personas_df['instagram_id'].astype(str) == ''))
            )
            wa_df = personas_df[wa_mask]
            if not wa_df.empty:
                fuc = wa_df['fecha_ultimo_contacto']
                wa_ok = pd.Series(True, index=wa_df.index)
                if ft_inicio:
                    wa_ok &= fuc >= ft_inicio
                if ft_fin:
                    wa_ok &= fuc <= ft_fin
                ids_via_wa = set(wa_df[wa_ok]['id'].tolist())
            else:
                ids_via_wa = set()

            persona_ids_en_rango = ids_via_analisis | ids_via_wa

        # Filtros demográficos y de propietario (vectorizados sobre personas_df)
        if candidato_ids_owner is not None:
            personas_df = personas_df[personas_df['candidato_id'].isin(set(candidato_ids_owner))]
        if persona_ids_en_rango is not None:
            personas_df = personas_df[personas_df['id'].isin(persona_ids_en_rango)]
        if busqueda.genero:
            personas_df = personas_df[personas_df['genero'] == busqueda.genero]
        if busqueda.edad_min is not None:
            personas_df = personas_df[pd.to_numeric(personas_df['edad'], errors='coerce') >= busqueda.edad_min]
        if busqueda.edad_max is not None:
            personas_df = personas_df[pd.to_numeric(personas_df['edad'], errors='coerce') <= busqueda.edad_max]
        if busqueda.ubicacion:
            personas_df = personas_df[personas_df['ubicacion'].fillna('').str.lower().str.contains(busqueda.ubicacion.lower(), regex=False)]

        if personas_df.empty:
            return {"total": 0, "total_paginas": 0, "personas": [], "stats": {"por_genero": {}, "por_interes": {}}}

        # Analisis deduplicado: el más reciente por persona (para LEFT JOIN)
        if not adf.empty:
            adf_dedup = (
                adf.sort_values('start_conversation', ascending=False)
                .drop_duplicates(subset=['persona_id'], keep='first')
                [['persona_id', 'id', 'resumen', 'categorias', 'start_conversation', 'fecha_analisis']]
                .rename(columns={'id': '_analisis_id', 'resumen': '_resumen_analisis'})
            )
        else:
            adf_dedup = pd.DataFrame(columns=['persona_id', '_analisis_id', '_resumen_analisis', 'categorias', 'start_conversation', 'fecha_analisis'])

        # LEFT JOIN: todas las personas + su analisis más reciente (si tienen)
        merged = personas_df.merge(adf_dedup, left_on='id', right_on='persona_id', how='left')

        # Filtro por intereses (analisis.categorias; personas WA sin analisis no son excluidas si no hay filtro)
        if busqueda.intereses:
            filtro = set(busqueda.intereses)
            def _has_interes(cat_json):
                if not cat_json or (isinstance(cat_json, float) and pd.isna(cat_json)):
                    return False
                try:
                    cats = json.loads(cat_json) if isinstance(cat_json, str) else []
                    return bool(set(cats) & filtro)
                except:
                    return False
            merged = merged[merged['categorias'].apply(_has_interes)]

        # Derivar plataforma vectorizado
        ig_ok = merged['instagram_id'].notna() & (merged['instagram_id'].astype(str).str.strip().ne(''))
        fb_ok = merged['facebook_id'].notna() & (merged['facebook_id'].astype(str).str.strip().ne(''))
        wa_ok = merged['telefono'].notna() & (merged['telefono'].astype(str).str.strip().ne(''))
        merged['_plataforma'] = np.select([ig_ok, fb_ok, wa_ok], ['instagram', 'messenger', 'whatsapp'], default=None)

        # Ordenar por fecha más reciente disponible
        merged['_fecha_sort'] = merged['start_conversation'].combine_first(
            merged.get('fecha_ultimo_contacto', pd.Series(dtype='datetime64[ns]'))
        )
        merged = merged.sort_values('_fecha_sort', ascending=False, na_position='last')

        # Estadísticas sobre el conjunto filtrado completo (antes de paginar)
        total = len(merged)
        total_paginas = max(1, (total + page_size - 1) // page_size)
        generos_list = merged['genero'].fillna('No especificado').tolist()
        all_intereses_flat = []
        for cat in merged['categorias'].dropna():
            try:
                all_intereses_flat.extend(json.loads(cat) if isinstance(cat, str) else [])
            except:
                pass
        stats = {
            "por_genero": dict(Counter(generos_list)),
            "por_interes": dict(Counter(all_intereses_flat))
        }

        # Paginación: solo construir dicts para la página actual
        paged = merged.iloc[page * page_size: (page + 1) * page_size]
        resultado = []
        for _, row in paged.iterrows():
            intereses = []
            try:
                cat = row.get('categorias')
                if cat and not (isinstance(cat, float) and pd.isna(cat)):
                    intereses = json.loads(cat) if isinstance(cat, str) else []
            except:
                pass
            if not intereses:
                pid = int(row['id']) if pd.notna(row.get('id')) else None
                if pid:
                    rel_mask = storage.persona_interes_df['persona_id'] == pid
                    if rel_mask.any():
                        interes_ids = storage.persona_interes_df[rel_mask]['interes_id'].values
                        intereses = storage.intereses_df[storage.intereses_df['id'].isin(interes_ids)]['categoria'].tolist()

            aid = row.get('_analisis_id')
            fc = row.get('fecha_primer_contacto')
            fecha_uc = row.get('_fecha_sort')
            resultado.append({
                "id": int(row['id']) if pd.notna(row.get('id')) else None,
                "analisis_id": int(aid) if pd.notna(aid) else 0,
                "nombre_completo": row.get('nombre_completo'),
                "edad": int(row['edad']) if pd.notna(row.get('edad')) else None,
                "genero": row.get('genero'),
                "telefono": row.get('telefono'),
                "email": row.get('email'),
                "ocupacion": row.get('ocupacion'),
                "ubicacion": row.get('ubicacion'),
                "facebook_username": row.get('facebook_username'),
                "instagram_username": row.get('instagram_username'),
                "intereses": intereses,
                "resumen_conversacion": row.get('_resumen_analisis'),
                "fecha_primer_contacto": str(fc) if pd.notna(fc) else None,
                "fecha_ultimo_contacto": str(fecha_uc) if pd.notna(fecha_uc) else None,
                "plataforma": row.get('_plataforma'),
            })

        return {"total": total, "total_paginas": total_paginas, "personas": resultado, "stats": stats}

    else:
        # Modo SQLAlchemy
        resultado = []
        with get_db() as db:
            analisis_candidates = AnalisisService.buscar_analisis(
                db,
                fecha_inicio=dt_inicio,
                fecha_fin=dt_fin,
                limit=1000
            )
        for analisis in analisis_candidates:
            persona = analisis.persona
            if not persona:
                continue
            if candidato_ids_owner is not None and persona.candidato_id not in candidato_ids_owner:
                continue
            if busqueda.genero and persona.genero != busqueda.genero:
                continue
            if busqueda.edad_min and (not persona.edad or persona.edad < busqueda.edad_min):
                continue
            if busqueda.edad_max and (not persona.edad or persona.edad > busqueda.edad_max):
                continue
            if busqueda.ubicacion and (not persona.ubicacion or busqueda.ubicacion.lower() not in persona.ubicacion.lower()):
                continue
            if busqueda.intereses:
                p_intereses = [i.categoria for i in persona.intereses]
                if not any(i in p_intereses for i in busqueda.intereses):
                    continue
            intereses = []
            try:
                if analisis.categorias:
                    intereses = json.loads(analisis.categorias)
                elif persona.intereses:
                    intereses = [i.categoria for i in persona.intereses]
            except:
                intereses = []
            resultado.append({
                "id": persona.id,
                "analisis_id": analisis.id,
                "nombre_completo": persona.nombre_completo,
                "edad": persona.edad,
                "genero": persona.genero,
                "telefono": persona.telefono,
                "email": persona.email,
                "ocupacion": persona.ocupacion,
                "ubicacion": persona.ubicacion,
                "facebook_username": persona.facebook_username,
                "instagram_username": persona.instagram_username,
                "intereses": intereses,
                "resumen_conversacion": analisis.resumen,
                "fecha_primer_contacto": persona.fecha_primer_contacto,
                "fecha_ultimo_contacto": analisis.start_conversation or analisis.fecha_analisis,
                "plataforma": (
                    "instagram" if getattr(persona, "instagram_id", None) else
                    "messenger" if getattr(persona, "facebook_id", None) else
                    "whatsapp" if getattr(persona, "telefono", None) else None
                ),
            })
        generos = [p["genero"] or "No especificado" for p in resultado]
        intereses_flat = [i for p in resultado for i in p["intereses"]]
        stats = {
            "por_genero": dict(Counter(generos)),
            "por_interes": dict(Counter(intereses_flat))
        }
        total_paginas = max(1, (len(resultado) + page_size - 1) // page_size)
        return {
            "total": len(resultado),
            "total_paginas": total_paginas,
            "personas": resultado[page * page_size: (page + 1) * page_size],
            "stats": stats
        }
        


@app.post("/api/personas/exportar")
def exportar_personas(busqueda: BusquedaRequest):
    """Exportar sesiones a CSV según criterios."""
    # 1. Parsear fechas
    dt_inicio = None
    dt_fin = None
    if busqueda.fecha_inicio:
        try: dt_inicio = datetime.fromisoformat(busqueda.fecha_inicio)
        except: pass
    if busqueda.fecha_fin:
        try: dt_fin = datetime.fromisoformat(busqueda.fecha_fin)
        except: pass
            
    # 2. Obtener todos los análisis (limit alto)
    if USE_DATAFRAMES:
        analisis_candidates = AnalisisService.buscar_analisis(
            fecha_inicio=dt_inicio, 
            fecha_fin=dt_fin,
            limit=2000 
        )
    else:
        with get_db() as db:
            analisis_candidates = AnalisisService.buscar_analisis(
                db, 
                fecha_inicio=dt_inicio, 
                fecha_fin=dt_fin,
                limit=2000 
            )
        
    data = []
    candidato_ids_owner = _get_candidato_ids_por_owner(busqueda.facebook_user_id)
    
    if USE_DATAFRAMES:
        for analisis in analisis_candidates:
            persona = PersonaService.obtener_persona_por_id(analisis['persona_id'])
            if not persona: continue

            # Filtro por propietario
            if candidato_ids_owner is not None and persona.get('candidato_id') not in candidato_ids_owner: continue
            
            # Filtros demográficos
            if busqueda.genero and persona.get('genero') != busqueda.genero: continue
            if busqueda.edad_min and (not persona.get('edad') or pd.isna(persona['edad']) or persona['edad'] < busqueda.edad_min): continue
            if busqueda.edad_max and (not persona.get('edad') or pd.isna(persona['edad']) or persona['edad'] > busqueda.edad_max): continue
            if busqueda.ubicacion and (not persona.get('ubicacion') or busqueda.ubicacion.lower() not in persona['ubicacion'].lower()): continue
            
            # Intereses filter
            intereses = []
            try:
                if analisis.get('categorias'): intereses = json.loads(analisis['categorias'])
            except: pass
            
            if busqueda.intereses:
                if not any(i in intereses for i in busqueda.intereses): continue

            data.append({
                "ID Persona": persona['id'],
                "ID Sesión": analisis['id'],
                "Inicio Conversación": (analisis.get('start_conversation') or analisis.get('fecha_analisis')),
                "Resumen": analisis.get('resumen') or "",
                "Nombre Completo": persona.get('nombre_completo') or "",
                "Usuario Facebook": persona.get('facebook_username') or "",
                "Usuario Instagram": persona.get('instagram_username') or "",
                "Edad": persona.get('edad') or "",
                "Género": persona.get('genero') or "",
                "Ubicación": persona.get('ubicacion') or "",
                "Email": persona.get('email') or "",
            })
    else:
        for analisis in analisis_candidates:
            persona = analisis.persona

            # Filtro por propietario
            if candidato_ids_owner is not None and persona.candidato_id not in candidato_ids_owner: continue
            
            # Filtros demográficos
            if busqueda.genero and persona.genero != busqueda.genero: continue
            if busqueda.edad_min and (not persona.edad or persona.edad < busqueda.edad_min): continue
            if busqueda.edad_max and (not persona.edad or persona.edad > busqueda.edad_max): continue
            if busqueda.ubicacion and (not persona.ubicacion or busqueda.ubicacion.lower() not in persona.ubicacion.lower()): continue
            if busqueda.intereses:
                 p_intereses = [i.categoria for i in persona.intereses]
                 if not any(i in p_intereses for i in busqueda.intereses): continue
            
            data.append({
                "ID Persona": persona.id,
                "ID Sesión": analisis.id,
                "Inicio Conversación": (analisis.start_conversation or analisis.fecha_analisis).strftime("%Y-%m-%d %H:%M:%S"),
                "Resumen": analisis.resumen or "",
                "Nombre Completo": persona.nombre_completo or "",
                "Usuario Facebook": persona.facebook_username or "",
                "Usuario Instagram": persona.instagram_username or "",
                "Edad": persona.edad or "",
                "Género": persona.genero or "",
                "Ubicación": persona.ubicacion or "",
                "Email": persona.email or "",
            })
        
    df = pd.DataFrame(data)
    
    # Guardar CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sesiones_export_{timestamp}.csv"
    filepath = config.EXPORTS_DIR / filename
    
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    
    return {
        "message": "Exportación exitosa",
        "filename": filename,
        "filepath": str(filepath),
        "total_registros": len(data)
    }


@app.get("/api/analisis/{analisis_id}/conversacion")
def obtener_conversacion(analisis_id: int):
    """Obtener los mensajes de una conversación/análisis específico."""
    if USE_DATAFRAMES:
        analisis = AnalisisService.obtener_por_id(analisis_id)
        if not analisis:
            raise HTTPException(status_code=404, detail="Análisis no encontrado")
        
        persona = PersonaService.obtener_persona_por_id(analisis['persona_id'])
        
        mensajes_texto = []
        if analisis.get('contenido_completo'):
            lineas = analisis['contenido_completo'].split('\n')
            mensajes_texto = [linea.strip() for linea in lineas if linea.strip()]
        
        conversaciones = ConversacionService.obtener_historial(analisis['persona_id'], limit=100)
        
        mensajes_detallados = []
        for conv in conversaciones:
            mensajes_detallados.append({
                "mensaje": conv['mensaje'],
                "fecha": conv['fecha_mensaje'].isoformat() if hasattr(conv['fecha_mensaje'], 'isoformat') else str(conv['fecha_mensaje']),
                "es_enviado": bool(conv['es_enviado']),
                "plataforma": conv['plataforma']
            })
            
        return {
            "analisis_id": analisis['id'],
            "persona_id": analisis['persona_id'],
            "persona_nombre": persona.get('nombre_completo') if persona else "Usuario",
            "resumen": analisis['resumen'],
            "start_conversation": analisis['start_conversation'].isoformat() if hasattr(analisis['start_conversation'], 'isoformat') else str(analisis['start_conversation']),
            "fecha_analisis": analisis['fecha_analisis'].isoformat() if hasattr(analisis['fecha_analisis'], 'isoformat') else str(analisis['fecha_analisis']),
            "mensajes": mensajes_detallados if mensajes_detallados else [
                {"mensaje": texto, "fecha": str(analisis['fecha_analisis']), "es_enviado": False, "plataforma": ""}
                for texto in mensajes_texto
            ]
        }
    else:
        with get_db() as db:
            analisis = db.query(Analisis).filter(Analisis.id == analisis_id).first()
            
            if not analisis:
                raise HTTPException(status_code=404, detail="Análisis no encontrado")
            
            # Parsear el contenido completo para extraer mensajes individuales
            # Si el contenido_completo tiene mensajes separados por \n, los dividimos
            mensajes_texto = []
            if analisis.contenido_completo:
                # Dividir por líneas y limpiar
                lineas = analisis.contenido_completo.split('\n')
                mensajes_texto = [linea.strip() for linea in lineas if linea.strip()]
            
            # Obtener también las conversaciones individuales de esta persona
            # para tener más contexto
            conversaciones = db.query(Conversacion)\
                .filter(Conversacion.persona_id == analisis.persona_id)\
                .order_by(Conversacion.fecha_mensaje.asc())\
                .all()
            
            mensajes_detallados = []
            for conv in conversaciones:
                mensajes_detallados.append({
                    "mensaje": conv.mensaje,
                    "fecha": conv.fecha_mensaje.isoformat(),
                    "es_enviado": bool(conv.es_enviado),
                    "plataforma": conv.plataforma
                })
            
            return {
                "analisis_id": analisis.id,
                "persona_id": analisis.persona_id,
                "persona_nombre": analisis.persona.nombre_completo if analisis.persona else "Usuario",
                "resumen": analisis.resumen,
                "start_conversation": (analisis.start_conversation or analisis.fecha_analisis).isoformat(),
                "fecha_analisis": analisis.fecha_analisis.isoformat(),
                "mensajes": mensajes_detallados if mensajes_detallados else [
                    {"mensaje": texto, "fecha": analisis.fecha_analisis.isoformat(), "es_enviado": False, "plataforma": ""}
                    for texto in mensajes_texto
                ]
            }


@app.post("/api/conversaciones/{analisis_id}/responder")
def responder_conversacion(analisis_id: int, reply: ReplyRequest):
    """
    Enviar una respuesta manual a una conversación desde el dashboard.
    Soporta Facebook Messenger e Instagram Direct.
    Guarda el mensaje enviado en la base de datos.
    """
    texto = (reply.texto or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="El texto de la respuesta no puede estar vacío")

    try:
        if USE_DATAFRAMES:
            analisis = AnalisisService.obtener_por_id(analisis_id)
            if not analisis:
                raise HTTPException(status_code=404, detail="Análisis no encontrado")
            persona = PersonaService.obtener_persona_por_id(analisis['persona_id'])
            if not persona:
                raise HTTPException(status_code=404, detail="Persona no encontrada")
            plataforma = persona.get('plataforma', '')
            facebook_id = persona.get('facebook_id')
            instagram_id = persona.get('instagram_id')
            candidato_id = persona.get('candidato_id')
            persona_id = analisis['persona_id']

            if plataforma == 'instagram' and instagram_id:
                recipient_id = instagram_id
            elif facebook_id:
                recipient_id = facebook_id
                plataforma = 'facebook'
            else:
                raise HTTPException(status_code=400, detail="No se encontró ID de destinatario. Solo Facebook Messenger e Instagram Direct son soportados.")

            cliente = meta_client
            if candidato_id:
                candidato = CandidatoService.obtener_candidato_por_id(candidato_id)
                if candidato and candidato.get('facebook_page_access_token'):
                    cliente = crear_cliente_candidato(
                        candidato['facebook_page_access_token'],
                        instagram_token=candidato.get('instagram_access_token')
                    )

            resultado = cliente.enviar_mensaje_simple(recipient_id, texto, plataforma)
            if not resultado:
                raise HTTPException(status_code=502, detail="Error al enviar el mensaje a través de la API de Meta")

            ConversacionService.guardar_conversacion(
                persona_id=persona_id,
                plataforma=plataforma,
                mensaje=texto,
                es_enviado=True,
                fecha_mensaje=datetime.utcnow()
            )

        else:
            with get_db() as db:
                analisis = db.query(Analisis).filter(Analisis.id == analisis_id).first()
                if not analisis:
                    raise HTTPException(status_code=404, detail="Análisis no encontrado")
                persona = analisis.persona
                if not persona:
                    raise HTTPException(status_code=404, detail="Persona no encontrada")
                plataforma = persona.plataforma or ''
                facebook_id = persona.facebook_id
                instagram_id = persona.instagram_id
                candidato_id = persona.candidato_id
                persona_id = persona.id

                if plataforma == 'instagram' and instagram_id:
                    recipient_id = instagram_id
                elif facebook_id:
                    recipient_id = facebook_id
                    plataforma = 'facebook'
                else:
                    raise HTTPException(status_code=400, detail="No se encontró ID de destinatario. Solo Facebook Messenger e Instagram Direct son soportados.")

                cliente = meta_client
                if candidato_id:
                    candidato = CandidatoService.obtener_candidato_por_id(candidato_id)
                    if candidato and candidato.get('facebook_page_access_token'):
                        cliente = crear_cliente_candidato(
                            candidato['facebook_page_access_token'],
                            instagram_token=candidato.get('instagram_access_token')
                        )

                resultado = cliente.enviar_mensaje_simple(recipient_id, texto, plataforma)
                if not resultado:
                    raise HTTPException(status_code=502, detail="Error al enviar el mensaje a través de la API de Meta")

                ConversacionService.guardar_conversacion(
                    db,
                    persona_id=persona_id,
                    plataforma=plataforma,
                    mensaje=texto,
                    es_enviado=True,
                    fecha_mensaje=datetime.utcnow()
                )

        print(f"✅ Respuesta enviada desde dashboard a {recipient_id} ({plataforma}): '{texto[:50]}...'")
        return {"ok": True, "message": "Mensaje enviado correctamente", "recipient_id": recipient_id}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error enviando respuesta desde dashboard: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mensajes/procesar")
def procesar_mensaje(mensaje_data: MensajeCreate):
    """
    Procesar un mensaje y extraer información estructurada.
    Crea o actualiza la persona en la base de datos.
    """
    with get_db() as db:
        try:
            # Buscar persona existente
            persona_id = None
            if USE_DATAFRAMES:
                from backend.database.dataframe_storage import get_storage
                storage = get_storage()
                if mensaje_data.facebook_id:
                    mask = storage.personas_df['facebook_id'] == mensaje_data.facebook_id
                    if mask.any():
                        persona_id = storage.personas_df[mask].iloc[0]['id']
                elif mensaje_data.instagram_id:
                    mask = storage.personas_df['instagram_id'] == mensaje_data.instagram_id
                    if mask.any():
                        persona_id = storage.personas_df[mask].iloc[0]['id']
            else:
                if mensaje_data.facebook_id:
                    persona = db.query(Persona).filter(
                        Persona.facebook_id == mensaje_data.facebook_id
                    ).first()
                    if persona:
                        persona_id = persona.id
                elif mensaje_data.instagram_id:
                    persona = db.query(Persona).filter(
                        Persona.instagram_id == mensaje_data.instagram_id
                    ).first()
                    if persona:
                        persona_id = persona.id
            
            # Obtener historial si existe la persona
            historial = []
            if persona_id:
                if USE_DATAFRAMES:
                    conversaciones = ConversacionService.obtener_historial(persona_id, limit=10)
                    historial = [c['mensaje'] for c in conversaciones]
                else:
                    conversaciones = ConversacionService.obtener_historial(db, persona_id, limit=10)
                    historial = [c.mensaje for c in conversaciones]
            
            # Procesar mensaje con el agente
            resultado = procesar_conversacion(
                mensaje=mensaje_data.mensaje,
                plataforma=mensaje_data.plataforma,
                persona_id=persona_id,
                historial=historial
            )
            
            # Crear o actualizar persona con los datos extraídos
            if resultado.get("datos_extraidos"):
                if USE_DATAFRAMES:
                    persona = PersonaService.crear_o_actualizar_persona(
                        datos=resultado["datos_extraidos"],
                        facebook_id=mensaje_data.facebook_id,
                        instagram_id=mensaje_data.instagram_id
                    )
                    
                    # Guardar conversación
                    ConversacionService.guardar_conversacion(
                        persona_id=persona['id'],
                        mensaje=mensaje_data.mensaje,
                        plataforma=mensaje_data.plataforma,
                        es_enviado=False,
                        datos_extraidos=resultado["datos_extraidos"]
                    )
                    
                    return {
                        "success": True,
                        "persona_id": persona['id'],
                        "datos_extraidos": resultado["datos_extraidos"],
                        "necesita_mas_info": resultado.get("necesita_mas_info", False)
                    }
                else:
                    persona = PersonaService.crear_o_actualizar_persona(
                        db,
                        datos=resultado["datos_extraidos"],
                        facebook_id=mensaje_data.facebook_id,
                        instagram_id=mensaje_data.instagram_id
                    )
                    
                    # Guardar conversación
                    ConversacionService.guardar_conversacion(
                        db,
                        persona_id=persona.id,
                        mensaje=mensaje_data.mensaje,
                        plataforma=mensaje_data.plataforma,
                        es_enviado=False,
                        datos_extraidos=resultado["datos_extraidos"]
                    )
                    
                    return {
                        "success": True,
                        "persona_id": persona.id,
                        "datos_extraidos": resultado["datos_extraidos"],
                        "necesita_mas_info": resultado.get("necesita_mas_info", False)
                    }
            else:
                return {
                    "success": False,
                    "error": resultado.get("error", "No se pudieron extraer datos"),
                    "datos_extraidos": {}
                }
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversaciones/{persona_id}")
def obtener_conversaciones(
    persona_id: int,
    limit: int = Query(50, ge=1, le=200)
):
    """Obtener historial de conversaciones de una persona."""
    persona = PersonaService.obtener_persona_por_id(persona_id)
    
    if not persona:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    
    conversaciones = ConversacionService.obtener_historial(persona_id, limit)
    
    return {
        "persona_id": persona_id,
        "nombre": persona.get('nombre_completo') if USE_DATAFRAMES else persona.nombre_completo,
        "total": len(conversaciones),
        "conversaciones": [
            {
                "id": c['id'] if USE_DATAFRAMES else c.id,
                "mensaje": c['mensaje'] if USE_DATAFRAMES else c.mensaje,
                "plataforma": c['plataforma'] if USE_DATAFRAMES else c.plataforma,
                "es_enviado": bool(c['es_enviado']) if USE_DATAFRAMES else bool(c.es_enviado),
                "fecha": c['fecha_mensaje'].isoformat() if USE_DATAFRAMES else c.fecha_mensaje.isoformat()
            }
            for c in conversaciones
        ]
    }


@app.get("/api/stats")
def obtener_estadisticas(owner_facebook_user_id: Optional[str] = Query(None)):
    """Obtener estadísticas generales del sistema, filtradas por propietario si se indica."""
    if USE_DATAFRAMES:
        from backend.database.dataframe_storage import get_storage
        storage = get_storage()

        personas_df = storage.personas_df
        conversaciones_df = storage.conversaciones_df

        # Filtrar por candidatos del usuario autenticado
        if owner_facebook_user_id:
            candidato_ids = set(CandidatoService.listar_candidatos_por_owner(owner_facebook_user_id))
            if 'candidato_id' in personas_df.columns:
                personas_df = personas_df[personas_df['candidato_id'].isin(candidato_ids)]
            persona_ids = set(personas_df['id'].tolist())
            if not conversaciones_df.empty and 'persona_id' in conversaciones_df.columns:
                conversaciones_df = conversaciones_df[conversaciones_df['persona_id'].isin(persona_ids)]

        total_personas = len(personas_df)
        total_conversaciones = len(conversaciones_df)
        
        # Estadísticas por género
        from collections import Counter
        generos = personas_df['genero'].fillna("No especificado").tolist()
        stats_genero = dict(Counter(generos))
        
        # Estadísticas por interés
        stats_intereses = {}
        if not storage.persona_interes_df.empty and not storage.intereses_df.empty:
            persona_ids = set(personas_df['id'].tolist())
            rel_df = storage.persona_interes_df[storage.persona_interes_df['persona_id'].isin(persona_ids)]
            if not rel_df.empty:
                merged = rel_df.merge(storage.intereses_df, left_on='interes_id', right_on='id')
                stats_intereses = dict(Counter(merged['categoria'].tolist()))
        
        return {
            "total_personas": total_personas,
            "total_conversaciones": total_conversaciones,
            "por_genero": stats_genero,
            "por_interes": stats_intereses
        }
    else:
        with get_db() as db:
            if owner_facebook_user_id:
                candidato_ids = CandidatoService.listar_candidatos_por_owner(owner_facebook_user_id)
                persona_ids = [p.id for p in db.query(Persona.id).filter(Persona.candidato_id.in_(candidato_ids)).all()]
                total_personas = len(persona_ids)
                total_conversaciones = db.query(Conversacion).filter(Conversacion.persona_id.in_(persona_ids)).count()
            else:
                total_personas = db.query(Persona).count()
                total_conversaciones = db.query(Conversacion).count()
            
            # Estadísticas por género
            stats_genero = {}
            for genero in config.GENEROS:
                if owner_facebook_user_id:
                    count = db.query(Persona).filter(Persona.genero == genero, Persona.candidato_id.in_(candidato_ids)).count()
                else:
                    count = db.query(Persona).filter(Persona.genero == genero).count()
                stats_genero[genero] = count
            
            # Estadísticas por interés
            stats_intereses = {}
            for interes in db.query(Interes).all():
                count = len(interes.personas)
                stats_intereses[interes.categoria] = count
            
            return {
                "total_personas": total_personas,
                "total_conversaciones": total_conversaciones,
                "por_genero": stats_genero,
                "por_interes": stats_intereses
            }


@app.get("/api/eventos")
def obtener_eventos():
    """Obtener lista de todos los eventos disponibles."""
    eventos = EventoService.obtener_todos()
    return [
        {
            "id": e['id'] if USE_DATAFRAMES else e.id,
            "nombre": e['nombre'] if USE_DATAFRAMES else e.nombre,
            "descripcion": e['descripcion'] if USE_DATAFRAMES else e.descripcion
        }
        for e in eventos
    ]


@app.put("/api/analisis/{analisis_id}/evento")
def actualizar_evento_analisis(
    analisis_id: int,
    evento_id: Optional[int] = None,
    evento_nombre: Optional[str] = None
):
    """
    Actualizar el evento asociado a un análisis.
    Puede recibir evento_id o evento_nombre (para crear uno nuevo).
    """
    analisis = AnalisisService.obtener_por_id(analisis_id)
    
    if not analisis:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")
    
    result_evento_id = None
    # Si se especificó un ID de evento
    if evento_id is not None:
        if evento_id == 0:  # 0 significa "sin evento"
            AnalisisService.actualizar_evento(analisis_id, None)
            evento_nombre_resultado = None
            result_evento_id = None
        else:
            evento = EventoService.obtener_por_id(evento_id)
            if not evento:
                raise HTTPException(status_code=404, detail="Evento no encontrado")
            AnalisisService.actualizar_evento(analisis_id, evento_id)
            evento_nombre_resultado = evento['nombre']
            result_evento_id = evento_id
    
    # Si se especificó un nombre de evento nuevo (para "Otros")
    elif evento_nombre:
        # Buscar si ya existe
        evento = EventoService.obtener_por_nombre(evento_nombre)
        if not evento:
            # Crear nuevo evento
            evento = EventoService.crear_evento(evento_nombre, "Evento personalizado")
        AnalisisService.actualizar_evento(analisis_id, evento['id'])
        evento_nombre_resultado = evento['nombre']
        result_evento_id = evento['id']
    else:
        evento_nombre_resultado = None

    # Force reload from disk to ensure other readers (and subsequent GETs) see the latest parquet files.
    if USE_DATAFRAMES:
        from backend.database.dataframe_storage import get_storage
        try:
            get_storage().reload_from_disk()
        except Exception:
            # silently ignore reload errors; the update itself was performed
            pass

    return {
        "success": True,
        "analisis_id": analisis_id,
        "evento_id": result_evento_id,
        "evento_nombre": evento_nombre_resultado
    }


# === Webhooks para Facebook e Instagram ===

@app.get("/webhook")
async def verify_meta_webhook(request: Request):
    """
    Endpoint de verificación para el Webhook de Meta (Facebook/Instagram).
    Valida el token y devuelve el challenge.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == config.META_VERIFY_TOKEN:
            print("✅ META_WEBHOOK_VERIFIED")
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Meta verification failed")
    
    return {"status": "ok"}


@app.post("/webhook")
async def meta_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """
    Manejar eventos de mensajes entrantes de Facebook e Instagram.
    """
    try:
        body = await request.json()
        
        # Facebook Messenger
        if body.get("object") == "page":
            for entry in body.get("entry", []):
                messaging_events = entry.get("messaging", [])
                for event in messaging_events:
                    sender_id = event.get("sender", {}).get("id")
                    recipient_id = event.get("recipient", {}).get("id")
                    
                    # Mensaje normal
                    if "message" in event:
                        message = event["message"]
                        
                        # Mensaje borrado por usuario (unsent)
                        if message.get("is_deleted") or message.get("is_echo"):
                            if message.get("is_deleted"):
                                message_id = message.get("mid")
                                background_tasks.add_task(
                                    procesar_mensaje_borrado,
                                    sender_id,
                                    message_id,
                                    "facebook"
                                )
                        # Mensaje de texto normal
                        elif message.get("text"):
                            texto = message["text"]
                            message_id = message.get("mid")
                            
                            background_tasks.add_task(
                                procesar_mensaje_meta,
                                sender_id,
                                texto,
                                "facebook",
                                message_id
                            )
                    
                    # Postback (usuario hizo clic en quick reply o botón)
                    elif "postback" in event:
                        postback = event["postback"]
                        payload = postback.get("payload", "")
                        title = postback.get("title", "")
                        
                        background_tasks.add_task(
                            procesar_postback,
                            sender_id,
                            payload,
                            title,
                            "facebook"
                        )
            
            return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)
        
        # Instagram Direct
        elif body.get("object") == "instagram":
            for entry in body.get("entry", []):
                messaging_events = entry.get("messaging", [])
                for event in messaging_events:
                    sender_id = event.get("sender", {}).get("id")
                    recipient_id = event.get("recipient", {}).get("id")
                    
                    # Mensaje normal
                    if "message" in event:
                        message = event["message"]
                        
                        # Mensaje borrado (Instagram usa is_unsupported)
                        if message.get("is_unsupported"):
                            message_id = message.get("mid")
                            background_tasks.add_task(
                                procesar_mensaje_borrado,
                                sender_id,
                                message_id,
                                "instagram"
                            )
                        # Mensaje de texto normal
                        elif message.get("text"):
                            texto = message["text"]
                            message_id = message.get("mid")
                            
                            background_tasks.add_task(
                                procesar_mensaje_meta,
                                sender_id,
                                texto,
                                "instagram",
                                message_id
                            )
                    
                    # Postback
                    elif "postback" in event:
                        postback = event["postback"]
                        payload = postback.get("payload", "")
                        title = postback.get("title", "")
                        
                        background_tasks.add_task(
                            procesar_postback,
                            sender_id,
                            payload,
                            title,
                            "instagram"
                        )
            
            return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)
        
        # Evento no soportado
        return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)
        
    except Exception as e:
        print(f"❌ Error en webhook Meta: {e}")
        import traceback
        traceback.print_exc()
        return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)


def procesar_mensaje_meta(sender_id: str, texto: str, plataforma: str, message_id: str):
    """
    Procesar mensaje de Facebook o Instagram con respuestas automáticas.
    """
    try:
        # Buscar o crear persona
        if USE_DATAFRAMES:
            if plataforma == "facebook":
                # Buscar método para Facebook ID
                from backend.database.dataframe_storage import get_storage
                storage = get_storage()
                mask = storage.personas_df['facebook_id'] == sender_id
                if mask.any():
                    persona = storage.personas_df[mask].iloc[0].to_dict()
                else:
                    persona = None
            else:  # instagram
                from backend.database.dataframe_storage import get_storage
                storage = get_storage()
                mask = storage.personas_df['instagram_id'] == sender_id
                if mask.any():
                    persona = storage.personas_df[mask].iloc[0].to_dict()
                else:
                    persona = None
            
            if not persona:
                # Crear nueva persona
                datos = {}
                if plataforma == "facebook":
                    persona = PersonaService.crear_o_actualizar_persona(
                        datos=datos,
                        facebook_id=sender_id
                    )
                else:
                    persona = PersonaService.crear_o_actualizar_persona(
                        datos=datos,
                        instagram_id=sender_id
                    )
            
            persona_id = persona['id']
            es_primer_mensaje = not persona.get('nombre_completo')
            
            # Obtener historial
            historial = ConversacionService.obtener_historial_por_persona(persona_id, limit=10)
            historial_mensajes = [c['mensaje'] for c in historial]
            
        else:
            # Modo SQLAlchemy
            with get_db() as db:
                if plataforma == "facebook":
                    persona = db.query(Persona).filter(Persona.facebook_id == sender_id).first()
                else:
                    persona = db.query(Persona).filter(Persona.instagram_id == sender_id).first()
                
                es_primer_mensaje = persona is None or not persona.nombre_completo
                
                if not persona:
                    datos = {}
                    if plataforma == "facebook":
                        persona = PersonaService.crear_o_actualizar_persona(
                            db,
                            datos=datos,
                            facebook_id=sender_id
                        )
                    else:
                        persona = PersonaService.crear_o_actualizar_persona(
                            db,
                            datos=datos,
                            instagram_id=sender_id
                        )
                
                persona_id = persona.id if not USE_DATAFRAMES else persona['id']
                
                conversaciones = ConversacionService.obtener_historial(db, persona_id, limit=10)
                historial_mensajes = [c.mensaje for c in conversaciones]
        
        # Procesar con Agente IA
        resultado = procesar_conversacion(
            mensaje=texto,
            plataforma=plataforma,
            persona_id=persona_id,
            historial=historial_mensajes
        )
        
        # Guardar resultados
        if resultado.get("datos_extraidos"):
            if USE_DATAFRAMES:
                if plataforma == "facebook":
                    PersonaService.crear_o_actualizar_persona(
                        datos=resultado["datos_extraidos"],
                        facebook_id=sender_id
                    )
                else:
                    PersonaService.crear_o_actualizar_persona(
                        datos=resultado["datos_extraidos"],
                        instagram_id=sender_id
                    )
                
                ConversacionService.guardar_conversacion(
                    persona_id=persona_id,
                    mensaje=texto,
                    plataforma=plataforma,
                    es_enviado=False,
                    datos_extraidos=resultado["datos_extraidos"],
                    mensaje_id=message_id
                )
            else:
                with get_db() as db:
                    if plataforma == "facebook":
                        PersonaService.crear_o_actualizar_persona(
                            db,
                            datos=resultado["datos_extraidos"],
                            facebook_id=sender_id
                        )
                        persona = db.query(Persona).filter(Persona.facebook_id == sender_id).first()
                    else:
                        PersonaService.crear_o_actualizar_persona(
                            db,
                            datos=resultado["datos_extraidos"],
                            instagram_id=sender_id
                        )
                        persona = db.query(Persona).filter(Persona.instagram_id == sender_id).first()
                    
                    ConversacionService.guardar_conversacion(
                        db,
                        persona_id=persona.id,
                        mensaje=texto,
                        plataforma=plataforma,
                        es_enviado=False,
                        datos_extraidos=resultado["datos_extraidos"]
                    )
            
            # RESPUESTA AUTOMÁTICA CON QUICK REPLIES
            nombre = resultado["datos_extraidos"].get("nombre_completo", "")
            intereses = resultado["datos_extraidos"].get("intereses", [])
            
            # Si es primer mensaje, enviar quick replies con temas
            if es_primer_mensaje or not intereses:
                respuesta_texto = f"¡Hola{' ' + nombre if nombre else ''}! Gracias por contactarnos. ¿Qué tema te interesa más?"
                
                quick_replies = [
                    {"title": "🔒 Seguridad", "payload": "SEGURIDAD"},
                    {"title": "🎓 Educación", "payload": "EDUCACION"},
                    {"title": "🏥 Salud", "payload": "SALUD"},
                    {"title": "💰 Economía", "payload": "ECONOMIA"},
                ]
                
                meta_client.enviar_mensaje_con_quick_replies(
                    sender_id,
                    respuesta_texto,
                    quick_replies,
                    plataforma
                )
            else:
                # Respuesta de confirmación simple
                if nombre:
                    respuesta = f"Gracias {nombre} por compartir tu preocupación"
                else:
                    respuesta = "Gracias por compartir tu preocupación"
                
                if intereses:
                    temas = ", ".join(intereses)
                    respuesta += f" sobre {temas}"
                
                respuesta += ". Un miembro de nuestro equipo revisará tu mensaje pronto."
                
                meta_client.enviar_mensaje_simple(
                    sender_id,
                    respuesta,
                    plataforma
                )
            
            print(f"✅ Mensaje {plataforma} procesado y respondido a {sender_id}")
            
    except Exception as e:
        print(f"❌ Error procesando mensaje {plataforma}: {e}")
        import traceback
        traceback.print_exc()


def procesar_postback(sender_id: str, payload: str, title: str, plataforma: str):
    """
    Procesar cuando usuario hace clic en quick reply, botón o elemento del menú.
    """
    try:
        # Buscar o crear persona
        if USE_DATAFRAMES:
            from backend.database.dataframe_storage import get_storage
            storage = get_storage()
            if plataforma == "facebook":
                mask = storage.personas_df['facebook_id'] == sender_id
            else:
                mask = storage.personas_df['instagram_id'] == sender_id
            
            if mask.any():
                persona = storage.personas_df[mask].iloc[0].to_dict()
                persona_id = persona['id']
            else:
                # Crear nueva persona
                datos = {}
                if plataforma == "facebook":
                    persona = PersonaService.crear_o_actualizar_persona(
                        datos=datos,
                        facebook_id=sender_id
                    )
                else:
                    persona = PersonaService.crear_o_actualizar_persona(
                        datos=datos,
                        instagram_id=sender_id
                    )
                persona_id = persona['id']
        else:
            with get_db() as db:
                if plataforma == "facebook":
                    persona = db.query(Persona).filter(Persona.facebook_id == sender_id).first()
                else:
                    persona = db.query(Persona).filter(Persona.instagram_id == sender_id).first()
                
                if not persona:
                    datos = {}
                    if plataforma == "facebook":
                        persona = PersonaService.crear_o_actualizar_persona(
                            db,
                            datos=datos,
                            facebook_id=sender_id
                        )
                    else:
                        persona = PersonaService.crear_o_actualizar_persona(
                            db,
                            datos=datos,
                            instagram_id=sender_id
                        )
                
                persona_id = persona.id if not USE_DATAFRAMES else persona['id']
        
        # Interpretar payload
        respuesta = ""
        
        # Payloads de intereses (Quick Replies)
        interes_map = {
            "SEGURIDAD": "Seguridad",
            "EDUCACION": "Educación",
            "SALUD": "Salud",
            "ECONOMIA": "Economía",
            "TRANSPORTE": "Transporte",
            "VIVIENDA": "Vivienda",
            "EMPLEO": "Empleo",
            "MEDIO_AMBIENTE": "Medio Ambiente"
        }
        
        if payload in interes_map:
            interes = interes_map[payload]
            
            # Actualizar con el interés seleccionado
            if USE_DATAFRAMES:
                if plataforma == "facebook":
                    PersonaService.crear_o_actualizar_persona(
                        datos={"intereses": [interes]},
                        facebook_id=sender_id
                    )
                else:
                    PersonaService.crear_o_actualizar_persona(
                        datos={"intereses": [interes]},
                        instagram_id=sender_id
                    )
            else:
                with get_db() as db:
                    if plataforma == "facebook":
                        PersonaService.crear_o_actualizar_persona(
                            db,
                            datos={"intereses": [interes]},
                            facebook_id=sender_id
                        )
                    else:
                        PersonaService.crear_o_actualizar_persona(
                            db,
                            datos={"intereses": [interes]},
                            instagram_id=sender_id
                        )
            
            respuesta = f"Perfecto, hemos registrado tu interés en {interes}. ¿Hay algo específico que te preocupe sobre este tema?"
        
        # Payloads del menú persistente/ice breakers
        elif payload == "GET_STARTED":
            respuesta = "¡Hola! Bienvenido. Estoy aquí para escuchar tus preocupaciones. ¿Qué tema te interesa más?"
            
            # Enviar con Quick Replies
            quick_replies = [
                {"title": "🔒 Seguridad", "payload": "SEGURIDAD"},
                {"title": "🎓 Educación", "payload": "EDUCACION"},
                {"title": "🏥 Salud", "payload": "SALUD"},
                {"title": "💰 Economía", "payload": "ECONOMIA"},
            ]
            meta_client.enviar_mensaje_con_quick_replies(sender_id, respuesta, quick_replies, plataforma)
            print(f"✅ Postback GET_STARTED procesado para {sender_id}")
            return
        
        elif payload == "PROPUESTAS":
            respuesta = "Nuestras propuestas se centran en mejorar la seguridad, educación, salud y economía. ¿Qué área te interesa más conocer?"
            
            quick_replies = [
                {"title": "🔒 Seguridad", "payload": "SEGURIDAD"},
                {"title": "🎓 Educación", "payload": "EDUCACION"},
                {"title": "🏥 Salud", "payload": "SALUD"},
                {"title": "💰 Economía", "payload": "ECONOMIA"},
            ]
            meta_client.enviar_mensaje_con_quick_replies(sender_id, respuesta, quick_replies, plataforma)
            print(f"✅ Postback PROPUESTAS procesado para {sender_id}")
            return
        
        elif payload == "APOYAR":
            respuesta = "¡Gracias por tu interés en apoyar! Hay varias formas de colaborar:\n\n1️⃣ Comparte nuestro mensaje\n2️⃣ Únete a nuestros eventos\n3️⃣ Regístrate como voluntario\n\n¿Te gustaría más información sobre alguna opción?"
        
        elif payload == "EVENTOS":
            respuesta = "Estamos organizando eventos próximamente. ¿Te gustaría recibir notificaciones cuando haya un evento en tu área? Si es así, comparte tu ubicación o ciudad."
        
        elif payload == "CONTACTO":
            respuesta = "Gracias por querer contactarnos. ¿Cuál es tu preocupación principal? Compártela libremente y un miembro de nuestro equipo te responderá pronto."
        
        else:
            # Payload desconocido, tratar como mensaje de texto
            respuesta = f"Gracias por tu interés en '{title}'. ¿Hay algo específico que te gustaría compartir?"
        
        # Enviar respuesta simple
        if respuesta:
            meta_client.enviar_mensaje_simple(sender_id, respuesta, plataforma)
            print(f"✅ Postback {payload} procesado para {sender_id}")
        
    except Exception as e:
        print(f"❌ Error procesando postback: {e}")
        import traceback
        traceback.print_exc()


def procesar_mensaje_borrado(sender_id: str, message_id: str, plataforma: str):
    """
    Eliminar datos cuando usuario borra un mensaje (respeto a privacidad).
    """
    try:
        if USE_DATAFRAMES:
            from backend.database.dataframe_storage import get_storage
            storage = get_storage()
            
            # Buscar persona
            if plataforma == "facebook":
                mask = storage.personas_df['facebook_id'] == sender_id
            else:
                mask = storage.personas_df['instagram_id'] == sender_id
            
            if mask.any():
                persona = storage.personas_df[mask].iloc[0].to_dict()
                persona_id = persona['id']
                
                # Buscar conversación con ese message_id
                conv_mask = (storage.conversaciones_df['persona_id'] == persona_id) & \
                           (storage.conversaciones_df.get('mensaje_id', pd.Series()) == message_id)
                
                if conv_mask.any():
                    # Eliminar la conversación
                    storage.conversaciones_df = storage.conversaciones_df[~conv_mask]
                    storage.save_conversaciones()
                    
                    print(f"✅ Mensaje {message_id} borrado, datos eliminados (privacidad respetada)")
        else:
            with get_db() as db:
                # Buscar persona
                if plataforma == "facebook":
                    persona = db.query(Persona).filter(Persona.facebook_id == sender_id).first()
                else:
                    persona = db.query(Persona).filter(Persona.instagram_id == sender_id).first()
                
                if persona:
                    # Buscar conversación con ese message_id
                    conversacion = db.query(Conversacion).filter(
                        Conversacion.persona_id == persona.id,
                        Conversacion.mensaje_id == message_id
                    ).first()
                    
                    if conversacion:
                        db.delete(conversacion)
                        db.commit()
                        print(f"✅ Mensaje {message_id} borrado, datos eliminados (privacidad respetada)")
    
    except Exception as e:
        print(f"❌ Error procesando mensaje borrado: {e}")
        import traceback
        traceback.print_exc()


# === Webhook para WhatsApp Business ===

@app.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(request: Request):
    """
    Endpoint de verificación para el Webhook de WhatsApp.
    Valida el token y devuelve el challenge.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == config.WHATSAPP_VERIFY_TOKEN:
            print("✅ WHATSAPP_WEBHOOK_VERIFIED")
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="WhatsApp verification failed")
    
    return {"status": "ok"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """
    Manejar eventos de mensajes entrantes de WhatsApp.
    """
    try:
        body = await request.json()
        
        # Procesar con el cliente de WhatsApp
        data = whatsapp_client.procesar_webhook_whatsapp(body)
        
        if data and data.get("message"):
            # Es un mensaje entrante
            phone = data.get("phone")
            message = data.get("message")
            message_id = data.get("message_id")
            username = data.get("username")
            phone_number_id = data.get("phone_number_id", "")
            
            # Procesar en background
            background_tasks.add_task(
                procesar_mensaje_whatsapp,
                phone,
                message,
                username,
                message_id,
                phone_number_id
            )
            
            return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)
        
        # Si es un cambio de estado (leído, entregado, etc), simplemente aceptar
        return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)
            
    except Exception as e:
        print(f"❌ Error en webhook WhatsApp: {e}")
        import traceback
        traceback.print_exc()
        # Siempre devolver 200 para evitar reintentos
        return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)


def procesar_mensaje_whatsapp(phone: str, texto: str, username: str, message_id: str, phone_number_id: str = ""):
    """
    Procesar mensaje de WhatsApp en background con respuestas automáticas.
    """
    # Resolver candidato dueño del número WA
    candidato_id_wsp = None
    if phone_number_id:
        try:
            candidato = CandidatoService.obtener_candidato_por_whatsapp_phone_id(phone_number_id)
            if candidato:
                candidato_id_wsp = candidato.get('id')
                print(f"[WSP-PROC] Candidato: '{candidato.get('nombre')}' | phone_number_id={phone_number_id} | candidato_id={candidato_id_wsp}")
            else:
                print(f"[WSP-PROC] ⚠️ No se encontró candidato para phone_number_id={phone_number_id}")
        except Exception as e_cand:
            print(f"[WSP-PROC] ⚠️ Error buscando candidato: {e_cand}")

    try:
        # Detectar si es un click en botón de interés
        interes_map = {
            "🔒 Seguridad": "Seguridad",
            "🎓 Educación": "Educación",
            "🏥 Salud": "Salud",
            "💰 Economía": "Economía",
            "🚌 Transporte": "Transporte",
            "🏠 Vivienda": "Vivienda",
            "💼 Empleo": "Empleo",
            "🌳 Medio Ambiente": "Medio Ambiente"
        }
        
        interes_seleccionado = interes_map.get(texto)
        
        # Buscar o crear persona por teléfono
        if USE_DATAFRAMES:
            persona = PersonaService.obtener_por_telefono(phone)
            
            if not persona:
                # Crear nueva persona
                datos = {"telefono": phone}
                if username:
                    datos["nombre_completo"] = username
                if candidato_id_wsp:
                    datos["candidato_id"] = candidato_id_wsp
                persona = PersonaService.crear_o_actualizar_persona(
                    datos=datos,
                    telefono=phone
                )
            elif candidato_id_wsp and not persona.get('candidato_id'):
                # Asignar candidato_id a persona existente que no lo tenga
                PersonaService.crear_o_actualizar_persona(
                    datos={"candidato_id": candidato_id_wsp},
                    telefono=phone
                )
                persona['candidato_id'] = candidato_id_wsp
            
            persona_id = persona['id']
            
            # Si es click en botón, actualizar interés directamente
            if interes_seleccionado:
                PersonaService.crear_o_actualizar_persona(
                    datos={"intereses": [interes_seleccionado]},
                    telefono=phone
                )
                
                # Enviar respuesta de confirmación
                respuesta = f"Perfecto, hemos registrado tu interés en {interes_seleccionado}. ¿Hay algo específico que te preocupe sobre este tema?"
                whatsapp_client.enviar_mensaje(phone, respuesta)
                
                # Guardar conversación
                ConversacionService.guardar_conversacion(
                    persona_id=persona_id,
                    mensaje=texto,
                    plataforma="whatsapp",
                    es_enviado=False,
                    datos_extraidos={"intereses": [interes_seleccionado]}
                )
                
                whatsapp_client.marcar_como_leido(message_id)
                print(f"✅ Interés {interes_seleccionado} registrado para {phone}")
                return
            
            # Obtener historial para procesamiento normal
            historial = ConversacionService.obtener_historial_por_persona(persona_id, limit=10)
            historial_mensajes = [c['mensaje'] for c in historial]
            
        else:
            # Modo SQLAlchemy
            with get_db() as db:
                persona = db.query(Persona).filter(Persona.telefono == phone).first()
                
                if not persona:
                    # Crear nueva persona
                    datos = {"telefono": phone}
                    if username:
                        datos["nombre_completo"] = username
                    if candidato_id_wsp:
                        datos["candidato_id"] = candidato_id_wsp
                    persona = PersonaService.crear_o_actualizar_persona(
                        db,
                        datos=datos,
                        telefono=phone
                    )
                elif candidato_id_wsp and not persona.candidato_id:
                    # Asignar candidato_id a persona existente que no lo tenga
                    persona.candidato_id = candidato_id_wsp
                    db.commit()
                    db.refresh(persona)
                
                persona_id = persona.id
                
                # Si es click en botón, actualizar interés directamente
                if interes_seleccionado:
                    PersonaService.crear_o_actualizar_persona(
                        db,
                        datos={"intereses": [interes_seleccionado]},
                        telefono=phone
                    )
                    
                    # Enviar respuesta de confirmación
                    respuesta = f"Perfecto, hemos registrado tu interés en {interes_seleccionado}. ¿Hay algo específico que te preocupe sobre este tema?"
                    whatsapp_client.enviar_mensaje(phone, respuesta)
                    
                    # Guardar conversación
                    ConversacionService.guardar_conversacion(
                        db,
                        persona_id=persona.id,
                        mensaje=texto,
                        plataforma="whatsapp",
                        es_enviado=False,
                        datos_extraidos={"intereses": [interes_seleccionado]}
                    )
                    
                    whatsapp_client.marcar_como_leido(message_id)
                    print(f"✅ Interés {interes_seleccionado} registrado para {phone}")
                    return
                
                # Obtener historial para procesamiento normal
                conversaciones = ConversacionService.obtener_historial(db, persona_id, limit=10)
                historial_mensajes = [c.mensaje for c in conversaciones]
        
        # Procesar con Agente
        resultado = procesar_conversacion(
            mensaje=texto,
            plataforma="whatsapp",
            persona_id=persona_id,
            historial=historial_mensajes
        )

        # Fallback: si el agente no extrajo nombre, usar el nombre de WhatsApp del contacto
        datos_extraidos = resultado.get("datos_extraidos") or {} if resultado else {}
        if not datos_extraidos.get("nombre_completo") and username:
            datos_extraidos["nombre_completo"] = username

        # Guardar resultados
        if datos_extraidos:
            if USE_DATAFRAMES:
                # Actualizar persona
                PersonaService.crear_o_actualizar_persona(
                    datos=datos_extraidos,
                    telefono=phone
                )
                
                # Guardar conversación
                ConversacionService.guardar_conversacion(
                    persona_id=persona_id,
                    mensaje=texto,
                    plataforma="whatsapp",
                    es_enviado=False,
                    datos_extraidos=datos_extraidos
                )

                # Crear/actualizar análisis del día (permite que WA aparezca en búsquedas)
                _hoy_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                _resumen_wa = datos_extraidos.get("resumen_conversacional") or texto[:120]
                AnalisisService.crear_analisis(
                    persona_id=persona_id,
                    resumen=_resumen_wa,
                    contenido_completo=texto,
                    categorias=datos_extraidos.get("intereses"),
                    start_conversation=_hoy_utc
                )
            else:
                with get_db() as db:
                    # Actualizar persona
                    PersonaService.crear_o_actualizar_persona(
                        db,
                        datos=datos_extraidos,
                        telefono=phone
                    )
                    
                    # Buscar persona actualizada
                    persona = db.query(Persona).filter(Persona.telefono == phone).first()
                    
                    # Guardar conversación
                    ConversacionService.guardar_conversacion(
                        db,
                        persona_id=persona.id,
                        mensaje=texto,
                        plataforma="whatsapp",
                        es_enviado=False,
                        datos_extraidos=datos_extraidos
                    )

                    # Crear/actualizar análisis del día
                    _hoy_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    _resumen_wa = datos_extraidos.get("resumen_conversacional") or texto[:120]
                    AnalisisService.crear_analisis(
                        db,
                        persona_id=persona.id,
                        resumen=_resumen_wa,
                        contenido_completo=texto,
                        categorias=datos_extraidos.get("intereses"),
                        start_conversation=_hoy_utc
                    )

            # RESPUESTA AUTOMÁTICA CON BOTONES INTERACTIVOS
            nombre = datos_extraidos.get("nombre_completo", "")
            intereses = datos_extraidos.get("intereses", [])
            
            es_primer_mensaje = not nombre or len(historial_mensajes) == 0
            
            # Si es primer mensaje, enviar botones con temas
            if es_primer_mensaje or not intereses:
                respuesta_texto = f"¡Hola{' ' + nombre if nombre else ''}! Gracias por contactarnos. ¿Qué tema te interesa más?"
                
                # WhatsApp solo soporta hasta 3 botones
                botones = [
                    {"id": "SEGURIDAD", "title": "🔒 Seguridad"},
                    {"id": "EDUCACION", "title": "🎓 Educación"},
                    {"id": "SALUD", "title": "🏥 Salud"}
                ]
                
                whatsapp_client.enviar_mensaje_con_botones(
                    phone,
                    respuesta_texto,
                    botones
                )
            else:
                # Respuesta de confirmación simple
                if nombre:
                    respuesta = f"Gracias {nombre} por compartir tu preocupación"
                else:
                    respuesta = "Gracias por compartir tu preocupación"
                
                if intereses:
                    temas = ", ".join(intereses)
                    respuesta += f" sobre {temas}"
                
                respuesta += ". Un miembro de nuestro equipo revisará tu mensaje pronto."
                
                whatsapp_client.enviar_mensaje(phone, respuesta)
            
            print(f"✅ Mensaje WhatsApp procesado y respondido a {phone}")
            
            # Marcar mensaje como leído
            try:
                whatsapp_client.marcar_como_leido(message_id)
            except:
                pass  # No es crítico si falla
            
    except Exception as e:
        print(f"❌ Error procesando mensaje WhatsApp: {e}")
        import traceback
        traceback.print_exc()


# === Dashboard Dash ===
# El dashboard Dash se ejecuta en un puerto separado (8050)
# Accesible en: http://localhost:8050 (local) o configurar en Railway como servicio separado
print("ℹ️  Dashboard Dash disponible en puerto 8050 (ejecutar: python -m frontend.app)")


if __name__ == "__main__":
    import uvicorn
    # Usar string de importación para permitir reload, asumiendo ejecución desde raíz
    uvicorn.run(
        "backend.main:app",
        host=config.BACKEND_HOST,
        port=config.BACKEND_PORT,
        reload=False  # Desactivar reload para evitar problemas de carga
    )
