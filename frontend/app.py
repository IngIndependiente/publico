"""Frontend con Dash - Interfaz responsive para consulta de personas."""
import dash
from dash import dcc, html, Input, Output, State, dash_table
import json
import dash_bootstrap_components as dbc
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz

_TZ_CL = pytz.timezone('America/Santiago')

def ahora_cl():
    """Retorna datetime actual en zona horaria Santiago de Chile."""
    return datetime.now(_TZ_CL)
import plotly.express as px
import plotly.graph_objects as go



import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend import control
from backend import config
from dash.exceptions import PreventUpdate

# === Traducciones / Translations ===
TRANSLATIONS = {
    "es": {
        "filtros": "Filtros", "fecha_desde": "Fecha Desde", "fecha_hasta": "Fecha Hasta",
        "genero_label": "Género", "seleccionar_genero": "Seleccionar género",
        "rango_edad": "Rango de Edad", "intereses_label": "Intereses",
        "seleccionar_intereses": "Seleccionar intereses", "ubicacion_label": "Ubicación",
        "ubicacion_placeholder": "Ciudad, región...",
        "buscar": "Buscar", "limpiar": "Limpiar", "exportar_csv": "Exportar CSV",
        "sync_btn": "Sync", "confirmar_sync": "Confirmar sincronización",
        "password_placeholder": "Contraseña", "sync_logs_label": "Sync logs",
        "cancelar": "Cancelar", "iniciar_sync": "Iniciar Sync", "cambiar_idioma_btn": "EN",
        "dashboard_titulo": "Dashboard - Agente CRM",
        "dashboard_subtitulo": "Sistema de análisis de conversaciones y gestión de contactos ciudadanos",
        "conexion_fb_header": "Conexión con Facebook/Instagram",
        "conexion_fb_desc": "Conecta tu página de Facebook e Instagram Business para recibir mensajes automáticamente.",
        "conectar_fb_btn": "Conectar Facebook/Instagram", "paginas_conectadas": "Páginas Conectadas:",
        "stat_total_personas": "Total Personas", "stat_resultados": "Resultados",
        "stat_conversaciones": "Conversaciones", "stat_ultima_act": "Última Actualización",
        "grafico_genero_header": "Distribución por Género", "grafico_intereses_header": "Intereses más Comunes",
        "grafico_genero_titulo": "Distribución por Género (Filtrado)",
        "grafico_intereses_titulo": "Intereses más Comunes (Filtrado)",
        "grafico_cantidad": "Cantidad de Personas", "grafico_categoria": "Categoría",
        "resultados_busqueda_header": "Resultados de Búsqueda",
        "tabla_accion": "Acción", "tabla_fecha": "Fecha", "tabla_nombre": "Nombre",
        "tabla_resumen": "Resumen Conv.", "tabla_origen": "Origen", "tabla_evento": "Evento",
        "tabla_edad": "Edad", "tabla_genero": "Género", "tabla_telefono": "Teléfono",
        "tabla_email": "Email", "tabla_ubicacion": "Ubicación", "tabla_intereses": "Intereses",
        "tabla_sin_resultados": "No hay resultados para mostrar",
        "tabla_sin_identificar": "Sin identificar", "tabla_ver": "Ver",
        "cand_sincronizar": "Sincronizar", "cand_config": "Config",
        "cand_re_analizar": "Re-analizar todo",
        "cand_sin_paginas": "No hay páginas conectadas. Haz clic en el botón para conectar.",
        "footer_privacidad": "Política de Privacidad", "footer_logs": "Logs",
    },
    "en": {
        "filtros": "Filters", "fecha_desde": "From Date", "fecha_hasta": "To Date",
        "genero_label": "Gender", "seleccionar_genero": "Select gender",
        "rango_edad": "Age Range", "intereses_label": "Interests",
        "seleccionar_intereses": "Select interests", "ubicacion_label": "Location",
        "ubicacion_placeholder": "City, region...",
        "buscar": "Search", "limpiar": "Clear", "exportar_csv": "Export CSV",
        "sync_btn": "Sync", "confirmar_sync": "Confirm Sync",
        "password_placeholder": "Password", "sync_logs_label": "Sync logs",
        "cancelar": "Cancel", "iniciar_sync": "Start Sync", "cambiar_idioma_btn": "ES",
        "dashboard_titulo": "Dashboard - CRM Agent",
        "dashboard_subtitulo": "Conversation analysis and citizen contact management system",
        "conexion_fb_header": "Facebook/Instagram Connection",
        "conexion_fb_desc": "Connect your Facebook and Instagram Business page to automatically receive messages.",
        "conectar_fb_btn": "Connect Facebook/Instagram", "paginas_conectadas": "Connected Pages:",
        "stat_total_personas": "Total People", "stat_resultados": "Results",
        "stat_conversaciones": "Conversations", "stat_ultima_act": "Last Update",
        "grafico_genero_header": "Gender Distribution", "grafico_intereses_header": "Most Common Interests",
        "grafico_genero_titulo": "Gender Distribution (Filtered)",
        "grafico_intereses_titulo": "Most Common Interests (Filtered)",
        "grafico_cantidad": "Number of People", "grafico_categoria": "Category",
        "resultados_busqueda_header": "Search Results",
        "tabla_accion": "Action", "tabla_fecha": "Date", "tabla_nombre": "Name",
        "tabla_resumen": "Conv. Summary", "tabla_origen": "Source", "tabla_evento": "Event",
        "tabla_edad": "Age", "tabla_genero": "Gender", "tabla_telefono": "Phone",
        "tabla_email": "Email", "tabla_ubicacion": "Location", "tabla_intereses": "Interests",
        "tabla_sin_resultados": "No results to display",
        "tabla_sin_identificar": "Unidentified", "tabla_ver": "View",
        "cand_sincronizar": "Sync", "cand_config": "Config",
        "cand_re_analizar": "Re-analyze all",
        "cand_sin_paginas": "No connected pages. Click the button to connect.",
        "footer_privacidad": "Privacy Policy", "footer_logs": "Logs",
    },
}

def t(key, lang="es"):
    """Retorna la traducción de la clave para el idioma dado."""
    return TRANSLATIONS.get(lang or "es", TRANSLATIONS["es"]).get(key, key)


# URL del backend
BACKEND_URL = config.BACKEND_URL

# Inicializar la app con tema Bootstrap
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ]
)

app.title = "Agente Político - Dashboard"

# Estilos
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "18rem",
    "padding": "2rem 1rem",
    "background-color": "#f8f9fa",
    "overflow-y": "auto",
}

CONTENT_STYLE = {
    "margin-left": "18rem",
    "padding": "2rem 1rem",
}

# Para móviles
MOBILE_STYLE = {
    "margin-left": "0",
    "padding": "1rem",
}

# === Componentes ===

def crear_sidebar():
    """Crear barra lateral con filtros."""
    return html.Div(
        [
            html.H2("Filtros", className="display-6", id="sidebar-titulo"),
            html.Hr(),
            
            # Fecha
            html.Label("Fecha Desde", className="fw-bold", id="label-fecha-desde"),
            dbc.Input(
                id="filtro-fecha-inicio",
                type="date",
                placeholder="YYYY-MM-DD",
                className="mb-2"
            ),
            html.Label("Fecha Hasta", className="fw-bold", id="label-fecha-hasta"),
            dbc.Input(
                id="filtro-fecha-fin",
                type="date",
                placeholder="YYYY-MM-DD",
                className="mb-3"
            ),

            html.Hr(),
            
            # Género
            html.Label("Género", className="fw-bold mt-3", id="label-genero-filtro"),
            dcc.Dropdown(
                id="filtro-genero",
                options=[{"label": g, "value": g} for g in config.GENEROS],
                placeholder="Seleccionar género",
                clearable=True,
                className="mb-3"
            ),
            
            # Edad
            html.Label("Rango de Edad", className="fw-bold mt-3", id="label-rango-edad"),
            dbc.Row([
                dbc.Col([
                    dbc.Input(
                        id="filtro-edad-min",
                        type="number",
                        placeholder="Min",
                        min=0,
                        max=120
                    )
                ], width=6),
                dbc.Col([
                    dbc.Input(
                        id="filtro-edad-max",
                        type="number",
                        placeholder="Max",
                        min=0,
                        max=120
                    )
                ], width=6),
            ], className="mb-3"),
            
            # Intereses
            html.Label("Intereses", className="fw-bold mt-3", id="label-intereses-filtro"),
            dcc.Dropdown(
                id="filtro-intereses",
                options=[{"label": i, "value": i} for i in config.CATEGORIAS_INTERES],
                placeholder="Seleccionar intereses",
                multi=True,
                className="mb-3"
            ),
            
            # Ubicación
            html.Label("Ubicación", className="fw-bold mt-3", id="label-ubicacion-filtro"),
            dbc.Input(
                id="filtro-ubicacion",
                type="text",
                placeholder="Ciudad, región...",
                className="mb-3"
            ),
            
            # Botones
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        [html.I(className="fas fa-search me-2"), "Buscar"],
                        id="btn-buscar",
                        color="primary",
                        className="w-100 mb-2"
                    ),
                ]),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        [html.I(className="fas fa-redo me-2"), "Limpiar"],
                        id="btn-limpiar",
                        color="secondary",
                        outline=True,
                        className="w-100 mb-2"
                    ),
                ]),
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        [html.I(className="fas fa-download me-2"), "Exportar CSV"],
                        id="btn-exportar",
                        color="success",
                        className="w-100"
                    ),
                ]),
            ]),
                                html.Hr(className="mt-4"),
                                dbc.Button(
                                    [html.I(className="fas fa-globe me-2"), "EN"],
                                    id="btn-idioma",
                                    color="outline-secondary",
                                    size="sm",
                                    className="w-100 mb-2",
                                ),
                                html.Div(id="info-exportacion", className="small text-muted"),
        ],
        style=SIDEBAR_STYLE,
        id="sidebar"
    )


