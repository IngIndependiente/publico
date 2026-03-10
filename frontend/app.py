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
                        dbc.Row([
                dbc.Col([
                            dbc.Button(
                                [html.I(className="fas fa-sync me-2"), "Sync"],
                                id="btn-sync",
                                color="warning",
                                className="w-100 mt-3"
                            ),
                        ]),
                    ]),
                        # Modal para contraseña
                        dbc.Modal([
                            dbc.ModalHeader("Confirmar sincronización", id="modal-sync-header"),
                            dbc.ModalBody([
                                dbc.Input(id="input-sync-password", type="password", placeholder="Contraseña"),
                                html.Div(id="sync-modal-status", className="mt-2"),
                                dbc.Progress(
                                    id="sync-progress",
                                    value=0,
                                    striped=True,
                                    animated=True,
                                    style={"height": "20px", "display": "none"},
                                    className="mt-2 mb-1"
                                ),
                                html.H6("Sync logs", className="mt-3", id="sync-logs-label"),
                                html.Pre(id="sync-log", style={
                                    'maxHeight': '300px',
                                    'overflowY': 'auto',
                                    'whiteSpace': 'pre-wrap',
                                    'fontSize': '0.8rem',
                                    'backgroundColor': '#f8f9fa',
                                    'padding': '8px',
                                    'borderRadius': '4px'
                                }),
                            ]),
                            dbc.ModalFooter([
                                dbc.Button("Cancelar", id="btn-sync-cancel", className="me-2"),
                                dbc.Button("Iniciar Sync", id="btn-sync-confirm", color="primary")
                            ])
                        ], id="modal-sync", is_open=False),
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
                        dbc.CardHeader([
                            html.H5("Resultados de Búsqueda", className="mb-0", id="ch-resultados-busqueda")
                        ]),
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
                        'maxHeight': '500px',
                        'overflowY': 'auto',
                        'padding': '10px'
                    })
                ]),
                dbc.ModalFooter(
                    dbc.Button("Cerrar", id="modal-conversacion-cerrar", className="ms-auto")
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
            
            # Modal selección de páginas de Facebook/Instagram
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
            
            # Store para datos
            dcc.Store(id="store-datos-personas"),
            dcc.Store(id="store-stats-filtradas"),
            dcc.Store(id="store-estadisticas"),
            dcc.Store(id="store-conversacion-actual"),
            dcc.Store(id="store-analisis-evento-actual"),  # Para guardar el análisis que está editando evento
            dcc.Store(id="store-sync-status"),
            dcc.Store(id="store-candidato-whatsapp-id"),  # Para guardar el candidato que está configurando WhatsApp
            dcc.Store(id="store-facebook-pages"),  # Para guardar páginas de Facebook
            dcc.Store(id="store-url-params"),  # Para detectar parámetros de URL
            dcc.Store(id="store-facebook-user-id"),  # facebook_user_id del usuario autenticado
            dcc.Store(id="store-instagram-access-token"),  # Token de usuario para Instagram Messaging API
            dcc.Store(id="store-idioma", data="es"),  # Idioma seleccionado: "es" o "en"
            dcc.Store(id="store-sync-candidatos", data={}),  # {candidato_id_str: job_state_dict}
            dcc.Interval(id="interval-sync-poll", interval=2000, n_intervals=0, disabled=True),
            dcc.Interval(id="interval-sync-candidato", interval=2500, n_intervals=0, disabled=True),
            # Interval para actualización automática
            dcc.Interval(
                id="interval-actualizacion",
                interval=30*1000,  # 30 segundos
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
     Output('url', 'pathname'),
     Output('url', 'search'),
     Output('store-facebook-user-id', 'data'),
     Output('store-instagram-access-token', 'data')],
    Input('url', 'href'),
    prevent_initial_call=False
)
def cargar_paginas_oauth(href):
    """Detecta oauth_token en la URL y recupera las páginas del backend."""
    if not href or 'oauth_token=' not in href:
        raise PreventUpdate
    
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        token = params.get('oauth_token', [None])[0]
        
        if not token:
            raise PreventUpdate
        
        response = requests.get(f"{BACKEND_URL}/api/oauth-session/{token}", timeout=10)
        if response.ok:
            data = response.json()
            pages = data.get('pages', [])
            facebook_user_id = data.get('facebook_user_id')
            instagram_access_token = data.get('instagram_access_token')
            if pages:
                # Limpiar el token de la URL (pathname y search)
                return pages, '/', '', facebook_user_id, instagram_access_token
    except Exception as e:
        print(f"Error recuperando sesión OAuth: {e}")
    
    raise PreventUpdate


