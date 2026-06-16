# -*- coding: utf-8 -*-
"""
Módulo de consulta CAMEX/Gecex e TTD409 — consulta individual e em lote.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

try:
    from modules.database import (
        get_db_stats, buscar_camex_por_ncm, get_camex_stats,
        buscar_ttd409_por_ncm, get_ttd409_stats,
    )
except ImportError:
    def get_db_stats(): return {"camex": 0, "ttd409": 0}
    def buscar_camex_por_ncm(ncm): return []
    def get_camex_stats(): return {"ncm_vigentes": 0, "registros_vigentes": 0, "fontes": 0, "ultima_atualizacao": "N/A"}
    def buscar_ttd409_por_ncm(ncm): return []
    def get_ttd409_stats(): return {"itens_legais": 0, "total_registros": 0, "ultima_atualizacao": "N/A"}

def _resumir_camex_matches(matches: List[Dict], limite: int = 6) -> str:
    if not matches:
        return "Nenhum"
    linhas = []
    for m in matches[:limite]:
        fonte = m.get("fonte", m.get("source", "?"))
        ncm = m.get("ncm", "?")
        desc = m.get("descricao", m.get("description", ""))
        linhas.append(f"- NCM {ncm} ({fonte}): {desc[:80]}")
    if len(matches) > limite:
        linhas.append(f"... e mais {len(matches) - limite} registro(s)")
    return "\n".join(linhas)

def render_camex_tab() -> None:
    st.title("Consulta CAMEX / Gecex e TTD409")
    st.caption("Verifique se um NCM está nas listas de exceção antes de gerar ICMS ou NF.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Base CAMEX/Gecex")
        cs = get_camex_stats()
        if cs:
            mc1, mc2 = st.columns(2)
            mc1.metric("NCMs vigentes", cs.get("ncm_vigentes", 0))
            mc2.metric("Registros", cs.get("registros_vigentes", 0))
            st.caption(f"{cs.get('fontes', 0)} fonte(s) oficiais - atualizado em {cs.get('ultima_atualizacao', 'sem data')}")
        else:
            st.warning("Base CAMEX não encontrada.")
    with col2:
        st.markdown("### TTD409")
        ts = get_ttd409_stats()
        if ts:
            tc1, tc2 = st.columns(2)
            tc1.metric("Itens legais", ts.get("itens_legais", 0))
            tc2.metric("NCMs/prefixos", ts.get("total_registros", 0))
            st.caption(f"Decreto SC 2.128/2009 - atualizado em {ts.get('ultima_atualizacao', 'sem data')}")
        else:
            st.warning("Base TTD409 não encontrada.")

    st.divider()

    # Consulta individual
    st.subheader("Consultar NCM")
    ncm_input = st.text_input("Digite o NCM (8 dígitos):", placeholder="Ex: 84713012", key="cx_ncm")
    if ncm_input:
        ncm = ncm_input.replace(".", "").replace("-", "").strip()
        if len(ncm) == 8 and ncm.isdigit():
            with st.spinner("Consultando..."):
                cr = buscar_camex_por_ncm(ncm)
                tr = buscar_ttd409_por_ncm(ncm)
            ca, cb = st.columns(2)
            with ca:
                st.markdown("**CAMEX/Gecex**")
                if cr:
                    st.warning(f"NCM encontrado na lista CAMEX ({len(cr)} registro(s))")
                    for r in cr[:10]:
                        st.markdown(f"- {r.get('fonte', '?')}: {r.get('descricao', '')[:100]}")
                else:
                    st.success("NCM não encontrado na base CAMEX")
            with cb:
                st.markdown("**TTD409**")
                if tr:
                    st.error(f"NCM encontrado na lista TTD409 ({len(tr)} registro(s))")
                    for r in tr[:10]:
                        st.markdown(f"- {r.get('ncm_prefixo', r.get('ncm', '?'))}: {r.get('descricao', '')[:100]}")
                else:
                    st.success("NCM não encontrado na base TTD409")
        else:
            st.warning("Digite um NCM válido de 8 dígitos (ex: 84713012)")

    st.divider()

    # Consulta em lote
    st.subheader("Consultar lote de NCMs")
    lote = st.file_uploader("Upload de arquivo com coluna NCM", type=["csv", "xlsx", "xls"], key="cx_lote")
    if lote is not None:
        try:
            df = pd.read_csv(lote, dtype=str) if lote.name.endswith(".csv") else pd.read_excel(lote, dtype=str)
            col_ncm = next((c for c in df.columns if "ncm" in str(c).lower()), None)
            if col_ncm is None:
                st.error("Nenhuma coluna com 'NCM' encontrada.")
                return st.dataframe(df.head(5))
            resultados = []
            for _, row in df.iterrows():
                n = str(row[col_ncm]).replace(".", "").replace("-", "").strip()
                if len(n) == 8 and n.isdigit():
                    c = buscar_camex_por_ncm(n)
                    t = buscar_ttd409_por_ncm(n)
                    resultados.append({
                        "NCM": n,
                        "CAMEX": "Sim" if c else "Não",
                        "TTD409": "Sim" if t else "Não",
                        "Detalhes CAMEX": _resumir_camex_matches(c),
                        "Detalhes TTD409": ", ".join([r.get("descricao", "")[:60] for r in t[:3]]) if t else "-",
                    })
            st.dataframe(pd.DataFrame(resultados), use_container_width=True)
            csv = pd.DataFrame(resultados).to_csv(index=False).encode("utf-8")
            st.download_button("Baixar CSV", data=csv, file_name="consulta_camex_lote.csv", mime="text/csv")
        except Exception as e:
            st.error(f"Erro: {e}")