def crear_contenido():
    """Crear área de contenido principal."""
    return html.Div(
        [
            # Header
            dbc.Row([
                dbc.Col([
                    html.H1("Dashboard - Agente CRM", className="display-4", id="texto-dashboard-titulo"),
                    html.P(
                        "Sistema de análisis de conversaciones y gestión de contactos ciudadanos",
                        className="lead",
                        id="texto-dashboard-subtitulo"
                    ),
                    html.Hr(),
                ]),
            ]),

            # OAuth status toast
            dbc.Toast(
                id="oauth-toast",
                header="Facebook Login",
                is_open=False,
                dismissable=True,
                duration=8000,
                style={"position": "fixed", "top": 20, "right": 20, "zIndex": 9999, "minWidth": "300px"}
            ),

            # Conexión Facebook/Instagram (Multi-tenant)
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.I(className="fab fa-facebook me-2"),
                            html.Span("Conexión con Facebook/Instagram", id="texto-ch-conexion-fb")
                        ]),
                        dbc.CardBody([
                            html.P(
                                "Conecta tu página de Facebook e Instagram Business para recibir mensajes automáticamente.",
                                className="text-muted",
                                id="texto-desc-fb"
                            ),
                            html.A(
                                dbc.Button(
                                    [
                                        html.I(className="fab fa-facebook me-2"),
                                        html.Span("Conectar Facebook/Instagram", id="texto-btn-conectar-fb")
                                    ],
                                    color="primary",
                                    size="lg",
                                    className="mb-3"
                                ),
                                href=f"{BACKEND_URL}/auth/facebook/login",
                                id="btn-conectar-facebook"
                            ),
                            html.Hr(),
                            html.H6("Páginas Conectadas:", className="fw-bold", id="texto-paginas-conectadas"),
                            html.Div(id="lista-candidatos-conectados")
                        ])
                    ], className="mb-4")
                ])
            ]),
                        html.Hr(),
            
            # Estadísticas
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Total Personas", className="card-title", id="label-stat-total-personas"),
                            html.H2(id="stat-total-personas", className="text-primary"),
                        ])
                    ], className="mb-3")
                ], width=12, lg=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Resultados", className="card-title", id="label-stat-resultados"),
                            html.H2(id="stat-resultados", className="text-success"),
                        ])
                    ], className="mb-3")
                ], width=12, lg=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Conversaciones", className="card-title", id="label-stat-conversaciones"),
                            html.H2(id="stat-conversaciones", className="text-info"),
                        ])
                    ], className="mb-3")
                ], width=12, lg=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Última Actualización", className="card-title", id="label-stat-ultima-act"),
                            html.P(id="stat-actualizacion", className="mb-0"),
                        ])
                    ], className="mb-3")
                ], width=12, lg=3),
            ], className="mb-4"),
            
            # Gráficos
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.Span("Distribución por Género", id="ch-dist-genero")),
                        dbc.CardBody([
                            dcc.Graph(id="grafico-genero")
                        ])
                    ], className="mb-3")
                ], width=12, lg=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.Span("Intereses más Comunes", id="ch-intereses-comunes")),
                        dbc.CardBody([
                            dcc.Graph(id="grafico-intereses")
                        ])
                    ], className="mb-3")
                ], width=12, lg=6),
            ], className="mb-4"),
            
            # Tabla de resultados
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(
                            html.Div([
                                html.H5("Resultados de Búsqueda", className="mb-0", id="ch-resultados-busqueda"),
                                html.Div([
                                    dbc.Button(html.I(className="fas fa-chevron-left"), id="btn-pagina-anterior",
                                               color="outline-secondary", size="sm", className="me-2"),
                                    html.Span(id="texto-pagina", className="small text-muted mx-1"),
                                    dbc.Button(html.I(className="fas fa-chevron-right"), id="btn-pagina-siguiente",
                                               color="outline-secondary", size="sm", className="ms-2"),
                                ], className="d-flex align-items-center"),
                            ], className="d-flex align-items-center justify-content-between")
                        ),
                        dbc.CardBody([
                            html.Div(id="tabla-resultados")
                        ])
                    ])
                ])
            ]),
            
            # Modal para ver conversación
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle(id="modal-conversacion-titulo")),
                dbc.ModalBody([
                    html.Div(id="modal-conversacion-contenido", style={
                        'maxHeight': '400px',
                        'overflowY': 'auto',
                        'padding': '10px'
                    })
                ]),
                dbc.ModalFooter(
                    html.Div([
                        # Reply section (Facebook / Instagram only)
                        html.Div([
                            dbc.InputGroup([
                                dbc.Textarea(
                                    id="input-reply-mensaje",
                                    placeholder="Write a reply...",
                                    rows=2,
                                    style={"resize": "none", "fontSize": "0.9rem"}
                                ),
                                dbc.Button(
                                    [html.I(className="fas fa-paper-plane me-1"), "Send"],
                                    id="btn-reply-enviar",
                                    color="primary",
                                    style={"whiteSpace": "nowrap"}
                                ),
                            ], className="mb-2"),
                            html.Div(id="reply-status", className="small"),
                        ], className="w-100 mb-2"),
                        dbc.Button("Cerrar", id="modal-conversacion-cerrar", color="secondary"),
                    ], className="d-flex flex-column w-100")
                ),
            ], id="modal-conversacion", size="lg", is_open=False),
            
            # Modal para evento personalizado
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Especificar Evento")),
                dbc.ModalBody([
                    html.P("Ingresa el nombre del evento personalizado:"),
                    dbc.Input(
                        id="input-evento-personalizado",
                        type="text",
                        placeholder="Ej: Feria Comunal 2026",
                        className="mb-3"
                    ),
                    html.Div(id="evento-personalizado-status")
                ]),
                dbc.ModalFooter([
                    dbc.Button("Cancelar", id="btn-evento-cancelar", className="me-2"),
                    dbc.Button("Guardar", id="btn-evento-guardar", color="primary")
                ]),
            ], id="modal-evento-personalizado", is_open=False),
            
            # Modal configuración WhatsApp
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Configurar WhatsApp Business")),
                dbc.ModalBody([
                    html.P("Configura tu cuenta de WhatsApp Business para recibir mensajes:", className="text-muted mb-3"),
                    dbc.Label("Phone Number ID:"),
                    dbc.Input(
                        id="input-whatsapp-phone-id",
                        placeholder="Ej: 1020214704502248",
                        type="text",
                        className="mb-2"
                    ),
                    dbc.Label("Business Account ID:"),
                    dbc.Input(
                        id="input-whatsapp-business-id",
                        placeholder="Ej: 883009121149060",
                        type="text",
                        className="mb-2"
                    ),
                    dbc.Label("Número de Teléfono:"),
                    dbc.Input(
                        id="input-whatsapp-phone-number",
                        placeholder="Ej: +56912345678",
                        type="text",
                        className="mb-3"
                    ),
                    html.Div([
                        html.I(className="fas fa-info-circle me-2 text-info"),
                        html.Small([
                            "Obtén estos valores en ",
                            html.A("Meta Business Manager", href="https://business.facebook.com/latest/whatsapp_manager/", target="_blank"),
                            " → WhatsApp → API Setup"
                        ], className="text-muted")
                    ], className="alert alert-info py-2 px-3 mb-2"),
                    html.Div(id="whatsapp-config-status", className="mt-2")
                ]),
                dbc.ModalFooter([
                    dbc.Button("Cancelar", id="btn-whatsapp-cancel", color="secondary", className="me-2"),
                    dbc.Button("Guardar", id="btn-whatsapp-save", color="success")
                ]),
            ], id="modal-whatsapp-config", is_open=False),

            # Modal configuración Token de Instagram
            # dbc.Modal([
            #     dbc.ModalHeader(dbc.ModalTitle([
            #         html.I(className="fab fa-instagram me-2"), "Token de Instagram"
            #     ])),
            #     dbc.ModalBody([
            #         html.P(
            #             "Ingresa el token de acceso de Instagram (IGAAU...). "
            #             "Se usa para leer mensajes de Instagram DM.",
            #             className="text-muted mb-3"
            #         ),
            #         dbc.Label("Instagram Access Token:"),
            #         dbc.Textarea(
            #             id="input-instagram-token",
            #             placeholder="IGAAUd...",
            #             rows=3,
            #             className="mb-2",
            #             style={"fontFamily": "monospace", "fontSize": "0.8rem"}
            #         ),
            #         html.Div([
            #             html.I(className="fas fa-info-circle me-2 text-warning"),
            #             html.Small([
            #                 "Este token expira. Genera uno nuevo en ",
            #                 html.A(
            #                     "Graph API Explorer",
            #                     href="https://developers.facebook.com/tools/explorer/",
            #                     target="_blank"
            #                 ),
            #                 " con el permiso instagram_manage_messages."
            #             ], className="text-muted")
            #         ], className="alert alert-warning py-2 px-3 mb-2"),
            #         html.Div(id="instagram-token-status", className="mt-2")
            #     ]),
            #     dbc.ModalFooter([
            #         dbc.Button("Cancelar", id="btn-instagram-token-cancel", color="secondary", className="me-2"),
            #         dbc.Button("Guardar", id="btn-instagram-token-save", color="danger")
            #     ]),
            # ], id="modal-instagram-token", is_open=False),

            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Seleccionar Páginas a Conectar")),
                dbc.ModalBody([
                    html.P("Selecciona las páginas que deseas conectar al sistema:", className="text-muted mb-3"),
                    html.Div([
                        dcc.Checklist(
                            id="checklist-paginas",
                            options=[],  # Se llenará dinámicamente
                            value=[],
                            labelStyle={'display': 'block', 'margin': '10px 0'},
                            inputStyle={'margin-right': '10px'}
                        )
                    ], id="container-checklist-paginas", style={'maxHeight': '400px', 'overflowY': 'auto'}),
                    html.Div(id="pages-selection-status", className="mt-3")
                ]),
                dbc.ModalFooter([
                    dbc.Button("Cancelar", id="btn-pages-cancel", color="secondary", className="me-2"),
                    dbc.Button("Conectar Seleccionadas", id="btn-pages-connect", color="primary")
                ]),
            ], id="modal-pages-selection", size="lg", is_open=False),

            # Modal de carga durante sincronización
            dbc.Modal([
                dbc.ModalBody([
                    html.Div([
                    dbc.Spinner(color="primary", size="lg"),
                        html.H5("Sincronizando conversaciones...", className="mt-3 mb-1 text-center"),
                        html.Div(id="modal-loading-sync-msg", className="text-center text-muted small mb-3"),
                        html.Div(id="modal-loading-sync-bar"),
                    ], className="text-center py-3")
                ]),
            ], id="modal-loading-sync", is_open=False, centered=True,
               backdrop="static", keyboard=False, size="sm"),

            # Store para datos
            dcc.Store(id="store-datos-personas"),
            dcc.Store(id="store-stats-filtradas"),
            dcc.Store(id="store-estadisticas"),
            dcc.Store(id="store-conversacion-actual"),
            dcc.Store(id="store-analisis-evento-actual"),  # Para guardar el análisis que está editando evento
            dcc.Store(id="store-candidato-whatsapp-id"),  # Para guardar el candidato que está configurando WhatsApp
            dcc.Store(id="store-candidato-ig-token-id"),   # Para guardar el candidato cuyo token IG se configura
            dcc.Store(id="store-facebook-pages"),  # Para guardar páginas de Facebook
            dcc.Store(id="store-url-params"),  # Para detectar parámetros de URL
            dcc.Store(id="store-facebook-user-id", storage_type="local"),  # facebook_user_id del usuario autenticado
            dcc.Store(id="store-instagram-access-token"),  # Token de usuario para Instagram Messaging API
            dcc.Store(id="store-idioma", data="es"),  # Idioma seleccionado: "es" o "en"
            dcc.Store(id="store-sync-candidatos", data={}),  # {candidato_id_str: job_state_dict}
            dcc.Store(id="store-pagina-actual", data=0),
            dcc.Store(id="store-total-paginas", data=1),
            dcc.Download(id="download-csv"),
            dcc.Interval(id="interval-sync-candidato", interval=2500, n_intervals=0, disabled=True),
            # Interval para actualización automática
            dcc.Interval(
                id="interval-actualizacion",
                interval=5*60*1000,  # 5 minutos
                n_intervals=0
            ),

            # Modal Política de Privacidad
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Marco Legal de Protección de Datos en Chile")),
                dbc.ModalBody([
                    html.H5("Ley Nº 21.719 — Protección de Datos Personales"),
                    html.P([
                        "Chile aprobó una nueva ley de protección de datos personales, la ",
                        html.Strong("Ley Nº 21.719"),
                        ", publicada en el Diario Oficial el 13 de diciembre de 2024. Esta ley moderniza y reemplaza la antigua Ley Nº 19.628, alineándose con estándares internacionales como el GDPR de la Unión Europea."
                    ]),
                    html.Ul([
                        html.Li([html.Strong("Objetivo: "), "Regular el tratamiento y protección de datos personales de personas naturales por parte de entidades públicas o privadas."]),
                        html.Li([html.Strong("Ámbito: "), "Se aplica a toda operación de tratamiento de datos —recolección, uso, almacenamiento, transmisión, etc.— automatizada o no."]),
                        html.Li([html.Strong("Entrada en vigor: "), "Plena vigencia el 1 de diciembre de 2026, tras un período de transición de 24 meses desde su publicación."]),
                    ]),

                    html.Hr(),
                    html.H5("Principios que Rigen el Tratamiento de Datos Personales"),
                    html.Ul([
                        html.Li([html.Strong("Licitud y lealtad: "), "El tratamiento debe ser legal, justo y transparente."]),
                        html.Li([html.Strong("Finalidad: "), "Los datos solo pueden usarse para fines específicos y explícitos informados al titular."]),
                        html.Li([html.Strong("Proporcionalidad: "), "Solo se deben recopilar los datos necesarios y pertinentes."]),
                        html.Li([html.Strong("Calidad: "), "Datos precisos, completos y actualizados."]),
                        html.Li([html.Strong("Seguridad: "), "Protección contra accesos no autorizados, pérdidas, filtraciones o destrucción."]),
                        html.Li([html.Strong("Transparencia: "), "Información clara sobre políticas y prácticas de tratamiento."]),
                        html.Li([html.Strong("Confidencialidad: "), "Los datos deben mantenerse en secreto, incluso después de terminado el tratamiento."]),
                    ]),

                    html.Hr(),
                    html.H5("Condiciones de Tratamiento y Bases Legales"),
                    html.P("Para que el tratamiento de datos sea legítimo, debe contar con una base legal válida:"),
                    html.Ul([
                        html.Li("Consentimiento informado y explícito del titular."),
                        html.Li("Necesidad contractual."),
                        html.Li("Cumplimiento de una obligación legal."),
                        html.Li("Interés legítimo justificado y documentado."),
                    ]),
                    html.P("El consentimiento debe ser previo, informado, específico e inequívoco."),

                    html.Hr(),
                    html.H5("Obligaciones para Responsables del Tratamiento"),
                    html.Ul([
                        html.Li("Documentar todas las actividades de tratamiento."),
                        html.Li("Implementar medidas de seguridad adecuadas."),
                        html.Li("Publicar políticas de privacidad claras y accesibles."),
                        html.Li("Establecer protocolos para gestionar incidentes y respuesta a derechos de titulares."),
                        html.Li("Realizar evaluaciones de impacto cuando el tratamiento conlleve riesgos altos."),
                    ]),

                    html.Hr(),
                    html.H5("❌ Qué No Permitirá Hacer"),
                    html.Ul([
                        html.Li("✘ Usar tus datos sin una base legal (sin consentimiento u otra justificación válida)."),
                        html.Li("✘ Tratar tus datos para fines distintos de los informados sin nuevo consentimiento."),
                        html.Li("✘ Mantener datos por tiempo indefinido sin necesidad legítima."),
                        html.Li("✘ Negar o ignorar tus derechos de acceso, rectificación, supresión u oposición."),
                        html.Li("✘ Ignorar medidas de seguridad o no responder a incidentes de seguridad."),
                    ]),

                    html.Hr(),
                    html.H6("Fuentes:"),
                    html.Ul([
                        html.Li(html.A("Ley Nº 21.719 — BCN", href="https://www.bcn.cl/leychile/navegar?idNorma=1209272", target="_blank")),
                        html.Li(html.A("Gestión de consentimiento — Entel Digital", href="https://enteldigital.cl/blog/gestion-de-consentimiento-lo-nuevo-en-ley-de-proteccion-de-datos", target="_blank")),
                        html.Li(html.A("Nueva ley exige preparación empresarial — CCS", href="https://www.ccs.cl/2025/06/04/nueva-ley-de-proteccion-de-datos-exige-preparacion-empresarial-inmediata", target="_blank")),
                    ]),
                    html.P(html.Small("Última actualización: marzo 2026"), className="text-muted mt-2"),
                ]),
                dbc.ModalFooter(
                    dbc.Button("Cerrar", id="btn-privacidad-cerrar", color="secondary")
                ),
            ], id="modal-privacidad", size="lg", scrollable=True, is_open=False),

            # Modal Logs del Sistema
            dbc.Modal([
                dbc.ModalHeader([
                    dbc.ModalTitle([
                        html.I(className="fas fa-terminal me-2"),
                        "Logs del Sistema (backend)"
                    ]),
                    dbc.Button(
                        html.I(className="fas fa-sync-alt"),
                        id="btn-logs-refresh",
                        color="outline-secondary",
                        size="sm",
                        className="ms-2",
                        title="Actualizar"
                    ),
                ]),
                dbc.ModalBody(
                    html.Pre(
                        id="logs-contenido",
                        style={
                            "backgroundColor": "#1e1e1e",
                            "color": "#d4d4d4",
                            "padding": "12px",
                            "borderRadius": "4px",
                            "maxHeight": "65vh",
                            "overflowY": "auto",
                            "fontSize": "0.78rem",
                            "fontFamily": "Consolas, monospace",
                            "whiteSpace": "pre-wrap",
                            "wordBreak": "break-all",
                        }
                    )
                ),
                dbc.ModalFooter(
                    dbc.Button("Cerrar", id="btn-logs-cerrar", color="secondary")
                ),
            ], id="modal-logs", size="xl", scrollable=False, is_open=False),

            # Footer
            html.Footer([
                html.Hr(),
                html.Div([
                    html.Span("© 2026 Retarget SpA · ", className="text-muted small"),
                    dbc.Button(
                        "Política de Privacidad",
                        id="btn-abrir-privacidad",
                        color="link",
                        size="sm",
                        className="p-0 text-muted",
                        style={"fontSize": "0.875rem", "verticalAlign": "baseline"}
                    ),
                    html.Span(" · ", className="text-muted small"),
                    dbc.Button(
                        [html.I(className="fas fa-terminal me-1"), "Logs"],
                        id="btn-abrir-logs",
                        color="link",
                        size="sm",
                        className="p-0 text-muted",
                        style={"fontSize": "0.875rem", "verticalAlign": "baseline"}
                    ),
                ], className="text-center py-3")
            ]),
        ],
        style=CONTENT_STYLE,
        id="page-content"
    )


