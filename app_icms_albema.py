# -*- coding: utf-8 -*-
"""
App unificado: ICMS SUL + NF-e Editor + CAMEX/TTD409 Checker
--------------------------------------------------------------
Arquivo principal para Streamlit Cloud (icms-sul-albema.streamlit.app).

Workflow:
  1. ICMS SUL  → Importar planilha DUIMP/DI → Calcular ICMS TDD 409
  2. NF-e Editor → Importar XML → Processar para Bling → Verificar CAMEX/TTD409
  3. CAMEX Check → Consultar NCM nas bases CAMEX/Gecex e TTD409

Cada aba é independente — uma não bloqueia a outra.
"""

import streamlit as st
import traceback

st.set_page_config(
    page_title="Importhub",
    page_icon="📊",
    layout="wide",
)

# Inicializa banco de dados antes das abas
with st.spinner("Inicializando bases de dados CAMEX e TTD409..."):
    try:
        from modules.database import init_db
        init_db()
    except Exception as e:
        st.error(f"Erro ao inicializar banco de dados: {e}")
        st.exception(e)
        st.stop()

tab_icms, tab_nfe, tab_camex = st.tabs([
    "📊 ICMS SUL — TDD 409",
    "📄 NF-e Editor — Bling",
    "🔍 CAMEX / TTD409 Check",
])

# ──────────────────────────────────────────────
# Aba 1: ICMS SUL
# ──────────────────────────────────────────────
with tab_icms:
    from modules.icms_calc import render_icms_tab
    render_icms_tab()

# ──────────────────────────────────────────────
# Aba 2: NF-e Editor
# ──────────────────────────────────────────────
with tab_nfe:
    from modules.nf_editor_app import render_nfe_tab
    render_nfe_tab()

# ──────────────────────────────────────────────
# Aba 3: CAMEX / TTD409 Checker
# ──────────────────────────────────────────────
with tab_camex:
    from modules.camex_checker import render_camex_tab
    render_camex_tab()