# === Callbacks ===

@app.callback(
    [Output("store-estadisticas", "data"),
     Output("stat-total-personas", "children"),
     Output("stat-conversaciones", "children")],
    [Input("interval-actualizacion", "n_intervals")]
)
def actualizar_estadisticas(n):
    """Actualizar estadísticas generales."""
    try:
        response = requests.get(f"{BACKEND_URL}/api/stats", timeout=5)
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
     Output("store-stats-filtradas", "data")],
    [Input("btn-buscar", "n_clicks"),
     Input("interval-actualizacion", "n_intervals")],
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
def buscar_personas(n_clicks, n_intervals, fecha_inicio, fecha_fin, genero, edad_min, edad_max, intereses, ubicacion, facebook_user_id):
    """Buscar personas según filtros."""
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
            stats = data.get("stats", {}) # Obtener estadísticas
            print(f"[buscar_personas] OK – total={total}, personas={len(personas)}, stats={stats}")
            ahora = ahora_cl().strftime("%d/%m/%Y %H:%M:%S")
            return personas, str(total), ahora, stats
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

    return [], "0", "Error", {}


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
        
        analisis_id = p.get("analisis_id") or 0
        evento_nombre = p.get("evento_nombre") or "Sin asignar"
        
        row = html.Tr([
            html.Td(
                dbc.Button(
                    [html.I(className="fas fa-comments me-1"), t("tabla_ver", lang)],
                    id={"type": "btn-ver-conversacion", "index": analisis_id},
                    color="primary" if analisis_id else "secondary",
                    size="sm",
                    className="w-100",
                    disabled=not analisis_id,
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
                    id={"type": "dropdown-evento", "index": analisis_id},
                    className="evento-dropdown",
                    style={'minWidth': '150px'},
                    clearable=False
                ),
                html.Div(id={"type": "evento-status", "index": analisis_id}, style={'fontSize': '0.7rem', 'marginTop': '2px'})
            ], id={"type": "td-evento", "index": analisis_id}),
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
     Output("store-conversacion-actual", "data")],
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
        return False, None
    
    trigger_id = ctx.triggered[0]["prop_id"]
    
    # Si se clickeó cerrar
    if "modal-conversacion-cerrar" in trigger_id:
        return False, None
    
    # Si se clickeó ver conversación
    if "btn-ver-conversacion" in trigger_id:
        # Encontrar cuál botón fue clickeado
        for i, clicks in enumerate(btn_ver_clicks):
            if clicks:
                analisis_id = btn_ids[i]["index"]
                return True, analisis_id
    
    return False, None


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
    Output("info-exportacion", "children"),
    [Input("btn-exportar", "n_clicks")],
    [State("filtro-fecha-inicio", "value"),
     State("filtro-fecha-fin", "value"),
     State("filtro-genero", "value"),
     State("filtro-edad-min", "value"),
     State("filtro-edad-max", "value"),
     State("filtro-intereses", "value"),
     State("filtro-ubicacion", "value")],
    prevent_initial_call=True
)
def exportar_csv(n_clicks, fecha_inicio, fecha_fin, genero, edad_min, edad_max, intereses, ubicacion):
    """Exportar resultados a CSV."""
    if not n_clicks:
        return ""
    
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
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/personas/exportar",
            json=payload,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            return dbc.Alert(
                [
                    html.I(className="fas fa-check-circle me-2"),
                    f"Exportado: {data['filename']} ({data['total_registros']} registros)"
                ],
                color="success",
                className="small mt-2"
            )
    except Exception as e:
        return dbc.Alert(
            [html.I(className="fas fa-exclamation-triangle me-2"), f"Error: {str(e)}"],
            color="danger",
            className="small mt-2"
        )
    
    return dbc.Alert("Error al exportar", color="danger", className="small mt-2")


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
     Input("store-idioma", "data")]
)
def cargar_candidatos_conectados(n, lang):
    """Cargar lista de candidatos conectados."""
    lang = lang or "es"
    try:
        response = requests.get(f"{BACKEND_URL}/api/candidatos", timeout=5)
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
     Output("interval-sync-candidato", "disabled")],
    Input({"type": "btn-sincronizar-candidato", "index": dash.dependencies.ALL}, "n_clicks"),
    [State("store-sync-candidatos", "data"),
     State({"type": "status-sincronizacion", "index": dash.dependencies.ALL}, "id"),
     State({"type": "switch-force-reprocess", "index": dash.dependencies.ALL}, "value")],
    prevent_initial_call=True
)
def iniciar_sync_candidato(all_clicks, store_data, all_ids, all_force):
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

    # Determinar force_reprocess para este candidato
    force = False
    for id_dict, fval in zip(all_ids, all_force):
        if id_dict["index"] == candidato_id:
            force = bool(fval)
            break

    # Llamar al endpoint (no bloqueante, retorna inmediatamente)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/candidatos/{candidato_id}/sincronizar",
            params={"limit": 50, "force_reprocess": force, "meses_historico": 3},
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
                    dbc.Spinner(size="sm", color="info", className="me-2"),
                    html.Small("Sincronizando…", className="text-muted")
                ]))
            else:
                statuses.append(dbc.Alert(f"Error: {msg}", color="danger", dismissable=True, duration=5000))
        else:
            statuses.append(dash.no_update)

    still_running = any(v.get("state") == "running" for v in store_data.values())
    return store_data, statuses, not still_running


