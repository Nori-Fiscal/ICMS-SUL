# -*- coding: utf-8 -*-
"""
Módulo de auditoria CAMEX/Gecex e TTD409
Implementa a MESMA lógica e visual do NF-e Editor original.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

try:
    from modules.database import (
        buscar_camex_por_ncm, get_camex_stats,
        buscar_ttd409_por_ncm, get_ttd409_stats,
    )
    from modules.xml_service import auditar_ttd409_xml, gerar_relatorio_ttd409
    _HAS_XML = True
except ImportError:
    _HAS_XML = False
    def buscar_camex_por_ncm(ncm, extipi=""): return []
    def get_camex_stats(): return {"ncm_vigentes": 0, "registros_vigentes": 0, "fontes": 0, "ultima_atualizacao": "N/A"}
    def buscar_ttd409_por_ncm(ncm): return []
    def get_ttd409_stats(): return {"itens_legais": 0, "total_registros": 0, "ultima_atualizacao": "N/A"}


def _stat_card(num, label):
    return f"""<div style="background:#f8f9fb;border:1px solid #e4e8ef;border-radius:10px;padding:0.9rem 1.1rem;text-align:center;">
<div style="font-size:2rem;font-weight:700;color:#1a3a6e;line-height:1;">{num}</div>
<div style="font-size:0.72rem;color:#6b7280;margin-top:0.2rem;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>
</div>"""


def _render_ttd409_alertas(alertas, titulo="Itens com risco de bloqueio TTD409"):
    """EXATAMENTE igual ao NF-e Editor original."""
    if not alertas:
        return
    st.markdown(f"""<div style="background:#fff1f2;border-left:5px solid #dc2626;border-radius:6px;padding:0.9rem 1.1rem;margin:1rem 0;color:#7f1d1d;">
<strong>ALERTA GRAVE TTD409:</strong> {len(alertas)} item(ns) do(s) XML(s)
batem com mercadorias do Anexo Unico do Decreto SC 2.128/2009.
Esses itens nao devem entrar no TTD409 sem revisao fiscal.
</div>""", unsafe_allow_html=True)
    with st.expander(titulo, expanded=True):
        st.dataframe(pd.DataFrame(alertas), use_container_width=True, hide_index=True)


def _render_camex_alertas(alertas, titulo="Itens encontrados na base CAMEX/Gecex"):
    """EXATAMENTE igual ao NF-e Editor original."""
    if not alertas:
        return
    st.markdown(f"""<div style="background:#eef6ff;border-left:4px solid #2563eb;border-radius:6px;padding:0.8rem 1.1rem;margin:1rem 0;">
