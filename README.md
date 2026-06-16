# ICMS + NF-e Unificado

App Streamlit unificado para workflow de importação:

- **📊 ICMS SUL — TDD 409**: Calcula ICMS TDD 409 a partir de planilha DUIMP/DI
- **📄 NF-e Editor — Bling**: Processa XML NF-e para emissão no Bling com verificação CAMEX/TTD409
- **🔍 CAMEX / TTD409 Check**: Consulta NCMs nas bases de exceção

## Como executar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Estrutura

```
├── app.py                    # Entry point com abas
├── app_icms_albema.py        # Entry point para Streamlit Cloud
├── modules/
│   ├── icms_calc.py          # Cálculo ICMS TDD 409
│   ├── nf_editor_app.py      # NF-e Editor (XML → Bling)
│   ├── camex_checker.py      # Consulta CAMEX/TTD409
│   ├── database.py           # Base de dados EAN + CAMEX + TTD409
│   ├── xml_service.py        # Processamento XML
│   └── excel_loader.py       # Leitura de planilhas
├── data/                     # Bases CAMEX/TTD409
├── tools/                    # Scripts de build
└── requirements.txt          # Dependências
```

## Workflow

1. **ICMS SUL** → Importar planilha DUIMP/DI → Calcular ICMS TDD 409
2. **CAMEX Check** → Verificar NCMs nas listas de exceção
3. **NF-e Editor** → Importar XML → Processar para Bling → Verificar CAMEX/TTD409

Cada aba é independente — uma não bloqueia a outra.