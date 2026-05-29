#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src/plots.py — Funções Plotly reutilizáveis para o Dashboard Previsão de Pesca v3.1
Conversão da lógica visual do PDF v2.10 (matplotlib) para gráficos interativos Plotly.
Compatível com Streamlit Cloud e Windows Session 0 (sem dependências GUI).
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ==============================================================================
# UTILITÁRIOS
# ==============================================================================
def get_cardinal(deg):
    """Converte graus em ponto cardeal (16 direções)."""
    if pd.isna(deg):
        return None
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", 
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int(round((deg + 11.25) / 22.5)) % 16]

def clean_text_for_plot(text):
    """Sanitiza texto para exibição em gráficos (remove emojis problemáticos)."""
    replacements = {
        '⭐': '*', '✅': '[OK]', '⚠️': '[!]', '❌': '[NAO]',
        '🌑': 'Lua Nova', '🌕': 'Lua Cheia', '🌧️': 'Chuva',
        '💨': 'Vento', '❄️': 'Frio', '🌊': 'Hidro'
    }
    for em, repl in replacements.items():
        text = text.replace(em, repl)
    return text.strip()

# ==============================================================================
# GRÁFICOS METEOROLÓGICOS
# ==============================================================================
def plot_wind_rose_plotly(df_weather, title="Rosa dos Ventos", height=400):
    """
    Rosa dos ventos interativa com Plotly.
    df_weather: DataFrame com coluna 'Dir_Graus' (0-360) e opcional 'Vento_kmh'.
    """
    df = df_weather.copy()
    df['Dir_Graus'] = pd.to_numeric(df['Dir_Graus'], errors='coerce').fillna(0)
    df.loc[df['Dir_Graus'] == 360, 'Dir_Graus'] = 0
    
    # Bin em 16 setores
    bins = np.arange(0, 361, 22.5)
    labels = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", 
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    df['Dir_Sector'] = pd.cut(df['Dir_Graus'], bins=bins, labels=labels, 
                               include_lowest=True, right=False)
    
    # Contagens + intensidade média de vento por setor
    stats = df.groupby('Dir_Sector', observed=False).agg(
        count=('Dir_Sector', 'size'),
        avg_wind=('Vento_kmh', 'mean') if 'Vento_kmh' in df.columns else ('Dir_Sector', 'size')
    ).reset_index().fillna(0)
    
    # Ordenar setores no sentido horário a partir do Norte
    sector_order = {d: i for i, d in enumerate(labels)}
    stats['order'] = stats['Dir_Sector'].map(sector_order)
    stats = stats.sort_values('order')
    
    # Coordenadas polares
    angles = np.linspace(0, 2*np.pi, 16, endpoint=False)
    
    fig = go.Figure(go.Barpolar(
        r=stats['count'],
        theta=labels,
        name='Frequência',
        marker_color=stats['avg_wind'] if 'avg_wind' in stats.columns else stats['count'],
        marker_colorscale='Blues',
        marker_line_color='white',
        marker_line_width=1,
        opacity=0.85,
        hovertemplate='<b>%{theta}</b><br>Frequência: %{r}<br>Vento médio: %{marker.color:.1f} km/h<extra></extra>'
    ))
    
    # Seta indicando direção dominante
    if not stats.empty and stats['count'].max() > 0:
        dom_idx = stats['count'].idxmax()
        dom_label = stats.loc[dom_idx, 'Dir_Sector']
        dom_angle = labels.index(dom_label) * 22.5
        fig.add_annotation(
            x=0, y=stats['count'].max() * 1.3,
            text=f"Dom: {dom_label}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.5,
            arrowwidth=2,
            arrowcolor='#C21E1E',
            font=dict(color='#C21E1E', size=10, weight='bold'),
            ax=0, ay=-30
        )
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, weight='bold')),
        polar=dict(
            radialaxis=dict(visible=False),
            angularaxis=dict(direction='clockwise', period=16)
        ),
        height=height,
        margin=dict(t=40, b=10, l=10, r=10)
    )
    return fig