<strong>{len(alertas)} item(ns)</strong> do(s) XML(s) possuem NCM em lista CAMEX/Gecex vigente.
Confira a lista, EX e vigencia antes de concluir a importacao.
</div>""", unsafe_allow_html=True)
    with st.expander(titulo, expanded=True):
        st.dataframe(pd.DataFrame(alertas), use_container_width=True, hide_index=True)


def render_camex_tab() -> None:
    st.markdown("### Conferencia de NCMs contra TTD409 e CAMEX")
    st.caption("Audite XMLs de importacao ou consulte NCMs individualmente.")

    # ── Stats no sidebar ──
    with st.sidebar:
        st.markdown("#### CAMEX/Gecex")
        cs = get_camex_stats()
        if cs and cs.get("ncm_vigentes", 0) > 0:
            st.metric("NCMs vigentes", cs["ncm_vigentes"])
            st.metric("Registros", cs["registros_vigentes"])
            st.caption(f"{cs.get('fontes', 0)} fonte(s) - {cs.get('ultima_atualizacao', 'N/A')}")
        else:
            st.info("Base CAMEX: aguardando dados...")

        st.divider()

        st.markdown("#### TTD409")
        ts = get_ttd409_stats()
        if ts and ts.get("itens_legais", 0) > 0:
            st.metric("Itens legais", ts["itens_legais"])
            st.metric("NCMs/prefixos", ts["total_registros"])
            st.caption(f"Decreto SC 2.128/2009 - {ts.get('ultima_atualizacao', 'N/A')}")
        else:
            st.info("Base TTD409: aguardando dados...")

    # =====================================================================
    # ABA 1: Auditoria por XML (igual ao NF-e Editor)
    # =====================================================================
    with st.container(border=True):
        st.markdown("#### 📄 Auditar XMLs")
        st.caption("Carregue XMLs NF-e para conferir TTD409 e CAMEX item a item.")

        uploaded_xmls = st.file_uploader(
            "XMLs NF-e (um ou mais)",
            type=["xml"],
            accept_multiple_files=True,
            key="cx_xmls",
        )

        if uploaded_xmls:
            st.info(f"{len(uploaded_xmls)} XML(s) carregado(s). Clique em **Conferir** para auditar.")

        if st.button("🔍 Conferir TTD409", type="primary", disabled=not uploaded_xmls, key="cx_conferir"):
            xmls = [(f.name, f.getvalue()) for f in uploaded_xmls]
            auditorias = []
            with st.spinner("Conferindo NCMs na base TTD409..."):
                for nome, data in xmls:
                    itens, stats = auditar_ttd409_xml(data, nome, buscar_ttd409_por_ncm)
                    auditorias.append({"nome_original": nome, "itens": itens, "stats": stats})

            # Processa resultados
            todos_itens = []
            erros = []
            for aud in auditorias:
                todos_itens.extend(aud.get("itens", []))
                sts = aud.get("stats", {})
                for e in sts.get("erros", []):
                    erros.append({"Arquivo XML": sts.get("arquivo", aud.get("nome_original", "")), "Erro": e})

            bloqueios = [r for r in todos_itens if r.get("Gravidade") == "GRAVE"]
            sem_ncm = [r for r in todos_itens if r.get("Status TTD409") == "SEM NCM NO XML"]
            ncm_distintos = len({str(r.get("NCM", "")).strip() for r in todos_itens if str(r.get("NCM", "")).strip()})

            st.divider()
            st.markdown("**Auditoria TTD409**")

            # Stats cards — igual ao original
            cols = st.columns(5)
            for col, num, lbl in [
                (cols[0], len(auditorias), "XMLs analisados"),
                (cols[1], len(todos_itens), "Itens analisados"),
                (cols[2], len(bloqueios), "Bloqueios graves"),
                (cols[3], len(sem_ncm), "Itens sem NCM"),
                (cols[4], ncm_distintos, "NCMs distintos"),
            ]:
                col.markdown(_stat_card(num, lbl), unsafe_allow_html=True)

            st.divider()
            _render_ttd409_alertas(bloqueios, "Bloqueios graves TTD409")

            if sem_ncm:
                st.markdown(f"""<div style="background:#fff8e1;border-left:4px solid #f59e0b;border-radius:6px;padding:0.8rem 1.1rem;margin:1rem 0;">