@app.callback(
    [Output("store-sync-candidatos", "data", allow_duplicate=True),
     Output({"type": "status-sincronizacion", "index": dash.dependencies.ALL}, "children", allow_duplicate=True),
     Output("interval-sync-candidato", "disabled", allow_duplicate=True)],
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
            pct = int(progress / total * 100) if total > 0 else 50

            if state == "running":
                statuses.append(html.Div([
                    dbc.Progress(value=pct, striped=True, animated=True,
                                 style={"height": "6px"}, className="mb-1"),
                    html.Small(f"{msg}  ({progress}/{total})", className="text-muted")
                ]))
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
    return new_store, statuses, not still_running


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
    prevent_initial_call=False
)
def toggle_pages_modal(pages_data, cancel_clicks, connect_clicks, is_open):
    """Abrir modal cuando hay páginas disponibles y manejar cerrado."""
    ctx = dash.callback_context
    
    if not ctx.triggered:
        # Checklist inicial vacío
        return False, [], []
    
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    # Cerrar modal
    if trigger_id in ["btn-pages-cancel", "btn-pages-connect"]:
        return False, [], []
    
    # Si llegan páginas nuevas, abrir modal
    if trigger_id == "store-facebook-pages" and pages_data and len(pages_data) > 0:
        # Crear opciones para el checklist
        options = []
        for page in pages_data:
            page_name = page.get('page_name', 'Página sin nombre')
            instagram_username = page.get('instagram_username')
            
            label_text = f"📘 {page_name}"
            if instagram_username:
                label_text += f" + 📷 @{instagram_username}"
            
            options.append({
                'label': label_text,
                'value': page.get('page_id')
            })
        
        # Seleccionar todas por defecto
        all_values = [opt['value'] for opt in options]
        
        return True, options, all_values
    
    return is_open, [], []


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


# === Callbacks para Sync ===

@app.callback(
    Output("modal-sync", "is_open"),
    [
        Input("btn-sync", "n_clicks"),
        Input("btn-sync-cancel", "n_clicks"),
        Input("btn-sync-confirm", "n_clicks"),
    ],
    [State("modal-sync", "is_open")]
)
def toggle_sync_modal(open_click, cancel_click, confirm_click, is_open):
    """Abrir modal al presionar `Sync`; cerrarlo si cancela o confirma."""
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger = ctx.triggered[0]["prop_id"]
    # Abrir solo con el botón principal
    if "btn-sync" in trigger:
        return True
    # Cerrar si se presionó cancelar
    if "btn-sync-cancel" in trigger:
        return False
    # Si se presionó confirmar, mantener modal abierto para mostrar logs
    if "btn-sync-confirm" in trigger:
        return True
    return is_open