def plot_temp_pressao_plotly(df_hourly, df_daily, tw=None, height=350):
    """
    Gráfico combinado: evolução térmica + pressão atmosférica + linha Tw.
    df_hourly: dados horários (Temp_C, Pressao_hPa)
    df_daily: dados diários (Min_C, Max_C)
    tw: temperatura da água estimada (linha de referência)
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Temperatura diária (área entre min/max)
    fig.add_trace(go.Scatter(
        x=df_daily['Data'], y=df_daily['Max_C'],
        mode='lines', name='Máx', line=dict(color='#E07B39', width=2)
    ), secondary_y=False)
    
    fig.add_trace(go.Scatter(
        x=df_daily['Data'], y=df_daily['Min_C'],
        mode='lines', name='Mín', line=dict(color='#2E86AB', width=2),
        fill='tonexty', fillcolor='rgba(46,134,171,0.1)'
    ), secondary_y=False)
    
    # Linha Tw (se fornecida)
    if tw is not None:
        fig.add_hline(y=tw, line_dash="dot", line_color="purple", 
                      annotation_text=f"Tw={tw}°C", annotation_position="top right")
    
    # Pressão (eixo secundário)
    if 'Pressao_hPa' in df_hourly.columns:
        # Downsample para não sobrecarregar
        df_p = df_hourly.iloc[::6].copy()
        fig.add_trace(go.Scatter(
            x=df_p['Data'], y=df_p['Pressao_hPa'],
            mode='lines', name='Pressão (hPa)',
            line=dict(color='darkgreen', dash='dash', width=1.5),
            opacity=0.7
        ), secondary_y=True)
        
        # Indicador de tendência
        delta = df_hourly['Pressao_hPa'].iloc[-1] - df_hourly['Pressao_hPa'].iloc[0]
        trend = "⬇️ A descer" if delta < -1.5 else ("⬆️ A subir" if delta > 1.5 else "➡️ Estável")
        fig.add_annotation(
            x=df_p['Data'].iloc[-1], y=df_p['Pressao_hPa'].iloc[-1],
            text=f"{trend} (Δ{delta:+.1f})",
            showarrow=False,
            bgcolor='white', bordercolor='darkgreen', borderwidth=1,
            font=dict(size=9, color='darkgreen')
        )
    
    fig.update_layout(
        title="Evolução Térmica e Pressão Atmosférica",
        xaxis_title="Data",
        yaxis_title="Temperatura (°C)",
        yaxis2_title="Pressão (hPa)",
        hovermode='x unified',
        height=height,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    fig.update_xaxes(title_text="Data")
    return fig


def plot_chuva_vento_plotly(df_daily, limiar_chuva=15, limiar_vento=35, height=300):
    """
    Gráfico combinado: precipitação (barras) + vento (linha) com limiares de alerta.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Chuva (barras)
    fig.add_trace(go.Bar(
        x=df_daily['Data'], y=df_daily['Chuva_mm'],
        name='Chuva (mm)', marker_color='steelblue', opacity=0.7,
        hovertemplate='%{x}<br>Chuva: %{y:.1f} mm<extra></extra>'
    ), secondary_y=False)
    
    # Vento (linha)
    fig.add_trace(go.Scatter(
        x=df_daily['Data'], y=df_daily['Vento_kmh'],
        mode='lines+markers', name='Vento (km/h)',
        line=dict(color='firebrick', width=2),
        marker=dict(size=6),
        hovertemplate='%{x}<br>Vento: %{y:.1f} km/h<extra></extra>'
    ), secondary_y=True)
    
    # Linhas de limiar
    fig.add_hline(y=limiar_chuva, line_dash="dash", line_color="blue", 
                  annotation_text=f"Limiar Chuva ({limiar_chuva}mm)", 
                  annotation_position="top left", secondary_y=False)
    fig.add_hline(y=limiar_vento, line_dash="dash", line_color="red",
                  annotation_text=f"Limiar Vento ({limiar_vento}km/h)",
                  annotation_position="top right", secondary_y=True)
    
    # Alertas visuais
    alertas = []
    if (df_daily['Chuva_mm'] > limiar_chuva).any():
        alertas.append("⚠️ Chuva acima do limiar")
    if (df_daily['Vento_kmh'] > limiar_vento).any():
        alertas.append("💨 Vento forte previsto")
    if alertas:
        fig.add_annotation(
            x=0.02, y=0.98, text=" | ".join(alertas),
            showarrow=False, bgcolor='#FFF3CD', bordercolor='#E6A817',
            font=dict(size=9, color='#856404'), xref='paper', yref='paper',
            xanchor='left', yanchor='top'
        )
    
    fig.update_layout(
        title="Precipitação e Vento Diário",
        xaxis_title="Data",
        yaxis_title="Chuva (mm)",
        yaxis2_title="Vento (km/h)",
        hovermode='x unified',
        height=height,
        barmode='overlay'
    )
    return fig

