"""Frontend con Dash - Interfaz responsive para consulta de personas."""
import dash
from dash import dcc, html, Input, Output, State, dash_table
import json
import dash_bootstrap_components as dbc
import requests
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go



import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend import control
from backend import config
from dash.exceptions import PreventUpdate

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
            html.H2("Filtros", className="display-6"),
            html.Hr(),
            
            # Fecha
            html.Label("Fecha Desde", className="fw-bold"),
            dbc.Input(
                id="filtro-fecha-inicio",
                type="date",
                placeholder="YYYY-MM-DD",
                className="mb-2"
            ),
            html.Label("Fecha Hasta", className="fw-bold"),
            dbc.Input(
                id="filtro-fecha-fin",
                type="date",
                placeholder="YYYY-MM-DD",
                className="mb-3"
            ),

            html.Hr(),
            
            # Género
            html.Label("Género", className="fw-bold mt-3"),
            dcc.Dropdown(
                id="filtro-genero",
                options=[{"label": g, "value": g} for g in config.GENEROS],
                placeholder="Seleccionar género",
                clearable=True,
                className="mb-3"
            ),
            
            # Edad
            html.Label("Rango de Edad", className="fw-bold mt-3"),
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
            html.Label("Intereses", className="fw-bold mt-3"),
            dcc.Dropdown(
                id="filtro-intereses",
                options=[{"label": i, "value": i} for i in config.CATEGORIAS_INTERES],
                placeholder="Seleccionar intereses",
                multi=True,
                className="mb-3"
            ),
            
            # Ubicación
            html.Label("Ubicación", className="fw-bold mt-3"),
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
                            dbc.ModalHeader("Confirmar sincronización"),
                            dbc.ModalBody([
                                dbc.Input(id="input-sync-password", type="password", placeholder="Contraseña"),
                                html.Div(id="sync-modal-status", className="mt-2"),
                                html.H6("Sync logs", className="mt-3"),
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
                    html.H1("Dashboard - Agente Político", className="display-4"),
                    html.P(
                        "Sistema de análisis de conversaciones y gestión de contactos ciudadanos",
                        className="lead"
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
                            "Conexión con Facebook/Instagram"
                        ]),
                        dbc.CardBody([
                            html.P(
                                "Conecta tu página de Facebook e Instagram Business para recibir mensajes automáticamente.",
                                className="text-muted"
                            ),
                            html.A(
                                dbc.Button(
                                    [
                                        html.I(className="fab fa-facebook me-2"),
                                        "Conectar Facebook/Instagram"
                                    ],
                                    color="primary",
                                    size="lg",
                                    className="mb-3"
                                ),
                                href=f"{BACKEND_URL}/auth/facebook/login",
                                target="_blank",
                                id="btn-conectar-facebook"
                            ),
                            html.Hr(),
                            html.H6("Páginas Conectadas:", className="fw-bold"),
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
                            html.H4("Total Personas", className="card-title"),
                            html.H2(id="stat-total-personas", className="text-primary"),
                        ])
                    ], className="mb-3")
                ], width=12, lg=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Resultados", className="card-title"),
                            html.H2(id="stat-resultados", className="text-success"),
                        ])
                    ], className="mb-3")
                ], width=12, lg=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Conversaciones", className="card-title"),
                            html.H2(id="stat-conversaciones", className="text-info"),
                        ])
                    ], className="mb-3")
                ], width=12, lg=3),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4("Última Actualización", className="card-title"),
                            html.P(id="stat-actualizacion", className="mb-0"),
                        ])
                    ], className="mb-3")
                ], width=12, lg=3),
            ], className="mb-4"),
            
            # Gráficos
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Distribución por Género"),
                        dbc.CardBody([
                            dcc.Graph(id="grafico-genero")
                        ])
                    ], className="mb-3")
                ], width=12, lg=6),
                
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Intereses más Comunes"),
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
                            html.H5("Resultados de Búsqueda", className="mb-0")
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
            dcc.Interval(id="interval-sync-poll", interval=2000, n_intervals=0, disabled=True),
            # Interval para actualización automática
            dcc.Interval(
                id="interval-actualizacion",
                interval=30*1000,  # 30 segundos
                n_intervals=0
            ),
        ],
        style=CONTENT_STYLE,
        id="page-content"
    )


# Layout principal
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    crear_sidebar(),
    crear_contenido()
])