# ── Callback Logs ──────────────────────────────────────────────────────────
@app.callback(
    [Output("modal-logs", "is_open"),
     Output("logs-contenido", "children")],
    [Input("btn-abrir-logs", "n_clicks"),
     Input("btn-logs-cerrar", "n_clicks"),
     Input("btn-logs-refresh", "n_clicks")],
    [State("modal-logs", "is_open")],
    prevent_initial_call=True
)
def toggle_modal_logs(abrir, cerrar, refresh, is_open):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger = ctx.triggered[0]["prop_id"]
    if trigger == "btn-logs-cerrar.n_clicks":
        return False, dash.no_update
    # Abrir o refrescar: fetch logs del backend
    texto = "(sin logs)"
    try:
        r = requests.get(f"{BACKEND_URL}/api/debug/logs", params={"n": 300}, timeout=8)
        if r.status_code == 200:
            lines = r.json().get("lines", [])
            total = r.json().get("total", 0)
            header = f"── {len(lines)} líneas mostradas de {total} en buffer ──\n\n"
            texto = header + "\n".join(lines)
        else:
            texto = f"HTTP {r.status_code}: {r.text[:500]}"
    except Exception as exc:
        texto = f"Error al obtener logs: {exc}"
    return True, texto
# ───────────────────────────────────────────────────────────────────────────


# Layout principal
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    crear_sidebar(),
    crear_contenido()
])


# === Callback para leer páginas via token OAuth (cross-origin safe) ===
@app.callback(
    [Output('store-facebook-pages', 'data'),
     Output('store-facebook-user-id', 'data'),
     Output('store-instagram-access-token', 'data'),
     Output('oauth-toast', 'children'),
     Output('oauth-toast', 'is_open'),
     Output('oauth-toast', 'icon')],
    Input('url', 'href'),
    prevent_initial_call=False
)
def cargar_paginas_oauth(href):
    """Detecta oauth_token o oauth_error en la URL y carga las páginas disponibles."""
    no_toast = (dash.no_update, dash.no_update, dash.no_update, dash.no_update, False, dash.no_update)

    if not href:
        raise PreventUpdate

    from urllib.parse import urlparse, parse_qs, unquote
    parsed = urlparse(href)
    params = parse_qs(parsed.query)

    # Show oauth_error from backend as a visible toast
    if 'oauth_error' in params:
        error_msg = unquote(params['oauth_error'][0])
        print(f"[Frontend] oauth_error recibido: {error_msg}")
        return dash.no_update, dash.no_update, dash.no_update, error_msg, True, "danger"

    if 'oauth_token' not in params:
        raise PreventUpdate

    token = params['oauth_token'][0]
    print(f"[Frontend] oauth_token recibido, consultando sesión...")

    try:
        response = requests.get(f"{BACKEND_URL}/api/oauth-session/{token}", timeout=10)
        print(f"[Frontend] /api/oauth-session respuesta: {response.status_code}")
        if response.ok:
            data = response.json()
            pages = data.get('pages', [])
            facebook_user_id = data.get('facebook_user_id')
            instagram_access_token = data.get('instagram_access_token')
            print(f"[Frontend] Páginas recibidas: {[p.get('page_name') for p in pages]}")
            if pages:
                return pages, facebook_user_id, instagram_access_token, dash.no_update, False, dash.no_update
            else:
                return dash.no_update, dash.no_update, dash.no_update, "No se encontraron páginas en la sesión OAuth.", True, "warning"
        else:
            msg = f"Error al recuperar la sesión OAuth ({response.status_code}): {response.text[:200]}"
            print(f"[Frontend] {msg}")
            return dash.no_update, dash.no_update, dash.no_update, msg, True, "danger"
    except Exception as e:
        print(f"[Frontend] Error recuperando sesión OAuth: {e}")
        return dash.no_update, dash.no_update, dash.no_update, f"Error de conexión: {e}", True, "danger"