# ==============================================================================
# GRÁFICOS DE CAPTURAS
# ==============================================================================
def plot_capturas_species_plotly(df_capturas, metrica='Kg', height=350):
    """
    Gráfico de barras horizontais: total capturado por espécie.
    metrica: 'Kg' ou 'Qtd'
    """
    if df_capturas.empty:
        return go.Figure().add_annotation(text="Sem dados de capturas", showarrow=False)
    
    # Filtrar colunas da métrica escolhida (excluir Total)
    suffix = f'_{metrica}'
    cols = [c for c in df_capturas.columns if c.endswith(suffix) and c != f'Total{suffix}']
    
    if not cols:
        return go.Figure().add_annotation(text=f"Sem dados de {metrica}", showarrow=False)
    
    # Somar por espécie
    totais = {c.replace(suffix, ''): df_capturas[c].sum() for c in cols}
    totais = {k: v for k, v in totais.items() if v > 0}
    
    if not totais:
        return go.Figure().add_annotation(text="Nenhuma captura registada", showarrow=False)
    
    df_p = pd.Series(totais).sort_values()
    unit = 'kg' if metrica == 'Kg' else 'un'
    
    fig = px.bar(
        x=df_p.values, y=df_p.index, orientation='h',
        color=df_p.values, color_continuous_scale='Set2',
        labels={'x': f'Total ({unit})', 'y': 'Espécie', 'color': f'Total ({unit})'},
        text_auto='.1f' if metrica == 'Kg' else '.0f'
    )
    
    fig.update_layout(
        title=f"Capturas por Espécie ({metrica}) | Total: {df_p.sum():.1f} {unit}",
        height=height,
        margin=dict(l=100, r=20, t=50, b=20),
        coloraxis_showscale=False,
        yaxis=dict(autorange='reversed')  # Maior valor no topo
    )
    return fig


