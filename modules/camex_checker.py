# -*- coding: utf-8 -*-
"""
Módulo de consulta CAMEX/Gecex e TTD409 — com auditoria completa
Similar à funcionalidade do NF-e Editor original.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

try:
    from modules.database import (
        buscar_camex_por_ncm, get_camex_stats,
        buscar_ttd409_por_ncm, get_ttd409_stats,
    )
except ImportError:
    def buscar_camex_por_ncm(ncm, extipi=""): return []
    def get_camex_stats(): return {"ncm_vigentes": 0, "registros_vigentes": 0, "fontes": 0, "ultima_atualizacao": "N/A"}
    def buscar_ttd409_por_ncm(ncm): return []
    def get_ttd409_stats(): return {"itens_legais": 0, "total_registros": 0, "ultima_atualizacao": "N/A"}


def _render_ttd409_alertas(alertas: List[Dict], titulo: str = "Itens com risco de bloqueio TTD409") -> None:
    """Renderiza alerta TTD409 igual ao do NF-e Editor original."""
    if not alertas:
        return
    st.markdown(f"""<div style="background:#fff1f2;border-left:5px solid #dc2626;
border-radius:6px;padding:0.9rem 1.1rem;margin:1rem 0;color:#7f1d1d;">
<strong>🚨 ALERTA GRAVE TTD409:</strong> {len(alertas)} item(ns) batem com mercadorias
do <strong>Anexo Único do Decreto SC 2.128/2009</strong>.
Esses itens <strong>não devem entrar no TTD409</strong> sem revisão fiscal.
</div>""", unsafe_allow_html=True)
    with st.expander(titulo, expanded=True):
        st.dataframe(pd.DataFrame(alertas), use_container_width=True, hide_index=True)


def _render_camex_alertas(alertas: List[Dict], titulo: str = "Itens encontrados na base CAMEX/Gecex") -> None:
    """Renderiza alerta CAMEX igual ao do NF-e Editor original."""
    if not alertas:
        return
    st.markdown(f"""<div style="background:#eef6ff;border-left:4px solid #2563eb;