# === Callbacks ===

@app.callback(
    [Output("store-estadisticas", "data"),
     Output("stat-total-personas", "children"),
     Output("stat-conversaciones", "children")],
    [Input("interval-actualizacion", "n_intervals")],
    [State("store-facebook-user-id", "data")]
)
def actualizar_estadisticas(n, facebook_user_id):
    """Actualizar estadísticas generales."""
    try:
        params = {}
        if facebook_user_id:
            params["owner_facebook_user_id"] = facebook_user_id
        response = requests.get(f"{BACKEND_URL}/api/stats", params=params, timeout=5)
        if response.status_code == 200:
            stats = response.json()
            return (
                stats,
                str(stats.get("total_personas", 0)),
                str(stats.get("total_conversaciones", 0))
            )
    except:
        pass
    
    return {}, "0", "0"


@app.callback(
    [Output("grafico-genero", "figure"),
     Output("grafico-intereses", "figure")],
    [Input("store-stats-filtradas", "data"),
     Input("store-idioma", "data")]
)
def actualizar_graficos(stats, lang):
    """Actualizar gráficos de estadísticas."""
    lang = lang or "es"
    if not stats:
        # Default empty fig
        return {}, {}
    
    # Gráfico de género
    genero_data = stats.get("por_genero", {})
    if not genero_data:
         fig_genero = {}
    else:
        fig_genero = px.pie(
            values=list(genero_data.values()),
            names=list(genero_data.keys()),
            title=t("grafico_genero_titulo", lang),
            hole=0.3
        )
        fig_genero.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    
    # Gráfico de intereses
    intereses_data = stats.get("por_interes", {})
    if not intereses_data:
        fig_intereses = {}
    else:
        fig_intereses = px.bar(
            x=list(intereses_data.values()),
            y=list(intereses_data.keys()),
            orientation='h',
            title=t("grafico_intereses_titulo", lang),
            labels={"x": t("grafico_cantidad", lang), "y": t("grafico_categoria", lang)}
        )
        fig_intereses.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    
    return fig_genero, fig_intereses


@app.callback(
    [Output("store-datos-personas", "data"),
     Output("stat-resultados", "children"),
     Output("stat-actualizacion", "children"),
     Output("store-stats-filtradas", "data"),
     Output("store-total-paginas", "data")],
    [Input("btn-buscar", "n_clicks"),
     Input("interval-actualizacion", "n_intervals"),
     Input("store-pagina-actual", "data")],
    [State("filtro-fecha-inicio", "value"),
     State("filtro-fecha-fin", "value"),
     State("filtro-genero", "value"),
     State("filtro-edad-min", "value"),
     State("filtro-edad-max", "value"),
     State("filtro-intereses", "value"),
     State("filtro-ubicacion", "value"),
     State("store-facebook-user-id", "data")],
    prevent_initial_call=False
)
def buscar_personas(n_clicks, n_intervals, pagina_actual, fecha_inicio, fecha_fin, genero, edad_min, edad_max, intereses, ubicacion, facebook_user_id):
    """Buscar personas según filtros."""
    # No hay usuario autenticado — no mostrar datos de nadie
    if not facebook_user_id:
        return [], "0", "—", {}, 0

    # Construir payload
    payload = {}
    # Solo enviar fechas si tienen valor y no son cadenas vacías
    if fecha_inicio and fecha_inicio.strip():
        payload["fecha_inicio"] = fecha_inicio
    if fecha_fin and fecha_fin.strip():
        payload["fecha_fin"] = fecha_fin
    if genero:
        payload["genero"] = genero
    if edad_min:
        payload["edad_min"] = edad_min
    if edad_max:
        payload["edad_max"] = edad_max
    if intereses:
        payload["intereses"] = intereses
    if ubicacion and ubicacion.strip():
        payload["ubicacion"] = ubicacion
    if facebook_user_id:
        payload["facebook_user_id"] = facebook_user_id
    payload["page"] = pagina_actual or 0
    payload["page_size"] = 50
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/personas/buscar",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            personas = data.get("personas", [])
            total = data.get("total", 0)
            total_paginas = data.get("total_paginas", 1)
            stats = data.get("stats", {}) # Obtener estadísticas
            print(f"[buscar_personas] OK – total={total}, pág={pagina_actual}/{total_paginas}, personas={len(personas)}")
            ahora = ahora_cl().strftime("%d/%m/%Y %H:%M:%S")
            return personas, str(total), ahora, stats, total_paginas
        else:
            print(f"[buscar_personas] HTTP {response.status_code}: {response.text[:1000]}")
    except Exception as e:
        print(f"[buscar_personas] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # Intentar obtener info de diagnóstico del backend
    try:
        r2 = requests.get(f"{BACKEND_URL}/api/debug/status", timeout=5)
        if r2.status_code == 200:
            print(f"[debug/status] {r2.json()}")
    except Exception:
        pass

    return [], "0", "Error", {}, 0


@app.callback(
    Output("store-pagina-actual", "data"),
    [Input("btn-buscar", "n_clicks"),
     Input("btn-pagina-anterior", "n_clicks"),
     Input("btn-pagina-siguiente", "n_clicks")],
    [State("store-pagina-actual", "data"),
     State("store-total-paginas", "data")],
    prevent_initial_call=True
)
def cambiar_pagina(n_buscar, n_anterior, n_siguiente, pagina, total_paginas):
    """Gestionar la página actual de resultados."""
    ctx = dash.callback_context
    if not ctx.triggered:
        return pagina or 0
    trigger = ctx.triggered[0]["prop_id"]
    if "btn-buscar" in trigger:
        return 0
    elif "btn-pagina-anterior" in trigger:
        return max(0, (pagina or 0) - 1)
    elif "btn-pagina-siguiente" in trigger:
        return min((total_paginas or 1) - 1, (pagina or 0) + 1)
    return pagina or 0


@app.callback(
    Output("texto-pagina", "children"),
    [Input("store-pagina-actual", "data"),
     Input("store-total-paginas", "data")]
)
def actualizar_display_pagina(pagina, total_paginas):
    """Actualizar el display de paginación."""
    p = (pagina or 0) + 1
    tp = total_paginas or 1
    return f"Pág. {p} de {tp}"


@app.callback(
    Output("tabla-resultados", "children"),
    [Input("store-datos-personas", "data"),
     Input("store-idioma", "data")]
)
def actualizar_tabla(personas, lang):
    """Actualizar tabla de resultados."""
    lang = lang or "es"
    if not personas:
        return html.Div(
            dbc.Alert(t("tabla_sin_resultados", lang), color="info"),
            className="text-center"
        )
    
    # Crear tabla con botones
    rows = []
    for p in personas:
        # Formatear nombre con usuario
        nombre = p.get("nombre_completo") or t("tabla_sin_identificar", lang)
        usuario = p.get("facebook_username") or p.get("instagram_username")
        
        if usuario:
            nombre_display = f"{nombre} (@{usuario})"
        else:
            nombre_display = nombre
        
        # analisis_id puede ser negativo (= -persona_id) cuando no hay análisis real
        analisis_id = p.get("analisis_id")
        if analisis_id is None:
            analisis_id = -(p.get("id") or 0)
        tiene_analisis = analisis_id is not None and analisis_id > 0
        evento_nombre = p.get("evento_nombre") or "Sin asignar"
        # Unique index for Dash pattern-matching IDs: always non-None and unique per row
        row_index = analisis_id if analisis_id is not None else -(p.get("id") or 0)
        
        row = html.Tr([
            html.Td(
                dbc.Button(
                    [html.I(className="fas fa-comments me-1"), t("tabla_ver", lang)],
                    id={"type": "btn-ver-conversacion", "index": row_index},
                    color="primary" if tiene_analisis else "secondary",
                    size="sm",
                    className="w-100",
                    disabled=not tiene_analisis,
                ),
                style={'width': '100px', 'textAlign': 'center'}
            ),
            html.Td(datetime.fromisoformat(p["fecha_ultimo_contacto"]).strftime("%Y-%m-%d %H:%M") if p.get("fecha_ultimo_contacto") else "N/A"),
            html.Td(nombre_display),
            html.Td(p.get("resumen_conversacion") or "N/A", style={'maxWidth': '300px'}),
            html.Td(
                dbc.Badge(
                    (p.get("plataforma") or "N/A").capitalize(),
                    color={"messenger": "primary", "instagram": "danger", "whatsapp": "success"}.get(
                        (p.get("plataforma") or "").lower(), "secondary"
                    ),
                    className="text-white"
                )
            ),
            html.Td([
                dcc.Dropdown(
                    id={"type": "dropdown-evento", "index": row_index},
                    className="evento-dropdown",
                    style={'minWidth': '150px'},
                    clearable=False,
                    disabled=not tiene_analisis,
                ),
                html.Div(id={"type": "evento-status", "index": row_index}, style={'fontSize': '0.7rem', 'marginTop': '2px'})
            ], id={"type": "td-evento", "index": row_index}),
            html.Td(p["edad"] or "N/A"),
            html.Td(p["genero"] or "N/A"),
            html.Td(p["telefono"] or "N/A"),
            html.Td(p["email"] or "N/A"),
            html.Td(p["ubicacion"] or "N/A"),
            html.Td(", ".join(p["intereses"]) if p["intereses"] else "N/A", style={'maxWidth': '200px'}),
        ])
        rows.append(row)
    
    tabla = dbc.Table(
        [
            html.Thead(html.Tr([
                html.Th(t("tabla_accion", lang)),
                html.Th(t("tabla_fecha", lang)),
                html.Th(t("tabla_nombre", lang)),
                html.Th(t("tabla_resumen", lang)),
                html.Th(t("tabla_origen", lang)),
                html.Th(t("tabla_evento", lang)),
                html.Th(t("tabla_edad", lang)),
                html.Th(t("tabla_genero", lang)),
                html.Th(t("tabla_telefono", lang)),
                html.Th(t("tabla_email", lang)),
                html.Th(t("tabla_ubicacion", lang)),
                html.Th(t("tabla_intereses", lang)),
            ])),
            html.Tbody(rows)
        ],
        striped=True,
        bordered=True,
        hover=True,
        responsive=True,
        style={'fontSize': '0.9rem'}
    )
    
    return html.Div(tabla, style={'maxHeight': '600px', 'overflowY': 'auto'})


@app.callback(
    [Output("modal-conversacion", "is_open"),
     Output("store-conversacion-actual", "data"),
     Output("reply-status", "children", allow_duplicate=True),
     Output("input-reply-mensaje", "value", allow_duplicate=True)],
    [Input({"type": "btn-ver-conversacion", "index": dash.dependencies.ALL}, "n_clicks"),
     Input("modal-conversacion-cerrar", "n_clicks")],
    [State("modal-conversacion", "is_open"),
     State({"type": "btn-ver-conversacion", "index": dash.dependencies.ALL}, "id")],
    prevent_initial_call=True
)
def toggle_modal_conversacion(btn_ver_clicks, btn_cerrar, is_open, btn_ids):
    """Abrir/cerrar modal de conversación."""
    ctx = dash.callback_context

    if not ctx.triggered:
        return False, None, None, ""

    trigger_id = ctx.triggered[0]["prop_id"]

    # Si se clickeó cerrar — limpiar reply también
    if "modal-conversacion-cerrar" in trigger_id:
        return False, None, None, ""

    # Si se clickeó ver conversación
    if "btn-ver-conversacion" in trigger_id:
        for i, clicks in enumerate(btn_ver_clicks):
            if clicks:
                analisis_id = btn_ids[i]["index"]
                return True, analisis_id, None, ""

    return False, None, None, ""


@app.callback(
    [Output("modal-conversacion-titulo", "children"),
     Output("modal-conversacion-contenido", "children")],
    [Input("store-conversacion-actual", "data")]
)
def cargar_conversacion(analisis_id):
    """Cargar y mostrar la conversación en el modal."""
    if not analisis_id:
        return "Conversación", html.Div("No hay datos para mostrar")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/analisis/{analisis_id}/conversacion",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Título del modal
            persona_nombre = data.get("persona_nombre", "Usuario")
            start_conversation = data.get("start_conversation", data.get("fecha_analisis", ""))
            # Formatear fecha
            if start_conversation:
                try:
                    fecha_obj = datetime.fromisoformat(start_conversation)
                    fecha_formateada = fecha_obj.strftime("%Y-%m-%d %H:%M")
                    titulo = f"Conversación con {persona_nombre} - {fecha_formateada}"
                except:
                    titulo = f"Conversación con {persona_nombre}"
            else:
                titulo = f"Conversación con {persona_nombre}"
            
            # Contenido: mensajes estilo chat
            mensajes = data.get("mensajes", [])
            
            if not mensajes:
                return titulo, dbc.Alert("No hay mensajes en esta conversación", color="info")
            
            # Crear burbujas de chat
            chat_messages = []
            for msg in mensajes:
                es_enviado = msg.get("es_enviado", False)
                texto = msg.get("mensaje", "")
                fecha = msg.get("fecha", "")
                
                try:
                    fecha_formateada = datetime.fromisoformat(fecha).strftime("%d/%m/%Y %H:%M")
                except:
                    fecha_formateada = fecha
                
                # Estilo de burbuja según quién envió
                if es_enviado:
                    # Mensaje enviado por nosotros (derecha, azul)
                    burbuja = html.Div([
                        html.Div([
                            html.P(texto, className="mb-1", style={'wordWrap': 'break-word'}),
                            html.Small(fecha_formateada, className="text-muted")
                        ], style={
                            'backgroundColor': '#007bff',
                            'color': 'white',
                            'padding': '10px 15px',
                            'borderRadius': '18px',
                            'maxWidth': '70%',
                            'marginLeft': 'auto',
                            'marginBottom': '10px',
                            'boxShadow': '0 1px 2px rgba(0,0,0,0.1)'
                        })
                    ], style={'display': 'flex', 'justifyContent': 'flex-end', 'marginBottom': '10px'})
                else:
                    # Mensaje recibido (izquierda, gris)
                    burbuja = html.Div([
                        html.Div([
                            html.P(texto, className="mb-1", style={'wordWrap': 'break-word'}),
                            html.Small(fecha_formateada, className="text-muted")
                        ], style={
                            'backgroundColor': '#e9ecef',
                            'color': '#212529',
                            'padding': '10px 15px',
                            'borderRadius': '18px',
                            'maxWidth': '70%',
                            'marginBottom': '10px',
                            'boxShadow': '0 1px 2px rgba(0,0,0,0.1)'
                        })
                    ], style={'display': 'flex', 'justifyContent': 'flex-start', 'marginBottom': '10px'})
                
                chat_messages.append(burbuja)
            
            # Resumen al final
            resumen = data.get("resumen", "")
            if resumen:
                chat_messages.append(html.Hr())
                chat_messages.append(
                    dbc.Alert([
                        html.Strong("Resumen: "),
                        resumen
                    ], color="info", className="mt-3")
                )
            
            return titulo, html.Div(chat_messages)
        
    except Exception as e:
        print(f"Error al cargar conversación: {e}")
        return "Error", dbc.Alert(f"Error al cargar la conversación: {str(e)}", color="danger")
    
    return "Conversación", html.Div("No se pudo cargar la conversación")


@app.callback(
    [Output("reply-status", "children"),
     Output("input-reply-mensaje", "value")],
    Input("btn-reply-enviar", "n_clicks"),
    [State("input-reply-mensaje", "value"),
     State("store-conversacion-actual", "data")],
    prevent_initial_call=True
)
def enviar_reply(n_clicks, texto, analisis_id):
    """Enviar respuesta manual a la conversación activa."""
    if not n_clicks or not texto or not texto.strip():
        raise PreventUpdate

    if not analisis_id:
        return dbc.Alert("No hay conversación activa.", color="warning", className="py-1 px-2"), texto

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/conversaciones/{analisis_id}/responder",
            json={"texto": texto.strip()},
            timeout=10
        )
        if response.ok:
            return dbc.Alert(
                [html.I(className="fas fa-check-circle me-1"), "Message sent successfully."],
                color="success", className="py-1 px-2 mb-0"
            ), ""
        else:
            detail = response.json().get("detail", response.text)
            return dbc.Alert(
                [html.I(className="fas fa-exclamation-circle me-1"), f"Error: {detail}"],
                color="danger", className="py-1 px-2 mb-0"
            ), texto
    except Exception as e:
        return dbc.Alert(
            [html.I(className="fas fa-exclamation-circle me-1"), f"Connection error: {str(e)}"],
            color="danger", className="py-1 px-2 mb-0"
        ), texto


