# -*- coding: utf-8 -*-
"""
Módulo NF-e Editor para aba unificada — Importação DUIMP / XML F5 → Bling
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

try:
    from modules.database import (
        init_db, get_all_eans, upsert_eans, salvar_ean_manual,
        get_db_stats, buscar_camex_por_ncm, get_camex_stats,
        buscar_ttd409_por_ncm, get_ttd409_stats,
    )
    from modules.excel_loader import carregar_planilha_ean, carregar_planilha_xmlf5
    from modules.xml_service import (
        auditar_ttd409_xml, gerar_relatorio_ttd409, processar_xml,
    )
    _OK = True
except ImportError as e:
    _OK = False
    _ERR = str(e)

def _digitos(s):
    return "".join(c for c in str(s) if c.isdigit())

def _resumir_camex(matches, limite=6):
    partes = []
    for m in matches[:limite]:
        ex = f" Ex {m.get('ex')}" if m.get("ex") else ""
        vig = ""
        if m.get("inicio_vigencia") or m.get("fim_vigencia"):
            vig = f" ({m.get('inicio_vigencia') or '?'} a {m.get('fim_vigencia') or '?'})"
        ato = f" - {m.get('ato_legal')}" if m.get("ato_legal") else ""
        partes.append(f"{m.get('lista', '')}{ex}{vig}{ato}")
    if len(matches) > limite:
        partes.append(f"+{len(matches)-limite} mais")
    return " | ".join(partes)

def _aviso_camex(alertas, titulo="Itens na base CAMEX/Gecex"):
    if not alertas:
        return
    st.markdown(f"""<div style="background:#eef6ff;border-left:4px solid #2563eb;border-radius:6px;padding:0.8rem;margin:1rem 0">
    <strong>{len(alertas)} item(ns)</strong> possuem NCM em lista CAMEX/Gecex vigente.</div>""", unsafe_allow_html=True)
    with st.expander(titulo, expanded=True):
        st.dataframe(pd.DataFrame(alertas), use_container_width=True, hide_index=True)

def _aviso_ttd409(alertas, titulo="Bloqueios TTD409"):
    if not alertas:
        return
    st.markdown(f"""<div style="background:#fff1f2;border-left:5px solid #dc2626;border-radius:6px;padding:0.9rem;margin:1rem 0;color:#7f1d1d">
    <strong>ALERTA TTD409:</strong> {len(alertas)} item(ns) batem com Decreto SC 2.128/2009.</div>""", unsafe_allow_html=True)
    with st.expander(titulo, expanded=True):
        st.dataframe(pd.DataFrame(alertas), use_container_width=True, hide_index=True)

def render_nfe_tab() -> None:
    if not _OK:
        st.warning(f"Módulos NF-e Editor não carregados: {_ERR}")
        st.info("Verifique se database.py, xml_service.py e excel_loader.py estão em modules/")
        return

    init_db()

    for k, v in {
        "nfe_stage": "input", "nfe_xmls": [], "nfe_faltantes": [],
        "nfe_resultados": [], "nfe_mapa_fiscal": {},
        "nfe_camex": [], "nfe_ttd409": [], "nfe_audits": [],
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    st.markdown("### NF-e Editor · Importação DUIMP → Bling")
    st.caption("Ajustes: EAN · ICMS zerado · IPI · PIS/COFINS · CAMEX/TTD409")

    with st.sidebar:
        st.markdown("#### Base de EANs")
        db = get_db_stats()
        c1, c2 = st.columns(2)
        c1.metric("SKUs", db["total"])
        c2.metric("Atualiz.", (db["ultima_atualizacao"] or "-")[:10])
        plan = st.file_uploader("Planilha EAN", type=["xlsx", "xls", "csv"], key="nfe_ean", label_visibility="collapsed")
        if plan and st.button("Importar", key="nfe_imp", use_container_width=True):
            try:
                r = carregar_planilha_ean(plan.getvalue(), plan.name)
                if r:
                    ins, upd, err = upsert_eans(r)
                    st.success(f"{ins} in + {upd} up" + (f" + {err} er" if err else ""))
                    st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
        st.divider()
        st.metric("CAMEX NCMs", get_camex_stats()["ncm_vigentes"])
        st.metric("TTD409 itens", get_ttd409_stats()["itens_legais"])

    # ── INPUT ──
    if st.session_state.nfe_stage == "input":
        c1, c2 = st.columns(2)
        with c1:
            xmls = st.file_uploader("XMLs NF-e", type=["xml"], accept_multiple_files=True, key="nfe_xml")
        with c2:
            plan = st.file_uploader("Planilha F5", type=["xlsx", "xls", "csv"], key="nfe_f5")

        ca, cb = st.columns(2)
        with ca:
            aud = st.button("Conferir TTD409", type="primary", disabled=not xmls, key="nfe_aud")
        with cb:
            ana = st.button("Analisar XMLs", type="primary", disabled=(not xmls or not plan), key="nfe_ana")

        if aud and xmls:
            lst = [(f.name, f.getvalue()) for f in xmls]
            auds = []
            with st.spinner("Conferindo TTD409..."):
                for n, d in lst:
                    it, sts = auditar_ttd409_xml(d, n, buscar_ttd409_por_ncm)
                    auds.append({"nome": n, "itens": it, "stats": sts})
            st.session_state.nfe_xmls = lst
            st.session_state.nfe_audits = auds
            st.session_state.nfe_stage = "ttd409"
            st.rerun()

        if ana and xmls and plan:
            try:
                mf = carregar_planilha_xmlf5(plan.getvalue(), plan.name)
            except Exception as e:
                return st.error(f"Erro planilha F5: {e}")
            me = get_all_eans()
            lst = [(f.name, f.getvalue()) for f in xmls]
            falt, camex, ttd = [], [], []
            for n, d in lst:
                try:
                    from lxml import etree
                    p = etree.XMLParser(recover=True, huge_tree=True)
                    root = etree.parse(io.BytesIO(d), p).getroot()
                    for det in root.xpath(".//*[local-name()='det']"):
                        prod = next(iter(det.xpath("./*[local-name()='prod']")), None)
                        if prod is None:
                            continue
                        cp = next(iter(prod.xpath("./*[local-name()='cProd']/text()")), "").strip()
                        xp = next(iter(prod.xpath("./*[local-name()='xProd']/text()")), "").strip()
                        ncm = next(iter(prod.xpath("./*[local-name()='NCM']/text()")), "").strip()
                        ext = next(iter(prod.xpath("./*[local-name()='EXTIPI']/text()")), "").strip()
                        if ncm:
                            mt = buscar_ttd409_por_ncm(ncm)
                            if mt:
                                ttd.append({"Arquivo": n, "nItem": det.get("nItem",""), "SKU": cp,
                                            "NCM": ncm, "Descricao": xp, "Regras": "; ".join(
                                    f"Item {m.get('item')}" for m in mt)})
                            mc = buscar_camex_por_ncm(ncm, ext)
                            if mc:
                                camex.append({"Arquivo": n, "nItem": det.get("nItem",""), "SKU": cp,
                                              "NCM": ncm, "Descricao": xp, "Listas": _resumir_camex(mc)})
                        if cp and not me.get(cp):
                            ce = next(iter(prod.xpath("./*[local-name()='cEAN']/text()")), "").strip()
                            falt.append({"Arquivo": n, "nItem": det.get("nItem",""), "SKU": cp,
                                         "Descricao": xp, "cEAN": ce, "EAN": ""})
                except Exception as e:
                    st.warning(f"Erro em {n}: {e}")
            st.session_state.nfe_xmls = lst
            st.session_state.nfe_mapa_fiscal = mf
            st.session_state.nfe_faltantes = falt
            st.session_state.nfe_camex = camex
            st.session_state.nfe_ttd409 = ttd
            if falt:
                st.session_state.nfe_stage = "fill_ean"
            else:
                res = []
                with st.spinner("Processando XMLs..."):
                    for n, d in lst:
                        o, s = processar_xml(d, get_all_eans(), n, mf, buscar_camex_por_ncm, buscar_ttd409_por_ncm)
                        res.append({"nome": n, "xml": o, "stats": s})
                st.session_state.nfe_resultados = res
                st.session_state.nfe_stage = "results"
            st.rerun()

    # ── TTD409 AUDIT ──
    elif st.session_state.nfe_stage == "ttd409":
        auds = st.session_state.nfe_audits
        todos, erros = [], []
        for a in auds:
            todos.extend(a.get("itens", []))
            erros.extend({"Arquivo": a.get("nome",""), "Erro": e} for e in a.get("stats",{}).get("erros",[]))
        bloqueios = [r for r in todos if r.get("Gravidade") == "GRAVE"]
        st.markdown("**Auditoria TTD409**")
        c1, c2, c3 = st.columns(3)
        c1.metric("XMLs", len(auds))
        c2.metric("Itens", len(todos))
        c3.metric("Bloqueios", len(bloqueios))
        _aviso_ttd409(bloqueios)
        if todos:
            with st.expander("Todos os itens"):
                st.dataframe(pd.DataFrame(todos), use_container_width=True, hide_index=True)
        rel = gerar_relatorio_ttd409(auds)
        st.download_button("Baixar relatório TTD409 (.xlsx)", data=rel,
                           file_name="relatorio_ttd409.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if st.button("Voltar"):
            st.session_state.nfe_stage = "input"
            st.rerun()

    # ── FILL EAN ──
    elif st.session_state.nfe_stage == "fill_ean":
        _aviso_ttd409(st.session_state.nfe_ttd409)
        _aviso_camex(st.session_state.nfe_camex)
        st.markdown(f"**{len(st.session_state.nfe_faltantes)} item(ns) sem EAN**")
        df = pd.DataFrame(st.session_state.nfe_faltantes)
        ed = st.data_editor(df, column_config={
            "EAN": st.column_config.TextColumn("EAN", width="medium"),
        }, disabled=["Arquivo", "nItem", "SKU", "Descricao", "cEAN"],
                             use_container_width=True, hide_index=True, num_rows="fixed")
        if st.button("Salvar EANs e Processar", type="primary", use_container_width=True):
            salvos = 0
            for _, r in ed.iterrows():
                e = str(r.get("EAN", "")).strip()
                if e and _digitos(e):
                    salvar_ean_manual(r["SKU"], _digitos(e), r.get("Descricao", ""))
                    salvos += 1
            if salvos:
                st.toast(f"{salvos} EAN(s) salvos!")
            res = []
            with st.spinner("Processando XMLs..."):
                for n, d in st.session_state.nfe_xmls:
                    o, s = processar_xml(d, get_all_eans(), n, st.session_state.nfe_mapa_fiscal,
                                         buscar_camex_por_ncm, buscar_ttd409_por_ncm)
                    res.append({"nome": n, "xml": o, "stats": s})
            st.session_state.nfe_resultados = res
            st.session_state.nfe_stage = "results"
            st.rerun()

    # ── RESULTS ──
    elif st.session_state.nfe_stage == "results":
        res = st.session_state.nfe_resultados
        st.markdown("**Processamento concluído!**")
        ok = sum(1 for r in res if not r["stats"]["erros"] and r["xml"])
        c1, c2 = st.columns(2)
        c1.metric("XMLs", len(res))
        c2.metric("OK", ok)
        for r in res:
            s = r["stats"]
            with st.container(border=True):
                icon = "OK" if not s["erros"] else "ERRO"
                st.markdown(f"**{icon} {r['nome']}**")
                cols = st.columns(5)
                cols[0].write(f"EAN criados: {s.get('ean_criados',0)}")
                cols[1].write(f"EAN ausentes: {s.get('ean_ausentes',0)}")
                cols[2].write(f"ICMS zerados: {s.get('icms_zerados',0)}")
                cols[3].write(f"IBS/CBS: {s.get('ibscbs_itens_gerados',0)}")
                cols[4].write(f"Erros: {len(s.get('erros',[]))}")
                if s["erros"]:
                    with st.expander("Erros"):
                        for e in s["erros"]:
                            st.write(f"- {e}")
        if res:
            z = io.BytesIO()
            with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in res:
                    if r["xml"]:
                        zf.writestr(r["nome"].replace(".xml", "_processado.xml"), r["xml"])
            z.seek(0)
            st.download_button("Baixar XMLs processados (ZIP)", data=z,
                               file_name="xmls_processados.zip", mime="application/zip",
                               use_container_width=True)
        if st.button("Novo processamento", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("nfe_"):
                    del st.session_state[k]
            st.rerun()