border-radius:6px;padding:0.8rem 1.1rem;margin:1rem 0;">
<strong>⚠️ {len(alertas)} item(ns)</strong> possuem NCM em lista CAMEX/Gecex vigente.
Confira a lista, EX e vigência antes de concluir a importação.
</div>""", unsafe_allow_html=True)
    with st.expander(titulo, expanded=True):
        st.dataframe(pd.DataFrame(alertas), use_container_width=True, hide_index=True)


def _resumir_camex_matches(matches: List[Dict], limite: int = 6) -> str:
    if not matches:
        return "Nenhum"
    partes = []
    for m in matches[:limite]:
        ex = f" Ex {m.get('ex')}" if m.get("ex") else ""
        vig = ""
        if m.get("inicio_vigencia") or m.get("fim_vigencia"):
            vig = f" ({m.get('inicio_vigencia') or '?'} a {m.get('fim_vigencia') or '?'})"
        ato = f" - {m.get('ato_legal')}" if m.get("ato_legal") else ""
        partes.append(f"{m.get('lista', '')}{ex}{vig}{ato}")
    if len(matches) > limite:
        partes.append(f"+{len(matches) - limite} lista(s)")
    return " | ".join(partes)


def _auditar_ncm(ncm: str, extipi: str = "", origem: str = "consulta manual") -> Dict:
    """Audita um NCM contra as bases CAMEX e TTD409."""
    resultado = {"ncm": ncm, "origem": origem}
    # TTD409
    ttd = buscar_ttd409_por_ncm(ncm)
    if ttd:
        resultado["ttd409_alerta"] = {
            "Gravidade": "GRAVE",
            "NCM": ncm,
            "Regra TTD409": " | ".join(
                f"Item {m.get('item')} - {m.get('descricao_legal', '')[:80]}" for m in ttd
            ),
            "Acao recomendada": "Não incluir no TTD409 sem revisar descrição legal, NCM e exceções aplicáveis.",
            "detalhes": ttd,
        }
    else:
        resultado["ttd409_alerta"] = None
    # CAMEX
    cam = buscar_camex_por_ncm(ncm, extipi)
    if cam:
        resultado["camex_alerta"] = {
            "NCM": ncm,
            "EXTIPI": extipi,
            "Qtd. listas": len(cam),
            "Listas CAMEX": _resumir_camex_matches(cam),
            "detalhes": cam,
        }
    else:
        resultado["camex_alerta"] = None
    return resultado


def render_camex_tab() -> None:
    st.title("Auditoria CAMEX / Gecex e TTD409")
    st.caption(
        "Verifique se os NCMs estão nas listas de exceção. "
        "Itens no TTD409 (Decreto SC 2.128/2009) "
        "<strong>não devem ser incluídos no benefício fiscal sem revisão</strong>.",
        unsafe_allow_html=True,
    )

    # ── Stats ──
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📋 Base CAMEX/Gecex")
        cs = get_camex_stats()
        if cs and cs.get("ncm_vigentes", 0) > 0:
            mc1, mc2 = st.columns(2)
            mc1.metric("NCMs vigentes", cs["ncm_vigentes"])
            mc2.metric("Registros", cs["registros_vigentes"])
            st.caption(f"{cs.get('fontes', 0)} fonte(s) oficiais - {cs.get('ultima_atualizacao', 'N/A')}")
        else:
            st.info("Base CAMEX: aguardando dados...")
    with col2:
        st.markdown("### 🚨 TTD409 — Decreto SC 2.128/2009")
        ts = get_ttd409_stats()
        if ts and ts.get("itens_legais", 0) > 0:
            tc1, tc2 = st.columns(2)
            tc1.metric("Itens legais", ts["itens_legais"])
            tc2.metric("NCMs/prefixos", ts["total_registros"])
            st.caption(f"Atualizado em {ts.get('ultima_atualizacao', 'N/A')}")
        else:
            st.info("Base TTD409: aguardando dados...")

    st.divider()

    # ── Consulta individual ──
    st.subheader("🔍 Consultar NCM")
    with st.container(border=True):
        col_ncm, col_ext = st.columns([3, 1])
        with col_ncm:
            ncm_in = st.text_input("NCM (8 dígitos):", placeholder="Ex: 84713012", key="cx_ncm")
        with col_ext:
            ext_in = st.text_input("EXTIPI (opcional):", placeholder="Ex: 001", key="cx_ext")

        if ncm_in:
            ncm = ncm_in.replace(".", "").replace("-", "").strip()
            ext = ext_in.strip()
            if len(ncm) == 8 and ncm.isdigit():
                with st.spinner("Consultando..."):
                    ttd = buscar_ttd409_por_ncm(ncm)
                    cam = buscar_camex_por_ncm(ncm, ext)

                if ttd:
                    _render_ttd409_alertas([{
                        "Gravidade": "GRAVE",
                        "NCM": ncm,
                        "Descrição Legal": " | ".join(
                            f"Item {m.get('item', '?')}" for m in ttd
                        ),
                        "Base Legal": "Decreto SC 2.128/2009",
                        "Detalhes": " | ".join(
                            f"{m.get('descricao_legal', '')[:120]}" for m in ttd
                        ),
                        "Ação": "Não incluir no TTD409 sem revisão",
                    }], "Alerta TTD409 — NCM consultado")
                else:
                    st.success(f"✅ NCM **{ncm}** liberado — não encontrado na base TTD409")

                if cam:
                    _render_camex_alertas([{
                        "NCM": ncm,
                        "EXTIPI": ext or "-",
                        "Listas": _resumir_camex_matches(cam),
                        "Qtd. listas": len(cam),
                        "Detalhes": " | ".join(
                            f"{m.get('lista', '?')}: {m.get('descricao', '')[:60]}" for m in cam[:5]
                        ),
                    }], "Alertas CAMEX — NCM consultado")
                else:
                    st.success(f"✅ NCM **{ncm}** não encontrado na base CAMEX/Gecex")
            else:
                st.warning("NCM deve ter 8 dígitos numéricos (ex: 84713012)")

    st.divider()

    # ── Auditoria em lote (upload de arquivo) ──
    st.subheader("📂 Auditoria em lote")
    st.markdown("Faça upload de um arquivo CSV/Excel com os NCMs para auditar todos contra CAMEX e TTD409.")
    lote = st.file_uploader("Arquivo com coluna NCM", type=["csv", "xlsx", "xls"], key="cx_lote")
    if lote is not None:
        try:
            df = pd.read_csv(lote, dtype=str) if lote.name.endswith(".csv") else pd.read_excel(lote, dtype=str)
            col_ncm = next((c for c in df.columns if "ncm" in str(c).lower()), None)
            if col_ncm is None:
                st.error("Nenhuma coluna com 'NCM' encontrada. Colunas disponíveis: " + ", ".join(df.columns))
                st.dataframe(df.head(5))
            else:
                # Auditar cada NCM
                ttd409_alertas = []
                camex_alertas = []
                total_itens = 0
                with st.spinner(f"Auditando {len(df)} linha(s)..."):
                    for _, row in df.iterrows():
                        n = str(row[col_ncm]).replace(".", "").replace("-", "").strip()
                        ext = str(row.get("EXTIPI", row.get("extipi", ""))).strip() if "EXTIPI" in df.columns or "extipi" in df.columns else ""
                        if len(n) == 8 and n.isdigit():
                            total_itens += 1
                            ttd = buscar_ttd409_por_ncm(n)
                            cam = buscar_camex_por_ncm(n, ext)
                            if ttd:
                                for m in ttd:
                                    ttd409_alertas.append({
                                        "Gravidade": "GRAVE",
                                        "NCM": n,
                                        "Item Decreto": m.get("item", "?"),
                                        "Descrição Legal": m.get("descricao_legal", "")[:120],
                                        "Base Legal": "Decreto SC 2.128/2009",
                                        "Ação": "Não incluir no TTD409 sem revisão fiscal",
                                        "Observação": m.get("observacao", "")[:100] or "-",
                                    })
                            if cam:
                                for m in cam:
                                    camex_alertas.append({
                                        "NCM": n,
                                        "Lista": m.get("lista", "?"),
                                        "EX": m.get("ex", "-"),
                                        "Vigência": f"{m.get('inicio_vigencia','?')} a {m.get('fim_vigencia','?')}",
                                        "Descrição": m.get("descricao", "")[:100],
                                        "Ato Legal": m.get("ato_legal", "-"),
                                    })

                st.info(f"**{total_itens}** NCM(s) analisados · "
                        f"**{len(camex_alertas)}** alerta(s) CAMEX · "
                        f"**{len(ttd409_alertas)}** bloqueio(s) TTD409")

                _render_ttd409_alertas(ttd409_alertas, f"🚨 {len(ttd409_alertas)} bloqueio(s) TTD409")
                _render_camex_alertas(camex_alertas, f"⚠️ {len(camex_alertas)} ocorrência(s) CAMEX")

                # Download do relatório
                if ttd409_alertas or camex_alertas:
                    rel = pd.DataFrame(ttd409_alertas + camex_alertas)
                    csv = rel.to_csv(index=False).encode("utf-8")
                    st.download_button("📥 Baixar relatório completo (CSV)", data=csv,
                                       file_name="auditoria_camex_ttd409.csv", mime="text/csv",
                                       use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")

    st.divider()

    # ── Informação legal ──
    with st.expander("📖 Base Legal — TTD409"):
        st.markdown("""
**Decreto SC 2.128/2009** — Anexo Único

Lista de mercadorias que **não podem se beneficiar** do tratamento tributário TTD409
(diferimento do ICMS nas importações do Sul).

- Itens com NCM correspondente devem ser **excluídos do benefício**
- Cada item possui descrição legal específica que define o enquadramento
- A consulta considera NCM exato e prefixos de 4 dígitos

**CAMEX/Gecex**
- Listas de exceção à Tarifa Externa Comum (TEC)
- Inclui cotas, ex-tarifários, bens de capital e informática
- Vigência limitada — confira sempre as datas
        """)