@app.callback(
    Output("sync-log", "children"),
    Output("sync-modal-status", "children"),
    Output("store-sync-status", "data"),
    Output("interval-sync-poll", "disabled"),
    Output("sync-progress", "value"),
    Output("sync-progress", "style"),
    Output("sync-progress", "color"),
    Input("btn-sync-confirm", "n_clicks"),
    Input("interval-sync-poll", "n_intervals"),
    State("input-sync-password", "value"),
    prevent_initial_call=True,
)
def handle_sync(confirm_click, n_intervals, password):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger = ctx.triggered[0]["prop_id"]

    _progress_running = {"height": "20px", "display": "block"}
    _progress_hidden  = {"height": "20px", "display": "none"}

    if "btn-sync-confirm" in trigger:
        res = control.request_sync(password or "")
        if not res.get("ok"):
            logs = "\n".join(control.get_logs(200))
            return logs, dbc.Alert(res.get("msg", "Error"), color="danger"), dash.no_update, True, 0, _progress_hidden, "primary"
        status = control.get_status()
        logs = "\n".join(control.get_logs(200))
        return logs, dbc.Alert("Sincronización iniciada...", color="info"), status, False, 30, _progress_running, "info"

    if "interval-sync-poll" in trigger:
        status = control.get_status()
        state = status.get("state")
        logs = "\n".join(control.get_logs(500))
        if state in ("finished", "error", "idle", "stopped"):
            if state == "finished":
                modal_msg = dbc.Alert("Sincronización completada ✓", color="success")
                prog_val, prog_color = 100, "success"
            elif state == "error":
                modal_msg = dbc.Alert(f"Error: {status.get('message','')}", color="danger")
                prog_val, prog_color = 100, "danger"
            else:
                modal_msg = dbc.Alert(status.get('message', 'Finalizado'), color="info")
                prog_val, prog_color = 100, "info"
            return logs, modal_msg, status, True, prog_val, _progress_running, prog_color
        # Sigue corriendo - mover la barra
        log_line = status.get('message', '')
        modal_msg = dbc.Alert(log_line, color="info") if log_line else dash.no_update
        return logs, modal_msg, status, False, 60, _progress_running, "info"

    raise PreventUpdate

@app.callback(
    Output("page-content", "style"),
    Input("store-sync-status", "data")
)
def show_loading_overlay(status):
    if not status:
        return CONTENT_STYLE
    state = status.get("state")
    if state == "running_sync":
        # simple style change to indicate loading; you can replace with modal overlay
        s = CONTENT_STYLE.copy()
        s.update({"opacity": "0.4", "pointerEvents": "none"})
        return s
    return CONTENT_STYLE


@app.callback(
    Output("sync-log", "style"),
    Input("store-sync-status", "data")
)
def toggle_sync_log(status):
    """Mostrar el área de logs cuando exista estado de sync (iniciado)."""
    if not status:
        return { 'display': 'none' }
    # mostrar el area con el mismo estilo que antes
    return {
        'display': 'block',
        'maxHeight': '200px',
        'overflowY': 'auto',
        'whiteSpace': 'pre-wrap',
        'fontSize': '0.8rem',
        'backgroundColor': '#f8f9fa',
        'padding': '8px',
        'borderRadius': '4px'
    }


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
     Output("btn-sync", "children"),
     Output("modal-sync-header", "children"),
     Output("input-sync-password", "placeholder"),
     Output("sync-logs-label", "children"),
     Output("btn-sync-cancel", "children"),
     Output("btn-sync-confirm", "children"),
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
        [html.I(className="fas fa-sync me-2"), t("sync_btn", lang)],
        t("confirmar_sync", lang),
        t("password_placeholder", lang),
        t("sync_logs_label", lang),
        t("cancelar", lang),
        t("iniciar_sync", lang),
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