# === Clientside callback para leer páginas de sessionStorage ===
app.clientside_callback(
    """
    function(n_intervals) {
        // Leer páginas de sessionStorage
        const pagesStr = sessionStorage.getItem('facebook_pages');
        if (pagesStr) {
            try {
                const pages = JSON.parse(pagesStr);
                // Limpiar sessionStorage después de leer
                sessionStorage.removeItem('facebook_pages');
                return pages;
            } catch(e) {
                console.error('Error parsing pages:', e);
                return [];
            }
        }
        return [];
    }
    """,
    Output('store-facebook-pages', 'data'),
    Input('interval-actualizacion', 'n_intervals')
)


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
    [Input("store-stats-filtradas", "data")]
)
def actualizar_graficos(stats):
    """Actualizar gráficos de estadísticas."""
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
            title="Distribución por Género (Filtrado)",
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
            title="Intereses más Comunes (Filtrado)",
            labels={"x": "Cantidad de Personas", "y": "Categoría"}
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
     State("filtro-ubicacion", "value")],
    prevent_initial_call=False
)
def buscar_personas(n_clicks, n_intervals, fecha_inicio, fecha_fin, genero, edad_min, edad_max, intereses, ubicacion):
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
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/personas/buscar",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            personas = data.get("personas", [])
            total = data.get("total", 0)
            stats = data.get("stats", {}) # Obtener estadísticas
            
            ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            return personas, str(total), ahora, stats
    except Exception as e:
        print(f"Error al buscar: {e}")
    
    return [], "0", "Error", {}


@app.callback(
    Output("tabla-resultados", "children"),
    [Input("store-datos-personas", "data")]
)
def actualizar_tabla(personas):
    """Actualizar tabla de resultados."""
    if not personas:
        return html.Div(
            dbc.Alert("No hay resultados para mostrar", color="info"),
            className="text-center"
        )
    
    # Crear tabla con botones
    rows = []
    for p in personas:
        # Formatear nombre con usuario
        nombre = p.get("nombre_completo") or "Sin identificar"
        usuario = p.get("facebook_username") or p.get("instagram_username")
        
        if usuario:
            nombre_display = f"{nombre} (@{usuario})"
        else:
            nombre_display = nombre
        
        analisis_id = p.get("analisis_id", 0)
        evento_nombre = p.get("evento_nombre") or "Sin asignar"
        
        row = html.Tr([
            html.Td(
                dbc.Button(
                    [html.I(className="fas fa-comments me-1"), "Ver"],
                    id={"type": "btn-ver-conversacion", "index": analisis_id},
                    color="primary",
                    size="sm",
                    className="w-100"
                ),
                style={'width': '100px', 'textAlign': 'center'}
            ),
            html.Td(datetime.fromisoformat(p["fecha_ultimo_contacto"]).strftime("%Y-%m-%d %H:%M") if p.get("fecha_ultimo_contacto") else "N/A"),
            html.Td(nombre_display),
            html.Td(p.get("resumen_conversacion") or "N/A", style={'maxWidth': '300px'}),
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
                html.Th("Acción"),
                html.Th("Fecha"),
                html.Th("Nombre"),
                html.Th("Resumen Conv."),
                html.Th("Evento"),
                html.Th("Edad"),
                html.Th("Género"),
                html.Th("Teléfono"),
                html.Th("Email"),
                html.Th("Ubicación"),
                html.Th("Intereses"),
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
    [Input("interval-actualizacion", "n_intervals")]
)
def cargar_candidatos_conectados(n):
    """Cargar lista de candidatos conectados."""
    try:
        response = requests.get(f"{BACKEND_URL}/api/candidatos", timeout=5)
        if response.ok:
            candidatos = response.json()
            
            if not candidatos:
                return dbc.Alert("No hay páginas conectadas. Haz clic en el botón para conectar.", color="warning", className="mt-2")
            
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
                                    [html.I(className="fas fa-sync-alt me-2"), "Sincronizar"],
                                    id={"type": "btn-sincronizar-candidato", "index": candidato_id},
                                    color="info",
                                    size="sm",
                                    className="w-100"
                                ),
                            ], width=6),
                            dbc.Col([
                                dbc.Button(
                                    [html.I(className="fab fa-whatsapp me-2"), "Config"],
                                    id={"type": "btn-config-whatsapp", "index": candidato_id},
                                    color="success",
                                    size="sm",
                                    outline=True,
                                    className="w-100"
                                ),
                            ], width=6),
                        ]),
                        html.Div(id={"type": "status-sincronizacion", "index": candidato_id}, className="mt-2")
                    ])
                ], className="mb-2")
                
                items.append(card)
            
            return html.Div(items)
    except Exception as e:
        print(f"Error cargando candidatos: {e}")
        return dbc.Alert("Error cargando candidatos conectados", color="danger")
    
    return html.Div()