<strong>{len(sem_ncm)} item(ns)</strong> estao sem NCM no XML.
Esses itens precisam de revisao manual antes de qualquer enquadramento no TTD409.
</div>""", unsafe_allow_html=True)
                with st.expander("Itens sem NCM", expanded=True):
                    st.dataframe(pd.DataFrame(sem_ncm), use_container_width=True, hide_index=True)

            if erros:
                with st.expander(f"{len(erros)} XML(s) com erro de leitura", expanded=True):
                    st.dataframe(pd.DataFrame(erros), use_container_width=True, hide_index=True)

            if todos_itens:
                ordenados = sorted(
                    todos_itens,
                    key=lambda r: (
                        0 if r.get("Gravidade") == "GRAVE" else 1,
                        r.get("Arquivo XML", ""),
                        str(r.get("nItem", "")),
                    ),
                )
                with st.expander("Todos os itens analisados", expanded=False):
                    st.dataframe(pd.DataFrame(ordenados), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum item encontrado nos XMLs analisados.")

            # Resumo por arquivo
            st.markdown("#### Resumo por arquivo")
            for aud in auditorias:
                sts = aud.get("stats", {})
                nome = aud.get("nome_original", sts.get("arquivo", ""))
                itens_arq = aud.get("itens", [])
                bloqueios_arq = [r for r in itens_arq if r.get("Gravidade") == "GRAVE"]

                with st.container(border=True):
                    icon = "🔴" if bloqueios_arq or sts.get("erros") else "🟢"
                    st.markdown(f"**{icon} {nome}**")
                    ca, cb, cc = st.columns(3)
                    ca.write(f"Itens: {sts.get('itens_analisados', 0)}")
                    cb.write(f"Bloqueios TTD409: {sts.get('bloqueios_ttd409', 0)}")
                    cc.write(f"Sem NCM: {sts.get('itens_sem_ncm', 0)}")
                    if bloqueios_arq:
                        with st.expander("Bloqueios deste arquivo", expanded=True):
                            st.dataframe(pd.DataFrame(bloqueios_arq), use_container_width=True, hide_index=True)

            st.divider()

            # Download relatório
            rel = gerar_relatorio_ttd409(auditorias)
            st.download_button(
                "📥 Baixar relatorio TTD409 (.xlsx)",
                data=rel,
                file_name="relatorio_ttd409_xmls_importacao.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    st.divider()

    # =====================================================================
    # ABA 2: Consulta rápida de NCM
    # =====================================================================
    with st.container(border=True):
        st.markdown("#### 🔍 Consultar NCM individual")
        st.caption("Digite um NCM para verificar se ele esta nas bases CAMEX e TTD409.")

        ncm_in = st.text_input("NCM (8 digitos):", placeholder="Ex: 84713012", key="cx_ncm")
        if ncm_in:
            ncm = ncm_in.replace(".", "").replace("-", "").strip()
            if len(ncm) == 8 and ncm.isdigit():
                with st.spinner("Consultando..."):
                    ttd = buscar_ttd409_por_ncm(ncm)
                    cam = buscar_camex_por_ncm(ncm)

                if ttd:
                    _render_ttd409_alertas([{
                        "Gravidade": "GRAVE",
                        "NCM": ncm,
                        "Descricao Legal": " | ".join(f"Item {m.get('item', '?')}" for m in ttd),
                        "Base Legal": "Decreto SC 2.128/2009",
                        "Detalhes": " | ".join(f"{m.get('descricao_legal', '')[:120]}" for m in ttd),
                        "Acao": "Nao incluir no TTD409 sem revisao",
                    }], "Alerta TTD409")
                else:
                    st.success(f" NCM **{ncm}** liberado para TTD409")

                if cam:
                    _render_camex_alertas([{
                        "NCM": ncm,
                        "Listas": " | ".join(f"{m.get('lista','?')}: {m.get('descricao','')[:60]}" for m in cam[:5]),
                        "Qtd. listas": len(cam),
                    }], "Alertas CAMEX")
                else:
                    st.success(f" NCM **{ncm}** nao encontrado na base CAMEX/Gecex")
            else:
                st.warning("NCM deve ter 8 digitos numericos (ex: 84713012)")

    st.divider()

    # =====================================================================
    # ABA 3: Consulta em lote (CSV/Excel)
    # =====================================================================
    with st.container(border=True):
        st.markdown("#### 📂 Consultar lote de NCMs")
        st.caption("Upload de arquivo CSV ou Excel com coluna NCM para auditar em massa.")

        lote = st.file_uploader("Arquivo com coluna NCM", type=["csv", "xlsx", "xls"], key="cx_lote")
        if lote is not None:
            try:
                df = pd.read_csv(lote, dtype=str) if lote.name.endswith(".csv") else pd.read_excel(lote, dtype=str)
                col_ncm = next((c for c in df.columns if "ncm" in str(c).lower()), None)
                if col_ncm is None:
                    st.error("Nenhuma coluna com 'NCM' encontrada. Colunas: " + ", ".join(df.columns))
                    st.dataframe(df.head(5))
                else:
                    ttd409_al = []
                    camex_al = []
                    total = 0
                    with st.spinner(f"Auditando {len(df)} linha(s)..."):
                        for _, row in df.iterrows():
                            n = str(row[col_ncm]).replace(".", "").replace("-", "").strip()
                            ext = str(row.get("EXTIPI", "")).strip() if "EXTIPI" in df.columns else ""
                            if len(n) == 8 and n.isdigit():
                                total += 1
                                ttd = buscar_ttd409_por_ncm(n)
                                cam = buscar_camex_por_ncm(n, ext)
                                for m in ttd:
                                    ttd409_al.append({
                                        "Gravidade": "GRAVE", "NCM": n,
                                        "Item Decreto": m.get("item", "?"),
                                        "Descricao Legal": m.get("descricao_legal", "")[:120],
                                        "Base Legal": "Decreto SC 2.128/2009",
                                        "Acao": "Nao incluir no TTD409 sem revisao fiscal",
                                    })
                                for m in cam:
                                    camex_al.append({
                                        "NCM": n, "Lista": m.get("lista", "?"),
                                        "EX": m.get("ex", "-"),
                                        "Vigencia": f"{m.get('inicio_vigencia','?')} a {m.get('fim_vigencia','?')}",
                                        "Descricao": m.get("descricao", "")[:100],
                                        "Ato Legal": m.get("ato_legal", "-"),
                                    })

                    st.info(f"**{total}** NCM(s) · **{len(camex_al)}** CAMEX · **{len(ttd409_al)}** TTD409")
                    _render_ttd409_alertas(ttd409_al, f"{len(ttd409_al)} bloqueio(s) TTD409")
                    _render_camex_alertas(camex_al, f"{len(camex_al)} ocorrencia(s) CAMEX")
                    if ttd409_al or camex_al:
                        rel = pd.DataFrame(ttd409_al + camex_al)
                        st.download_button("📥 Baixar CSV", data=rel.to_csv(index=False).encode("utf-8"),
                                           file_name="auditoria_camex_ttd409.csv", mime="text/csv",
                                           use_container_width=True)
            except Exception as e:
                st.error(f"Erro: {e}")