def plot_evolution_qtd_moon_plotly(df_capturas, height=400):
    """
    Evolução temporal de capturas (quantidade) codificada por fase lunar.
    Requer coluna 'Fase_Lua_Captura' ou similar.
    """
    if df_capturas.empty or 'Total_Qtd' not in df_capturas.columns:
        return go.Figure().add_annotation(text="Sem dados de quantidade", showarrow=False)
    
    # Agrupar por data
    df_agg = df_capturas.groupby(df_capturas['Timestamp'].dt.date).agg({
        'Total_Qtd': 'sum',
        'Fase_Lua_Captura': 'first' if 'Fase_Lua_Captura' in df_capturas.columns else lambda x: None
    }).reset_index()
    
    if df_agg.empty:
        return go.Figure().add_annotation(text="Dados insuficientes", showarrow=False)
    
    # Mapear cores por fase lunar
    def get_lunar_color(phase):
        phase = str(phase).lower() if pd.notna(phase) else ""
        if 'nova' in phase: return '#1E90FF'   # DodgerBlue
        if 'cheia' in phase: return '#FFD700'  # Gold
        if 'cresc' in phase: return '#90EE90'  # LightGreen
        if 'ming' in phase: return '#FFB6C1'   # LightPink
        return '#D3D3D3'  # LightGray
    
    df_agg['color'] = df_agg['Fase_Lua_Captura'].apply(get_lunar_color)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_agg['Timestamp'],
        y=df_agg['Total_Qtd'],
        marker_color=df_agg['color'],
        marker_line_color='gray',
        marker_line_width=0.5,
        name='Capturas',
        hovertemplate='%{x}<br>Peixes: %{y}<br>Fase: %{customdata}<extra></extra>',
        customdata=df_agg['Fase_Lua_Captura']
    ))
    
    # Legenda manual para fases lunares
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', 
                             marker=dict(size=10, color='#1E90FF'), name='Lua Nova'))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers',
                             marker=dict(size=10, color='#FFD700'), name='Lua Cheia'))
    
    fig.update_layout(
        title="Evolução de Capturas (Nº Peixes) vs Fases Lunares",
        xaxis_title="Data",
        yaxis_title="Quantidade (unidades)",
        hovermode='x unified',
        height=height,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    fig.update_xaxes(tickformat="%d/%m")
    return fig


def plot_capturas_mensais_plotly(df_capturas, height=450):
    """
    Gráfico de barras agrupadas: capturas mensais por espécie (Qtd / Kg).
    Formato: barra = quantidade, label = "Qtd / X.Xkg"
    """
    if df_capturas.empty:
        return go.Figure().add_annotation(text="Sem dados de capturas", showarrow=False)
    
    # Filtrar espécies com capturas
    species_qtd = [c for c in df_capturas.columns if c.endswith('_Qtd') and c != 'Total_Qtd']
    species_qtd = [c for c in species_qtd if df_capturas[c].sum() > 0]
    
    if not species_qtd:
        return go.Figure().add_annotation(text="Nenhuma captura registada", showarrow=False)
    
    df_c = df_capturas.copy()
    df_c['Mes'] = df_c['Timestamp'].dt.to_period('M').astype(str)
    
    # Agregação mensal
    mensal = df_c.groupby('Mes').agg({c: 'sum' for c in species_qtd}).reset_index()
    
    # Transformar para formato longo
    df_long = mensal.melt(id_vars='Mes', value_vars=species_qtd, 
                          var_name='Especie_Qtd', value_name='Quantidade')
    df_long['Especie'] = df_long['Especie_Qtd'].str.replace('_Qtd', '')
    
    # Adicionar peso correspondente
    for i, row in df_long.iterrows():
        col_kg = row['Especie_Qtd'].replace('_Qtd', '_Kg')
        if col_kg in df_c.columns:
            peso = df_c.groupby('Mes')[col_kg].sum().get(row['Mes'], 0)
            df_long.at[i, 'Peso_Kg'] = peso
        else:
            df_long.at[i, 'Peso_Kg'] = 0
    
    fig = px.bar(
        df_long, x='Mes', y='Quantidade', color='Especie',
        barmode='group',
        text=df_long.apply(lambda r: f"{int(r['Quantidade'])}/{r['Peso_Kg']:.1f}kg", axis=1),
        color_discrete_sequence=px.colors.qualitative.Set2,
        labels={'Quantidade': 'Peixes (un)', 'Mes': 'Mês', 'Especie': 'Espécie'}
    )
    
    fig.update_traces(textposition='outside', textfont_size=9)
    fig.update_layout(
        title="Capturas Mensais por Espécie (Qtd / Kg)",
        height=height,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        xaxis_title="Mês",
        yaxis_title="Quantidade de Peixes"
    )
    return fig

# ==============================================================================
# GRÁFICOS DE MACHINE LEARNING
# ==============================================================================
def plot_feature_importance_plotly(model, feature_names, top_n=10, height=400):
    """
    Gráfico de importância de features para modelo scikit-learn (RandomForest, etc.).
    model: objeto com atributo .feature_importances_
    feature_names: lista de nomes das features na ordem correta
    top_n: número de features a exibir (ordenadas por importância)
    """
    if not hasattr(model, 'feature_importances_'):
        return go.Figure().add_annotation(
            text="Modelo não suporta feature_importances_", showarrow=False)
    
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:top_n]
    
    df_imp = pd.DataFrame({
        'Feature': [feature_names[i] for i in indices],
        'Importance': importances[indices]
    }).sort_values('Importance')
    
    fig = px.bar(
        df_imp, x='Importance', y='Feature', orientation='h',
        color='Importance', color_continuous_scale='Viridis',
        labels={'Importance': 'Importância', 'Feature': 'Variável'},
        text_auto='.3f'
    )
    
    fig.update_layout(
        title=f"Importância das Variáveis (Top {top_n})",
        height=height,
        margin=dict(l=120, r=20, t=40, b=20),
        coloraxis_showscale=False,
        yaxis=dict(autorange='reversed')
    )
    return fig