# Callback para sincronizar candidato individual
@app.callback(
    Output({"type": "status-sincronizacion", "index": dash.dependencies.MATCH}, "children"),
    Input({"type": "btn-sincronizar-candidato", "index": dash.dependencies.MATCH}, "n_clicks"),
    State({"type": "btn-sincronizar-candidato", "index": dash.dependencies.MATCH}, "id"),
    prevent_initial_call=True
)
def sincronizar_candidato_individual(n_clicks, button_id):
    """Sincronizar conversaciones de un candidato específico."""
    if not n_clicks:
        raise PreventUpdate
    
    candidato_id = button_id["index"]
    
    try:
        # Llamar endpoint de sincronización
        response = requests.post(
            f"{BACKEND_URL}/api/candidatos/{candidato_id}/sincronizar",
            params={"limit": 10},
            timeout=5
        )
        
        if response.ok:
            data = response.json()
            sincronizaciones = data.get("sincronizaciones", [])
            
            if sincronizaciones:
                return dbc.Alert(
                    [
                        html.I(className="fas fa-check-circle me-2"),
                        "Sincronización iniciada: " + ", ".join(sincronizaciones)
                    ],
                    color="success",
                    dismissable=True,
                    duration=4000
                )
            else:
                return dbc.Alert(
                    "No hay cuentas configuradas para sincronizar",
                    color="warning",
                    dismissable=True,
                    duration=4000
                )
        else:
            error_detail = response.json().get("detail", "Error desconocido")
            return dbc.Alert(
                f"Error: {error_detail}",
                color="danger",
                dismissable=True,
                duration=4000
            )
            
    except Exception as e:
        print(f"Error al sincronizar candidato {candidato_id}: {e}")
        return dbc.Alert(
            f"Error de conexión: {str(e)}",
            color="danger",
            dismissable=True,
            duration=4000
        )


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
     State("store-facebook-pages", "data")],
    prevent_initial_call=True
)
def conectar_paginas_seleccionadas(n_clicks, selected_page_ids, pages_data):
    """Conectar las páginas seleccionadas."""
    if not n_clicks or not selected_page_ids or not pages_data:
        raise PreventUpdate
    
    try:
        # Filtrar solo las páginas seleccionadas
        selected_pages = [page for page in pages_data if page.get('page_id') in selected_page_ids]
        
        if not selected_pages:
            return dbc.Alert("No hay páginas seleccionadas", color="warning", dismissable=True)
        
        # Enviar al backend
        response = requests.post(
            f"{BACKEND_URL}/api/candidatos/conectar-paginas",
            json={"pages": selected_pages},
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
    Input("btn-sync-confirm", "n_clicks"),
    Input("interval-sync-poll", "n_intervals"),
    State("input-sync-password", "value"),
    prevent_initial_call=True,
)
def handle_sync(confirm_click, n_intervals, password):
    """Maneja inicio de sync y polling de estado en un solo callback.

    - Si se activa por `btn-sync-confirm`: valida contraseña y lanza `control.request_sync()`.
    - Si se activa por `interval-sync-poll`: consulta `control.get_status()` y actualiza el store.
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger = ctx.triggered[0]["prop_id"]

    # Si el trigger fue el botón de confirmar: iniciar sync
    if "btn-sync-confirm" in trigger:
        res = control.request_sync(password or "")
        if not res.get("ok"):
            # No iniciar polling, mostrar error
            logs = "\n".join(control.get_logs(200))
            return logs, dbc.Alert(res.get("msg", "Error"), color="danger"), dash.no_update, True

        # Sync iniciado: devolver mensaje y habilitar polling
        status = control.get_status()
        logs = "\n".join(control.get_logs(200))
        return logs, dbc.Alert("Sincronización iniciada...", color="info"), status, False

    # Si el trigger es el interval: devolver estado y decidir si seguir polling
    if "interval-sync-poll" in trigger:
        status = control.get_status()
        state = status.get("state")
        logs = "\n".join(control.get_logs(500))
        if state in ("finished", "error", "idle", "stopped"):
            # Mostrar mensaje final según estado y detener polling
            if state == "finished":
                modal_msg = dbc.Alert("Sincronización completada", color="success")
            elif state == "error":
                modal_msg = dbc.Alert(f"Error: {status.get('message','')}", color="danger")
            else:
                modal_msg = dbc.Alert(status.get('message', 'Sincronización finalizada'), color="info")
            return logs, modal_msg, status, True
        # Seguir polling
        return logs, dash.no_update, status, False

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


if __name__ == "__main__":
    app.run(
        host=config.FRONTEND_HOST,
        port=config.FRONTEND_PORT,
        debug=config.DEBUG
    )