@app.callback(
    [Output("download-csv", "data"),
     Output("info-exportacion", "children")],
    [Input("btn-exportar", "n_clicks")],
    [State("store-datos-personas", "data")],
    prevent_initial_call=True
)
def exportar_csv(n_clicks, personas):
    """Descargar la tabla de resultados de búsqueda actual como CSV."""
    if not n_clicks:
        return None, ""
    if not personas:
        return None, dbc.Alert(
            [html.I(className="fas fa-exclamation-triangle me-2"), "No hay resultados para exportar."],
            color="warning", className="small mt-2"
        )
    
    try:
        columnas = [
            ("id", "ID"),
            ("nombre_completo", "Nombre Completo"),
            ("edad", "Edad"),
            ("genero", "Género"),
            ("ubicacion", "Ubicación"),
            ("ocupacion", "Ocupación"),
            ("telefono", "Teléfono"),
            ("email", "Email"),
            ("facebook_username", "Usuario Facebook"),
            ("instagram_username", "Usuario Instagram"),
            ("intereses", "Intereses"),
            ("resumen_conversacion", "Resumen Conversación"),
            ("fecha_primer_contacto", "Primer Contacto"),
            ("fecha_ultimo_contacto", "Último Contacto"),
        ]
        rows = []
        for p in personas:
            row = {}
            for key, label in columnas:
                val = p.get(key, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                row[label] = val if val is not None else ""
            rows.append(row)
        
        df_export = pd.DataFrame(rows)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return dcc.send_data_frame(df_export.to_csv, f"resultados_{timestamp}.csv", index=False, encoding="utf-8-sig"), \
               dbc.Alert(
                   [html.I(className="fas fa-check-circle me-2"), f"{len(rows)} registros exportados"],
                   color="success", className="small mt-2"
               )
    except Exception as e:
        return None, dbc.Alert(
            [html.I(className="fas fa-exclamation-triangle me-2"), f"Error: {str(e)}"],
            color="danger", className="small mt-2"
        )


@app.callback(
    [Output("filtro-fecha-inicio", "value"),
     Output("filtro-fecha-fin", "value"),
     Output("filtro-genero", "value"),
     Output("filtro-edad-min", "value"),
     Output("filtro-edad-max", "value"),
     Output("filtro-intereses", "value"),
     Output("filtro-ubicacion", "value")],
    [Input("btn-limpiar", "n_clicks")],
    prevent_initial_call=True
)
def limpiar_filtros(n_clicks):
    """Limpiar todos los filtros."""
    return None, None, None, None, None, None, ""


@app.callback(
    Output({"type": "dropdown-evento", "index": dash.dependencies.MATCH}, "options"),
    Output({"type": "dropdown-evento", "index": dash.dependencies.MATCH}, "value"),
    Input({"type": "td-evento", "index": dash.dependencies.MATCH}, "id"),
    State("store-datos-personas", "data")
)
def poblar_dropdown_evento(td_id, personas):
    """Poblar dropdown de eventos con las opciones disponibles."""
    if not td_id or not personas:
        return [], None
    
    analisis_id = td_id["index"]
    
    # Obtener eventos del backend
    try:
        response = requests.get(f"{BACKEND_URL}/api/eventos", timeout=5)
        if response.status_code == 200:
            eventos = response.json()
            
            # Crear opciones del dropdown
            options = [{"label": "Sin asignar", "value": 0}]
            options.extend([{"label": e["nombre"], "value": e["id"]} for e in eventos])

            # Encontrar el evento actual de esta persona
            persona = next((p for p in personas if p.get("analisis_id") == analisis_id), None)
            evento_id = persona.get("evento_id") if persona else None
            evento_nombre = persona.get("evento_nombre") if persona else None

            # Si no tiene evento_id o es None, usar 0 (Sin asignar)
            if evento_id is None:
                evento_id = 0

            # Si el evento actual no está entre las opciones (por ejemplo, evento creado recientemente),
            # añadir una opción temporal para preservar la selección y etiqueta.
            option_values = {opt["value"] for opt in options}
            if evento_id not in option_values and evento_id is not None:
                # usar nombre si está disponible, sino una etiqueta genérica
                label = evento_nombre or f"Evento #{evento_id}"
                options.append({"label": label, "value": evento_id})

            return options, evento_id
    except Exception as e:
        print(f"Error al cargar eventos: {e}")
    
    return [{"label": "Error cargando eventos", "value": 0}], 0


@app.callback(
    Output({"type": "evento-status", "index": dash.dependencies.MATCH}, "children"),
    Input({"type": "dropdown-evento", "index": dash.dependencies.MATCH}, "value"),
    State({"type": "dropdown-evento", "index": dash.dependencies.MATCH}, "id"),
    State({"type": "dropdown-evento", "index": dash.dependencies.MATCH}, "options"),
    prevent_initial_call=True
)
def actualizar_evento_status(evento_id, dropdown_id, options):
    """Actualizar el evento en el backend y mostrar status (solo devuelve status)."""
    if evento_id is None or not dropdown_id:
        return ""

    analisis_id = dropdown_id["index"]

    # analisis_id negativo significa persona sin análisis real — no hay nada que actualizar
    if analisis_id is None or analisis_id <= 0:
        return ""

    # Buscar si el evento seleccionado es "Otros"
    evento_seleccionado = next((opt for opt in options if opt["value"] == evento_id), None)
    es_otros = evento_seleccionado and evento_seleccionado["label"] == "Otros"

    # Si es "Otros", no actualizar aquí (se manejará en otro callback)
    if es_otros:
        return ""

    try:
        # Actualizar en el backend
        response = requests.put(
            f"{BACKEND_URL}/api/analisis/{analisis_id}/evento",
            params={"evento_id": evento_id if evento_id != 0 else None},
            timeout=5
        )

        if response.status_code == 200:
            return html.Span("✓ Guardado", style={'color': 'green'})
        else:
            return html.Span("✗ Error", style={'color': 'red'})
    except Exception as e:
        print(f"Error al actualizar evento: {e}")
        return html.Span("✗ Error", style={'color': 'red'})


# Callback separado para actualizar el store de personas cuando cambia el dropdown
@app.callback(
    Output("store-datos-personas", "data", allow_duplicate=True),
    Input({"type": "dropdown-evento", "index": dash.dependencies.ALL}, "value"),
    State({"type": "dropdown-evento", "index": dash.dependencies.ALL}, "id"),
    State({"type": "dropdown-evento", "index": dash.dependencies.ALL}, "options"),
    State("store-datos-personas", "data"),
    prevent_initial_call=True
)
def actualizar_evento_store(eventos_values, dropdowns_ids, dropdowns_options, personas):
    """Actualizar localmente `store-datos-personas` cuando se selecciona un evento.

    Usa ALL para evitar mismatches de wildcard; detecta qué dropdown cambió leyendo
    `dash.callback_context.triggered` y actualiza ese `analisis_id` en el store.
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    trigger = ctx.triggered[0]["prop_id"]
    # prop_id viene como JSON.string + ".value"; extraer la parte JSON
    json_id = trigger.split('.')[0]
    try:
        changed = json.loads(json_id)
        changed_index = changed.get('index')
    except Exception:
        changed_index = None

    if changed_index is None:
        raise dash.exceptions.PreventUpdate

    # encontrar posición del dropdown cambiado
    changed_pos = None
    for i, did in enumerate(dropdowns_ids or []):
        if did.get('index') == changed_index:
            changed_pos = i
            break

    if changed_pos is None:
        raise dash.exceptions.PreventUpdate

    evento_id = eventos_values[changed_pos]
    options = dropdowns_options[changed_pos] if dropdowns_options else []

    evento_seleccionado = next((opt for opt in (options or []) if opt.get('value') == evento_id), None)
    nombre = evento_seleccionado.get('label') if evento_seleccionado else None

    if not personas:
        return personas

    for persona in personas:
        if persona.get('analisis_id') == changed_index:
            persona['evento_id'] = evento_id if evento_id != 0 else None
            if nombre:
                persona['evento_nombre'] = nombre
            break

    return personas


@app.callback(
    Output("modal-evento-personalizado", "is_open"),
    Output("store-analisis-evento-actual", "data"),
    Input({"type": "dropdown-evento", "index": dash.dependencies.ALL}, "value"),
    State({"type": "dropdown-evento", "index": dash.dependencies.ALL}, "id"),
    State({"type": "dropdown-evento", "index": dash.dependencies.ALL}, "options"),
    prevent_initial_call=True
)
def abrir_modal_evento_personalizado(eventos_values, dropdowns_ids, dropdowns_options):
    """Abrir modal cuando se selecciona 'Otros' en cualquier dropdown de evento."""
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, None
    
    # Obtener el dropdown que cambió
    trigger = ctx.triggered[0]
    if not trigger["value"]:
        return False, None
    
    # Encontrar cuál dropdown cambió
    for i, (evento_id, dropdown_id, options) in enumerate(zip(eventos_values, dropdowns_ids, dropdowns_options)):
        if f'"index":{dropdown_id["index"]}' in trigger["prop_id"]:
            # Buscar si el evento seleccionado es "Otros"
            evento_seleccionado = next((opt for opt in options if opt["value"] == evento_id), None)
            es_otros = evento_seleccionado and evento_seleccionado["label"] == "Otros"
            
            if es_otros:
                analisis_id = dropdown_id["index"]
                return True, analisis_id
    
    return False, None


@app.callback(
    Output("modal-evento-personalizado", "is_open", allow_duplicate=True),
    Output("input-evento-personalizado", "value"),
    Output("evento-personalizado-status", "children"),
    Output("store-datos-personas", "data", allow_duplicate=True),
    Input("btn-evento-guardar", "n_clicks"),
    Input("btn-evento-cancelar", "n_clicks"),
    State("input-evento-personalizado", "value"),
    State("store-analisis-evento-actual", "data"),
    State("store-datos-personas", "data"),
    prevent_initial_call=True
)
def guardar_evento_personalizado(btn_guardar, btn_cancelar, nombre_evento, analisis_id, personas):
    """Guardar un evento personalizado cuando el usuario lo especifica."""
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, "", "", personas
    
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    # Si cancela, solo cerrar el modal
    if trigger_id == "btn-evento-cancelar":
        return False, "", "", personas
    
    # Si guarda, validar y crear el evento
    if trigger_id == "btn-evento-guardar":
        if not nombre_evento or not nombre_evento.strip():
            return True, nombre_evento, dbc.Alert("Por favor ingresa un nombre", color="warning"), personas
        
        if not analisis_id:
            return False, "", "", personas
        
        try:
            # Crear/actualizar evento con nombre personalizado
            response = requests.put(
                f"{BACKEND_URL}/api/analisis/{analisis_id}/evento",
                params={"evento_nombre": nombre_evento.strip()},
                timeout=5
            )
            
            if response.status_code == 200:
                # Intentar leer id/nombre retornado
                try:
                    resp = response.json()
                    returned_id = resp.get("evento_id")
                    returned_name = resp.get("evento_nombre", nombre_evento.strip())
                except Exception:
                    returned_id = None
                    returned_name = nombre_evento.strip()

                # Actualizar los datos en el store
                if personas:
                    for persona in personas:
                        if persona.get("analisis_id") == analisis_id:
                            if returned_id is not None:
                                persona["evento_id"] = returned_id
                            persona["evento_nombre"] = returned_name

                return False, "", "", personas
            else:
                return True, nombre_evento, dbc.Alert("Error al guardar", color="danger"), personas
        except Exception as e:
            print(f"Error al guardar evento personalizado: {e}")
            return True, nombre_evento, dbc.Alert(f"Error: {str(e)}", color="danger"), personas
    
    return False, "", "", personas


# === Callbacks para Facebook Login (Multi-tenant) ===

@app.callback(
    Output("lista-candidatos-conectados", "children"),
    [Input("interval-actualizacion", "n_intervals"),
     Input("store-idioma", "data")],
    [State("store-sync-candidatos", "data"),
     State("store-facebook-user-id", "data")]
)
def cargar_candidatos_conectados(n, lang, sync_store, facebook_user_id):
    """Cargar lista de candidatos conectados."""
    # Si el usuario no está autenticado, no mostrar nada
    if not facebook_user_id:
        return dbc.Alert(
            [html.I(className="fab fa-facebook me-2"), "Conecta tu cuenta de Facebook para ver tus páginas."],
            color="info", className="mt-2"
        )
    # No re-renderizar si hay un sync activo — evita destruir el spinner/progress bar
    if sync_store and any(v.get("state") == "running" for v in sync_store.values()):
        raise PreventUpdate
    lang = lang or "es"
    try:
        params = {}
        if facebook_user_id:
            params["owner_facebook_user_id"] = facebook_user_id
        response = requests.get(f"{BACKEND_URL}/api/candidatos", params=params, timeout=5)
        if response.ok:
            candidatos = response.json()
            
            if not candidatos:
                return dbc.Alert(t("cand_sin_paginas", lang), color="warning", className="mt-2")
            
            items = []
            for candidato in candidatos:
                candidato_id = candidato.get('id')
                nombre = candidato.get('nombre', 'Sin nombre')
                facebook_page = candidato.get('facebook_page_name', 'N/A')
                instagram = candidato.get('instagram_username', 'N/A')
                whatsapp_number = candidato.get('whatsapp_phone_number', 'N/A')
                
                card = dbc.Card([
                    dbc.CardBody([
                        html.H6(nombre, className="card-title"),
                        html.P([
                            html.I(className="fab fa-facebook me-2 text-primary"),
                            f"Facebook: {facebook_page}"
                        ], className="mb-1 small"),
                        html.P([
                            html.I(className="fab fa-instagram me-2 text-danger"),
                            f"Instagram: @{instagram}" if instagram != 'N/A' else "Instagram: No conectado"
                        ], className="mb-1 small"),
                        html.P([
                            html.I(className="fab fa-whatsapp me-2 text-success"),
                            f"WhatsApp: {whatsapp_number}" if whatsapp_number != 'N/A' else "WhatsApp: No configurado"
                        ], className="mb-2 small"),
                        html.Div([
                            html.Small("Sincronizar desde:", className="text-muted d-block mb-1"),
                            dcc.DatePickerSingle(
                                id={"type": "date-sync-candidato", "index": candidato_id},
                                max_date_allowed=datetime.today().strftime("%Y-%m-%d"),
                                min_date_allowed="2020-01-01",
                                date=(datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d"),
                                initial_visible_month=(datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d"),
                                display_format="DD/MM/YYYY",
                                clearable=True,
                                style={"width": "100%", "fontSize": "0.8rem"},
                            ),
                        ], className="mb-2"),
                        html.Div([
                            html.Small("Máx. conversaciones:", className="text-muted d-block mb-1"),
                            dbc.Input(
                                id={"type": "input-limit-candidato", "index": candidato_id},
                                type="number",
                                value=50,
                                min=1,
                                max=500,
                                step=1,
                                size="sm",
                            ),
                        ], className="mb-2"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fas fa-sync-alt me-2"), t("cand_sincronizar", lang)],
                                    id={"type": "btn-sincronizar-candidato", "index": candidato_id},
                                    color="info",
                                    size="sm",
                                    className="w-100"
                                ),
                            ], width=6),
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fab fa-whatsapp me-2"), t("cand_config", lang)],
                                    id={"type": "btn-config-whatsapp", "index": candidato_id},
                                    color="success",
                                    size="sm",
                                    outline=True,
                                    className="w-100"
                                ),
                            ], width=6),
                        ]),
                        dbc.Switch(
                            id={"type": "switch-force-reprocess", "index": candidato_id},
                            label=t("cand_re_analizar", lang),
                            value=False,
                            className="mt-2 small"
                        ),
                        html.Div(id={"type": "status-sincronizacion", "index": candidato_id}, className="mt-2")
                    ])
                ], className="mb-2")
                
                items.append(card)
            
            return html.Div(items)
    except Exception as e:
        print(f"Error cargando candidatos: {e}")
        return dbc.Alert("Error cargando candidatos conectados", color="danger")
    
    return html.Div()


# Callback para sincronizar candidato individual (dispara job en background)
@app.callback(
    [Output("store-sync-candidatos", "data"),
     Output({"type": "status-sincronizacion", "index": dash.dependencies.ALL}, "children"),
     Output("interval-sync-candidato", "disabled"),
     Output("modal-loading-sync", "is_open"),
     Output("modal-loading-sync-bar", "children"),
     Output("modal-loading-sync-msg", "children")],
    Input({"type": "btn-sincronizar-candidato", "index": dash.dependencies.ALL}, "n_clicks"),
    [State("store-sync-candidatos", "data"),
     State({"type": "status-sincronizacion", "index": dash.dependencies.ALL}, "id"),
     State({"type": "switch-force-reprocess", "index": dash.dependencies.ALL}, "value"),
     State({"type": "date-sync-candidato", "index": dash.dependencies.ALL}, "date"),
     State({"type": "input-limit-candidato", "index": dash.dependencies.ALL}, "value")],
    prevent_initial_call=True
)
def iniciar_sync_candidato(all_clicks, store_data, all_ids, all_force, all_dates, all_limits):
    """Lanza sincronización en background; habilita el interval de polling."""
    ctx = dash.callback_context
    if not ctx.triggered or not any(c for c in all_clicks if c):
        raise PreventUpdate

    # Determinar cuál botón fue pulsado
    import json as _json
    prop = ctx.triggered[0]["prop_id"].replace(".n_clicks", "")
    try:
        clicked_id = _json.loads(prop)
        candidato_id = clicked_id["index"]
    except Exception:
        raise PreventUpdate

    # Determinar force_reprocess y desde_fecha para este candidato
    force = False
    desde_fecha = None
    limit = 50
    for id_dict, fval, dval, lval in zip(all_ids, all_force, all_dates, all_limits or []):
        if id_dict["index"] == candidato_id:
            force = bool(fval)
            desde_fecha = dval
            limit = int(lval) if lval else 50
            break

    # Construir parámetros de la llamada
    params = {"limit": limit, "force_reprocess": force}
    if desde_fecha:
        params["desde_fecha"] = desde_fecha
    else:
        params["meses_historico"] = 3

    # Llamar al endpoint (no bloqueante, retorna inmediatamente)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/candidatos/{candidato_id}/sincronizar",
            params=params,
            timeout=10
        )
        if not resp.ok:
            msg = resp.json().get("detail", "Error desconocido")
            ok = False
        else:
            data = resp.json()
            ok = data.get("ok", True)
            msg = data.get("message", "")
    except Exception as exc:
        ok = False
        msg = str(exc)

    store_data = store_data or {}
    statuses = []
    for id_dict in all_ids:
        cid = id_dict["index"]
        if cid == candidato_id:
            if ok:
                store_data[str(cid)] = {"state": "running", "progress": 0, "total": 0, "message": "Iniciando…"}
                statuses.append(html.Div([
                    dbc.Spinner(size="sm", color="info"),
                    html.Small(" Sincronizando…", className="text-muted")
                ]))
            else:
                statuses.append(dbc.Alert(f"Error: {msg}", color="danger", dismissable=True, duration=5000))
        else:
            statuses.append(dash.no_update)

    still_running = any(v.get("state") == "running" for v in store_data.values())
    # Abrir modal inmediatamente al iniciar
    if still_running:
        modal_bar = dbc.Progress(value=10, striped=True, animated=True, style={"height": "10px"})
        return store_data, statuses, not still_running, True, modal_bar, "Iniciando sincronización…"
    return store_data, statuses, not still_running, False, None, ""


@app.callback(
    [Output("store-sync-candidatos", "data", allow_duplicate=True),
     Output({"type": "status-sincronizacion", "index": dash.dependencies.ALL}, "children", allow_duplicate=True),
     Output("interval-sync-candidato", "disabled", allow_duplicate=True),
     Output("modal-loading-sync", "is_open", allow_duplicate=True),
     Output("modal-loading-sync-bar", "children", allow_duplicate=True),
     Output("modal-loading-sync-msg", "children", allow_duplicate=True)],
    Input("interval-sync-candidato", "n_intervals"),
    [State("store-sync-candidatos", "data"),
     State({"type": "status-sincronizacion", "index": dash.dependencies.ALL}, "id")],
    prevent_initial_call=True
)
def poll_sync_candidatos(n, store_data, all_ids):
    """Polling de progreso para sincronizaciones individuales."""
    if not store_data:
        raise PreventUpdate

    running = {k: v for k, v in store_data.items() if v.get("state") == "running"}
    if not running:
        raise PreventUpdate

    new_store = dict(store_data)
    statuses = []

    for id_dict in all_ids:
        cid = id_dict["index"]
        cid_str = str(cid)
        if cid_str not in running:
            statuses.append(dash.no_update)
            continue
        try:
            r = requests.get(f"{BACKEND_URL}/api/candidatos/{cid}/sync-status", timeout=5)
            if not r.ok:
                statuses.append(dash.no_update)
                continue
            job = r.json()
            new_store[cid_str] = job
            state = job.get("state", "idle")
            progress = job.get("progress", 0)
            total = job.get("total", 0)
            msg = job.get("message", "")

            if state == "running":
                fb_total = job.get("fb_total", 0)
                fb_prog  = job.get("fb_progress", 0)
                ig_total = job.get("ig_total", 0)
                ig_prog  = job.get("ig_progress", 0)
                phase    = job.get("phase", "")

                if fb_total > 0 or ig_total > 0:
                    # Show stacked bar: left half = FB (0-50%), right half = IG (0-50%)
                    fb_pct = int(fb_prog / fb_total * 50) if fb_total > 0 else (50 if phase == "instagram" else 0)
                    ig_pct = int(ig_prog / ig_total * 50) if ig_total > 0 else 0
                    # During FB phase, add small minimum so bar shows activity
                    if phase == "facebook" and fb_pct == 0:
                        fb_pct = 5
                    fb_label = f"FB {fb_prog}/{fb_total}" if fb_pct > 12 else ""
                    ig_label = f"IG {ig_prog}/{ig_total}" if ig_pct > 12 else ""
                    bar = dbc.Progress([
                        dbc.Progress(value=fb_pct, color="primary", bar=True, label=fb_label),
                        dbc.Progress(value=ig_pct, color="danger", bar=True, label=ig_label),
                    ], style={"height": "16px"}, className="mb-1")
                    status_text = msg
                else:
                    pct = int(progress / total * 100) if total > 0 else 20
                    bar = dbc.Progress(value=pct, striped=True, animated=True,
                                       style={"height": "16px"}, className="mb-1")
                    status_text = f"{msg}  ({progress}/{total})"

                statuses.append(html.Div([bar, html.Small(status_text, className="text-muted")]))
            elif state == "done":
                statuses.append(dbc.Alert(
                    [html.I(className="fas fa-check-circle me-2"), msg or f"✓ Completado ({progress} conversaciones)"],
                    color="success", dismissable=True, duration=8000
                ))
            elif state == "error":
                statuses.append(dbc.Alert(
                    [html.I(className="fas fa-exclamation-triangle me-2"), msg],
                    color="danger", dismissable=True
                ))
            else:
                statuses.append(dash.no_update)
        except Exception as exc:
            statuses.append(dash.no_update)

    still_running = any(v.get("state") == "running" for v in new_store.values())

    # Calcular estado del modal desde el job en curso (o cerrar si terminó)
    running_jobs = [(k, v) for k, v in new_store.items() if v.get("state") == "running"]
    if running_jobs:
        _, job = running_jobs[0]
        fb_prog  = job.get("fb_progress", 0)
        fb_total = job.get("fb_total", 0)
        ig_prog  = job.get("ig_progress", 0)
        ig_total = job.get("ig_total", 0)
        phase    = job.get("phase", "")
        modal_msg = job.get("message", "Sincronizando...")
        if fb_total > 0 or ig_total > 0:
            fb_pct = int(fb_prog / fb_total * 50) if fb_total > 0 else (50 if phase == "instagram" else 5)
            ig_pct = int(ig_prog / ig_total * 50) if ig_total > 0 else 0
            if phase == "facebook" and fb_pct == 0:
                fb_pct = 5
            fb_label = f"FB {fb_prog}/{fb_total}" if fb_pct > 12 else ""
            ig_label = f"IG {ig_prog}/{ig_total}" if ig_pct > 12 else ""
            modal_bar = dbc.Progress([
                dbc.Progress(value=fb_pct, color="primary", bar=True, label=fb_label),
                dbc.Progress(value=ig_pct, color="danger", bar=True, label=ig_label),
            ], style={"height": "10px"})
        else:
            prog  = job.get("progress", 0)
            total = job.get("total", 0)
            pct = max(10, int(prog / total * 100)) if total > 0 else 15
            modal_bar = dbc.Progress(value=pct, striped=True, animated=True, style={"height": "10px"})
        modal_open = True
    else:
        modal_open, modal_bar, modal_msg = False, None, ""

    return new_store, statuses, not still_running, modal_open, modal_bar, modal_msg


# Callback para abrir modal de configuración WhatsApp
@app.callback(
    [Output("modal-whatsapp-config", "is_open"),
     Output("store-candidato-whatsapp-id", "data")],
    [Input({"type": "btn-config-whatsapp", "index": dash.dependencies.ALL}, "n_clicks"),
     Input("btn-whatsapp-cancel", "n_clicks"),
     Input("btn-whatsapp-save", "n_clicks")],
    [State("modal-whatsapp-config", "is_open"),
     State({"type": "btn-config-whatsapp", "index": dash.dependencies.ALL}, "id")],
    prevent_initial_call=True
)
def toggle_modal_whatsapp(btn_config_clicks, btn_cancel, btn_save, is_open, btn_ids):
    """Abrir/cerrar modal de configuración WhatsApp."""
    ctx = dash.callback_context
    
    if not ctx.triggered:
        raise PreventUpdate
    
    trigger_id = ctx.triggered[0]["prop_id"]
    
    # Cerrar modal
    if "btn-whatsapp-cancel" in trigger_id or "btn-whatsapp-save" in trigger_id:
        return False, None
    
    # Abrir modal - identificar qué botón se presionó
    if "btn-config-whatsapp" in trigger_id:
        # Encontrar el botón que fue clickeado
        for i, clicks in enumerate(btn_config_clicks):
            if clicks:
                candidato_id = btn_ids[i]["index"]
                return True, candidato_id
    
    return is_open, None


# Callback para guardar configuración de WhatsApp
@app.callback(
    Output("whatsapp-config-status", "children"),
    Input("btn-whatsapp-save", "n_clicks"),
    [State("store-candidato-whatsapp-id", "data"),
     State("input-whatsapp-phone-id", "value"),
     State("input-whatsapp-business-id", "value"),
     State("input-whatsapp-phone-number", "value")],
    prevent_initial_call=True
)
def guardar_config_whatsapp(n_clicks, candidato_id, phone_id, business_id, phone_number):
    """Guardar configuración de WhatsApp para el candidato."""
    if not n_clicks or not candidato_id:
        raise PreventUpdate
    
    # Validar campos
    if not phone_id or not business_id or not phone_number:
        return dbc.Alert(
            "Por favor completa todos los campos",
            color="warning",
            dismissable=True
        )
    
    try:
        # Llamar endpoint de configuración
        response = requests.post(
            f"{BACKEND_URL}/api/candidatos/{candidato_id}/configurar-whatsapp",
            params={
                "whatsapp_phone_number_id": phone_id,
                "whatsapp_business_account_id": business_id,
                "whatsapp_phone_number": phone_number
            },
            timeout=5
        )
        
        if response.ok:
            data = response.json()
            return dbc.Alert(
                [
                    html.I(className="fas fa-check-circle me-2"),
                    f"WhatsApp configurado correctamente para {data.get('candidato', {}).get('nombre', 'candidato')}"
                ],
                color="success",
                dismissable=True
            )
        else:
            error_detail = response.json().get("detail", "Error desconocido")
            return dbc.Alert(
                f"Error: {error_detail}",
                color="danger",
                dismissable=True
            )
            
    except Exception as e:
        print(f"Error al configurar WhatsApp: {e}")
        return dbc.Alert(
            f"Error de conexión: {str(e)}",
            color="danger",
            dismissable=True
        )


# === Callbacks para selección de páginas de Facebook ===

@app.callback(
    [Output("modal-pages-selection", "is_open"),
     Output("checklist-paginas", "options"),
     Output("checklist-paginas", "value")],
    [Input("store-facebook-pages", "data"),
     Input("btn-pages-cancel", "n_clicks"),
     Input("btn-pages-connect", "n_clicks")],
    [State("modal-pages-selection", "is_open")],
    prevent_initial_call=True
)
def toggle_pages_modal(pages_data, cancel_clicks, connect_clicks, is_open):
    """Abrir modal cuando hay páginas disponibles y manejar cerrado."""
    ctx = dash.callback_context
    trigger = ctx.triggered_id if ctx.triggered else None
    print(f"[toggle_pages_modal] trigger={trigger}, pages_data tipo={type(pages_data)}, len={len(pages_data) if pages_data else 0}")

    if trigger in ("btn-pages-cancel", "btn-pages-connect"):
        return False, [], []

    if pages_data:
        options = []
        for page in pages_data:
            page_name = page.get('page_name', 'Página sin nombre')
            instagram_username = page.get('instagram_username')
            is_admin = page.get('is_admin', True)

            label_text = f"📘 {page_name}"
            if instagram_username:
                label_text += f" + 📷 @{instagram_username}"
            label_text += " ✔ Admin" if is_admin else " ⚠ Limited access"

            options.append({'label': label_text, 'value': page.get('page_id')})

        all_values = [opt['value'] for opt in options]
        print(f"[toggle_pages_modal] Abriendo modal con {len(options)} páginas: {[o['value'] for o in options]}")
        return True, options, all_values

    return False, [], []


@app.callback(
    Output("pages-selection-status", "children"),
    Input("btn-pages-connect", "n_clicks"),
    [State("checklist-paginas", "value"),
     State("store-facebook-pages", "data"),
     State("store-facebook-user-id", "data"),
     State("store-instagram-access-token", "data")],
    prevent_initial_call=True
)
def conectar_paginas_seleccionadas(n_clicks, selected_page_ids, pages_data, facebook_user_id, instagram_access_token):
    """Conectar las páginas seleccionadas."""
    if not n_clicks or not selected_page_ids or not pages_data:
        raise PreventUpdate
    
    try:
        # Filtrar solo las páginas seleccionadas
        selected_pages = [page for page in pages_data if page.get('page_id') in selected_page_ids]
        
        if not selected_pages:
            return dbc.Alert("No hay páginas seleccionadas", color="warning", dismissable=True)
        
        # Enviar al backend
        payload = {"pages": selected_pages}
        if facebook_user_id:
            payload["facebook_user_id"] = facebook_user_id
        if instagram_access_token:
            payload["instagram_access_token"] = instagram_access_token

        response = requests.post(
            f"{BACKEND_URL}/api/candidatos/conectar-paginas",
            json=payload,
            timeout=10
        )
        
        if response.ok:
            data = response.json()
            creados = data.get('total_creados', 0)
            actualizados = data.get('total_actualizados', 0)
            errores = data.get('total_errores', 0)
            
            mensaje_parts = []
            if creados > 0:
                mensaje_parts.append(f"{creados} página(s) nueva(s) conectada(s)")
            if actualizados > 0:
                mensaje_parts.append(f"{actualizados} página(s) actualizada(s)")
            
            mensaje = " y ".join(mensaje_parts)
            
            if errores > 0:
                mensaje += f". {errores} error(es) encontrado(s)"
                color = "warning"
            else:
                color = "success"
            
            return dbc.Alert(
                [
                    html.I(className="fas fa-check-circle me-2"),
                    mensaje,
                    html.Br(),
                    html.Small("Refresca la página para ver las páginas conectadas", className="text-muted")
                ],
                color=color,
                dismissable=True
            )
        else:
            error_detail = response.json().get("detail", "Error desconocido")
            return dbc.Alert(
                f"Error: {error_detail}",
                color="danger",
                dismissable=True
            )
            
    except Exception as e:
        print(f"Error conectando páginas: {e}")
        return dbc.Alert(
            f"Error de conexión: {str(e)}",
            color="danger",
            dismissable=True
        )


# === Callback modal Política de Privacidad ===
@app.callback(
    Output("modal-privacidad", "is_open"),
    [Input("btn-abrir-privacidad", "n_clicks"),
     Input("btn-privacidad-cerrar", "n_clicks")],
    State("modal-privacidad", "is_open"),
    prevent_initial_call=True
)
def toggle_modal_privacidad(abrir, cerrar, is_open):
    return not is_open


# === Callbacks de Idioma ===

@app.callback(
    Output("store-idioma", "data"),
    Input("btn-idioma", "n_clicks"),
    State("store-idioma", "data"),
    prevent_initial_call=True
)
def cambiar_idioma(n_clicks, lang):
    """Alternar entre español e inglés."""
    return "en" if (lang or "es") == "es" else "es"


@app.callback(
    [Output("sidebar-titulo", "children"),
     Output("label-fecha-desde", "children"),
     Output("label-fecha-hasta", "children"),
     Output("label-genero-filtro", "children"),
     Output("filtro-genero", "placeholder"),
     Output("label-rango-edad", "children"),
     Output("label-intereses-filtro", "children"),
     Output("filtro-intereses", "placeholder"),
     Output("label-ubicacion-filtro", "children"),
     Output("filtro-ubicacion", "placeholder"),
     Output("btn-buscar", "children"),
     Output("btn-limpiar", "children"),
     Output("btn-exportar", "children"),
     Output("btn-idioma", "children"),
     Output("texto-dashboard-titulo", "children"),
     Output("texto-dashboard-subtitulo", "children"),
     Output("texto-ch-conexion-fb", "children"),
     Output("texto-desc-fb", "children"),
     Output("texto-btn-conectar-fb", "children"),
     Output("texto-paginas-conectadas", "children"),
     Output("label-stat-total-personas", "children"),
     Output("label-stat-resultados", "children"),
     Output("label-stat-conversaciones", "children"),
     Output("label-stat-ultima-act", "children"),
     Output("ch-dist-genero", "children"),
     Output("ch-intereses-comunes", "children"),
     Output("ch-resultados-busqueda", "children"),
     Output("btn-abrir-privacidad", "children"),
     Output("btn-abrir-logs", "children")],
    Input("store-idioma", "data")
)
def actualizar_textos_ui(lang):
    """Actualizar todos los textos de la interfaz según el idioma seleccionado."""
    lang = lang or "es"
    return [
        t("filtros", lang),
        t("fecha_desde", lang),
        t("fecha_hasta", lang),
        t("genero_label", lang),
        t("seleccionar_genero", lang),
        t("rango_edad", lang),
        t("intereses_label", lang),
        t("seleccionar_intereses", lang),
        t("ubicacion_label", lang),
        t("ubicacion_placeholder", lang),
        [html.I(className="fas fa-search me-2"), t("buscar", lang)],
        [html.I(className="fas fa-redo me-2"), t("limpiar", lang)],
        [html.I(className="fas fa-download me-2"), t("exportar_csv", lang)],
        [html.I(className="fas fa-globe me-2"), t("cambiar_idioma_btn", lang)],
        t("dashboard_titulo", lang),
        t("dashboard_subtitulo", lang),
        t("conexion_fb_header", lang),
        t("conexion_fb_desc", lang),
        t("conectar_fb_btn", lang),
        t("paginas_conectadas", lang),
        t("stat_total_personas", lang),
        t("stat_resultados", lang),
        t("stat_conversaciones", lang),
        t("stat_ultima_act", lang),
        t("grafico_genero_header", lang),
        t("grafico_intereses_header", lang),
        t("resultados_busqueda_header", lang),
        t("footer_privacidad", lang),
        [html.I(className="fas fa-terminal me-1"), t("footer_logs", lang)],
    ]


if __name__ == "__main__":
    app.run(
        host=config.FRONTEND_HOST,
        port=config.FRONTEND_PORT,
        debug=config.DEBUG
    )