def plot_model_performance_plotly(y_true, y_pred, r2, rmse, height=350):
    """
    Gráfico de dispersão: valores reais vs previstos + métricas.
    """
    fig = go.Figure()
    
    # Linha de referência (y=x)
    min_val = min(y_true.min(), y_pred.min())
    max_val = max(y_true.max(), y_pred.max())
    fig.add_trace(go.Scatter(
        x=[min_val, max_val], y=[min_val, max_val],
        mode='lines', name='Ideal (y=x)',
        line=dict(color='gray', dash='dash'),
        showlegend=True
    ))
    
    # Pontos reais vs previstos
    fig.add_trace(go.Scatter(
        x=y_true, y=y_pred,
        mode='markers', name='Previsões',
        marker=dict(size=8, color='steelblue', opacity=0.7),
        hovertemplate='Real: %{x}<br>Previsto: %{y}<extra></extra>'
    ))
    
    # Métricas em annotation
    fig.add_annotation(
        x=0.98, y=0.02,
        text=f"R² = {r2:.3f}<br>RMSE = {rmse:.2f}",
        showarrow=False,
        bgcolor='white', bordercolor='navy', borderwidth=1,
        font=dict(size=10, color='navy', family='monospace'),
        xref='paper', yref='paper', xanchor='right', yanchor='bottom'
    )
    
    fig.update_layout(
        title="Desempenho do Modelo: Valores Reais vs Previstos",
        xaxis_title="Score Real",
        yaxis_title="Score Previsto",
        height=height,
        hovermode='closest'
    )
    return fig


def plot_score_distribution_plotly(scores, title="Distribuição de Scores", height=300):
    """
    Histograma + boxplot da distribuição de scores de pesca.
    """
    fig = make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    # Histograma
    fig.add_trace(go.Histogram(
        x=scores, nbinsx=20, name='Distribuição',
        marker_color='lightseagreen', opacity=0.8,
        hovertemplate='Score: %{x}<br>Frequência: %{y}<extra></extra>'
    ), row=1, col=1)
    
    # Boxplot
    fig.add_trace(go.Box(
        y=scores, name='Boxplot', marker_color='lightseagreen',
        boxpoints='outliers', hoverinfo='skip'
    ), row=2, col=1)
    
    # Classificação visual por faixa
    fig.add_vrect(x0=0, x1=20, fillcolor="red", opacity=0.1, layer="below",
                  annotation_text="Fraco", annotation_position="top", row=1, col=1)
    fig.add_vrect(x0=20, x1=40, fillcolor="orange", opacity=0.1, layer="below",
                  annotation_text="Moderado", row=1, col=1)
    fig.add_vrect(x0=40, x1=70, fillcolor="yellow", opacity=0.1, layer="below",
                  annotation_text="Bom", row=1, col=1)
    fig.add_vrect(x0=70, x1=100, fillcolor="green", opacity=0.1, layer="below",
                  annotation_text="Excelente", row=1, col=1)
    
    fig.update_layout(
        title=title,
        height=height,
        showlegend=False,
        hovermode='x unified'
    )
    fig.update_yaxes(title_text="Frequência", row=1, col=1)
    fig.update_yaxes(title_text="Score", row=2, col=1)
    fig.update_xaxes(title_text="Score de Pesca (0-100)", row=2, col=1)
    return fig

# ==============================================================================
# KPIs E INDICADORES
# ==============================================================================
def create_kpi_card(title, value, suffix="", delta=None, color="blue"):
    """
    Cria um componente KPI em HTML/CSS para Streamlit.
    delta: tuple (valor, texto) para indicador de variação
    """
    color_map = {
        "blue": "#2E86AB", "green": "#28A745", "orange": "#FD7E14",
        "red": "#DC3545", "purple": "#6F42C1"
    }
    hex_color = color_map.get(color, color)
    
    delta_html = ""
    if delta:
        val, txt = delta
        sign = "+" if val >= 0 else ""
        delta_color = "green" if val >= 0 else "red"
        delta_html = f"""
        <div style="font-size: 0.9em; color: {delta_color}; margin-top: 4px;">
            {sign}{val} {txt}
        </div>"""
    
    return f"""
    <div style="
        background: white; border-left: 4px solid {hex_color};
        padding: 12px 16px; border-radius: 6px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 8px;">
        <div style="font-size: 0.85em; color: #666; text-transform: uppercase;">
            {title}
        </div>
        <div style="font-size: 1.8em; font-weight: bold; color: #1A1A1A;">
            {value}{suffix}
        </div>
        {delta_html}
    </div>"""