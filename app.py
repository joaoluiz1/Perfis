import os
import streamlit as st
import pandas as pd
import numpy as np

# ==============================================================================
# MÓDULO MATEMÁTICO DE ENGENHARIA (FÁCIL AUDITORIA)
# As funções abaixo representam as equações da NBR 14762
# ==============================================================================

def calc_tracao(area_g, fy, gama_m):
    """ Resistência à Tração (Escoamento da Seção Bruta) """
    nt_rd = (area_g * fy) / gama_m
    return nt_rd

def calc_compressao_global(area_g, rx, ry, lx, ly, fy, E, gama_m):
    """ Resistência à Compressão (Curva de Flambagem de Euler) """
    lambda_x = lx / rx if rx > 0 else 999.0
    lambda_y = ly / ry if ry > 0 else 999.0
    
    fe_x = (np.pi**2 * E) / (lambda_x**2)
    fe_y = (np.pi**2 * E) / (lambda_y**2)
    fe = min(fe_x, fe_y)
    
    lambda_0 = np.sqrt(fy / fe) if fe > 0 else 999.0
    
    # Fator de redução (rho) conforme NBR 14762
    if lambda_0 <= 1.5:
        fator_rho = 0.658**(lambda_0**2)
    else:
        fator_rho = 0.877 / (lambda_0**2)
        
    nc_rd = (fator_rho * area_g * fy) / gama_m
    return nc_rd, lambda_0

def calc_momentos_resistentes(wx, wy, iy, it, cw, lt, fy, E, G, gama_m):
    """ Resistência à Flexão (Considerando Flambagem Lateral com Torção - FLT) """
    # M_plástico
    m_pl_x = (wx * fy / 100.0) 
    m_pl_y = (wy * fy / 100.0)
    
    # M_crítico elástico (FLT)
    if it > 0.001 and cw > 0.001:
        termo_torcao = E * iy * G * it
        termo_empenamento = ((np.pi * E / lt)**2) * iy * cw
        m_cr_flt = (np.pi / lt) * np.sqrt(termo_torcao + termo_empenamento) / 100.0
    else:
        m_cr_flt = 9999.0 # Imune à FLT (ex: tubos fechados ou travamento contínuo)
        
    mx_rd = min(m_pl_x, m_cr_flt) / gama_m if gama_m > 0 else 1.0
    my_rd = m_pl_y / gama_m if gama_m > 0 else 1.0
    
    return mx_rd, my_rd

def calc_cortante(h, t, fy, E, gama_m):
    """ Resistência ao Cortante (Fases Plástica, Inelástica e Elástica) """
    h_w = max(h - (2 * t), 0.1) # Altura plana da alma
    h_t = h_w / t
    kv = 5.34 # Fator de cisalhamento para alma sem enrijecedor transversal
    
    limite_escoamento = 1.08 * np.sqrt((E * kv) / fy)
    limite_inelastico = 1.40 * np.sqrt((E * kv) / fy)
    
    if h_t <= limite_escoamento:
        tau_c = 0.60 * fy
        fase = "Plástica"
    elif h_t <= limite_inelastico:
        tau_c = (0.64 * np.sqrt(E * kv * fy)) / h_t
        fase = "Inelástica"
    else:
        tau_c = (0.90 * E * kv) / (h_t**2)
        fase = "Elástica"
        
    area_alma = (h * t) / 100.0
    v_rd = (area_alma * tau_c) / gama_m
    
    return v_rd, h_t, tau_c, fase

def calc_interacoes(n_sd_comp, n_sd_trac, m_sd_x, m_sd_y, v_sd, nt_rd, nc_rd, mx_rd, my_rd, v_rd):
    """ Equações de Combinação de Esforços """
    taxa_tracao = (n_sd_trac / nt_rd)
    taxa_compressao = (n_sd_comp / nc_rd)
    taxa_cortante = (v_sd / v_rd)
    
    taxa_flexo_comp = (n_sd_comp / nc_rd) + (m_sd_x / mx_rd) + (m_sd_y / my_rd)
    taxa_flexo_cortante = ((m_sd_x / mx_rd)**2) + ((v_sd / v_rd)**2)
    
    taxa_maxima = max(taxa_tracao, taxa_compressao, taxa_cortante, taxa_flexo_comp, taxa_flexo_cortante)
    
    return {
        "T_Tracao": taxa_tracao, 
        "T_Compressao": taxa_compressao, 
        "T_Cortante": taxa_cortante,
        "T_FlexoComp": taxa_flexo_comp, 
        "T_FlexoCort": taxa_flexo_cortante,
        "Max_Global": taxa_maxima
    }

# ==============================================================================
# FIM DO MÓDULO MATEMÁTICO - INÍCIO DA INTERFACE (STREAMLIT)
# ==============================================================================

st.set_page_config(layout="wide", page_title="Dimensionamento NBR 14762")
st.title("Sistema de Dimensionamento e Otimização - NBR 6355 / NBR 14762")

pasta_do_script = os.path.dirname(os.path.abspath(__file__))
caminho_excel = os.path.join(pasta_do_script, "Perfis NBR 6355.xlsx")

mapa_imagens = {
    "L Sem Revestimento": "Cantoneiras de Abas Iguais.png",
    "U Sem Revestimento": "U Simples.png",
    "Ue Sem Revestimento": "U Enrigecido.png",
    "Ue Zincado": "U Enrigecido.png",
    "Z90 Sem Revestimento": "Z Enrigecido a 90.png",
    "Z45 Sem Revestimento": "Z Enrigecido a 45.png",
    "CR Sem Revestimento": "Cartola.png",
    "CR Zincado": "Cartola.png"
}

@st.cache_data
def carregar_dados():
    try:
        xls = pd.ExcelFile(caminho_excel)
    except FileNotFoundError:
        st.error(f"Arquivo Excel não encontrado: {caminho_excel}")
        st.stop()
        
    dfs = {}
    for sheet in xls.sheet_names:
        df_sheet = pd.read_excel(xls, sheet_name=sheet, skiprows=2)
        df_sheet.rename(columns={df_sheet.columns[0]: "Perfil"}, inplace=True)
        df_sheet.insert(0, "Selecionar", False)
        dfs[sheet] = df_sheet
    return dfs

dicionario_dfs = carregar_dados()

# --- PAINEL LATERAL (SOLICITAÇÕES) ---
st.sidebar.header("1. Cargas (ex: Ftool)")
n_sd_comp = st.sidebar.number_input("Compressão N_Sd (kN)", value=10.0)
n_sd_trac = st.sidebar.number_input("Tração N_t,Sd (kN)", value=0.0)
m_sd_x = st.sidebar.number_input("Momento M_x,Sd (kNm)", value=1.5)
m_sd_y = st.sidebar.number_input("Momento M_y,Sd (kNm)", value=0.2)
v_sd = st.sidebar.number_input("Esforço Cortante V_Sd (kN)", value=3.0)

st.sidebar.markdown("---")
st.sidebar.header("2. Geometria e Aço")
fy_mpa = st.sidebar.number_input("Escoamento do Aço f_y (MPa)", value=250.0)
lx = st.sidebar.number_input("Comprimento Livre L_x (cm)", value=300.0)
ly = st.sidebar.number_input("Comprimento Livre L_y (cm)", value=150.0)
lt = st.sidebar.number_input("Comprimento de Torção L_t (cm)", value=150.0)

# Constantes globais convertidas
fy = fy_mpa / 10.0  # kN/cm²
E = 20000.0         # kN/cm²
G = 7700.0          # kN/cm²
gama_m = 1.10

# Extrator de Dados Blindado
def get_val(row, chaves_busca):
    for col in row.index:
        col_normalizada = str(col).lower().replace('\n', '').replace('\r', '').replace(' ', '').replace('³', '3').replace('²', '2')
        for chave in chaves_busca:
            chave_normalizada = chave.lower().replace(' ', '').replace('³', '3').replace('²', '2')
            if chave_normalizada in col_normalizada:
                val = row[col]
                if pd.notna(val) and val != "":
                    try:
                        if isinstance(val, str):
                            val = val.replace(",", ".").strip()
                        return float(val)
                    except ValueError:
                        pass
    return 0.00001 

# --- AVALIADOR CENTRAL ---
def avaliar_perfil(peca):
    """ Puxa os dados do Excel e envia para as funções matemáticas """
    # 1. Leitura
    area = get_val(peca, ["acm2", "acm"])
    peso = get_val(peca, ["mkg/m", "kg/m"])
    ix, iy = get_val(peca, ["ixcm4", "ix=iycm4"]), get_val(peca, ["iycm4", "ix=iycm4"])
    wx, wy = get_val(peca, ["wxcm3", "wx=wycm3"]), get_val(peca, ["wycm3", "wx=wycm3"])
    rx, ry = get_val(peca, ["rxcm", "rx=rycm"]), get_val(peca, ["rycm", "rx=rycm"])
    it, cw = get_val(peca, ["itcm4"]), get_val(peca, ["cwcm6"])
    h, t = get_val(peca, ["bwmm", "bfmm"]), get_val(peca, ["tnmm", "t=tnmm"])
    
    # 2. Cálculos (Chamando as funções limpas)
    nt_rd = calc_tracao(area, fy, gama_m)
    nc_rd, lambda_0 = calc_compressao_global(area, rx, ry, lx, ly, fy, E, gama_m)
    mx_rd, my_rd = calc_momentos_resistentes(wx, wy, iy, it, cw, lt, fy, E, G, gama_m)
    v_rd, h_t, tau_c, fase_cortante = calc_cortante(h, t, fy, E, gama_m)
    
    # 3. Interações
    taxas = calc_interacoes(n_sd_comp, n_sd_trac, m_sd_x, m_sd_y, v_sd, nt_rd, nc_rd, mx_rd, my_rd, v_rd)
    
    return {
        "Perfil": peca["Perfil"], "Peso (kg/m)": peso, "Eficiência Máxima (%)": taxas["Max_Global"] * 100,
        "Nc_Rd (kN)": nc_rd, "Mx_Rd (kNm)": mx_rd, "V_Rd (kN)": v_rd,
        "T_Tracao": taxas["T_Tracao"], "T_Compressao": taxas["T_Compressao"], "T_Cortante": taxas["T_Cortante"],
        "T_FlexoComp": taxas["T_FlexoComp"], "T_FlexoCort": taxas["T_FlexoCort"],
        "Aprovada": taxas["Max_Global"] <= 1.0,
        "h": h, "t": t, "area": area, "h_t": h_t, "tau_c": tau_c, "fase_cortante": fase_cortante
    }


def render_status(nome, taxa):
    if taxa <= 1.0:
        return f"✅ **{nome}**: {taxa*100:.1f}% (Passou)"
    else:
        return f"❌ **{nome}**: {taxa*100:.1f}% (FALHOU)"

def aplicar_estilo(df):
    def cor_status(val):
        return 'background-color: #198754; color: white;' if val <= 100.0 else 'background-color: #dc3545; color: white;'
    df_reduzido = df[["Perfil", "Peso (kg/m)", "Eficiência Máxima (%)", "Nc_Rd (kN)", "Mx_Rd (kNm)", "V_Rd (kN)"]].round(2)
    if hasattr(df_reduzido.style, "map"):
        return df_reduzido.style.map(cor_status, subset=["Eficiência Máxima (%)"])
    return df_reduzido.style.applymap(cor_status, subset=["Eficiência Máxima (%)"])

# --- ÁREA PRINCIPAL COM ABAS ---
tab_manual, tab_auto, tab_memorial = st.tabs(["🛠️ Seleção Manual", "🚀 Auto-Dimensionamento", "📐 Memorial Detalhado"])

pecas_selecionadas_globais = []

# ABA 1: SELEÇÃO MANUAL
with tab_manual:
    nomes_abas_excel = list(dicionario_dfs.keys())
    abas_ui = st.tabs(nomes_abas_excel)

    for i, nome_aba in enumerate(nomes_abas_excel):
        with abas_ui[i]:
            col_img, col_tabela = st.columns([1, 4])
            with col_img:
                nome_imagem = mapa_imagens.get(nome_aba)
                caminho_img = os.path.join(pasta_do_script, str(nome_imagem))
                if os.path.exists(caminho_img):
                    st.image(caminho_img, use_container_width=True)
            with col_tabela:
                df_editado = st.data_editor(
                    dicionario_dfs[nome_aba], hide_index=True, use_container_width=True,
                    column_config={"Selecionar": st.column_config.CheckboxColumn(required=True)},
                    disabled=dicionario_dfs[nome_aba].columns.drop("Selecionar"), key=f"editor_{nome_aba}"
                )
                selecionadas = df_editado[df_editado["Selecionar"]]
                if not selecionadas.empty:
                    selecionadas = selecionadas.copy()
                    selecionadas["Categoria"] = nome_aba
                    pecas_selecionadas_globais.append(selecionadas)

    if pecas_selecionadas_globais:
        df_analise = pd.concat(pecas_selecionadas_globais, ignore_index=True)
        resultados_manuais = [avaliar_perfil(row) for idx, row in df_analise.iterrows()]
        df_resultados_manuais = pd.DataFrame(resultados_manuais)
        st.subheader("Painel Comparativo - Peças Selecionadas")
        st.dataframe(aplicar_estilo(df_resultados_manuais), use_container_width=True, column_config={"Eficiência Máxima (%)": st.column_config.NumberColumn("Uso Máximo (%)", format="%.1f%%")})

# ABA 2: AUTO-DIMENSIONAMENTO
with tab_auto:
    st.header("Motor de Auto-Dimensionamento")
    categoria_auto = st.selectbox("Qual geometria deseja utilizar?", options=list(dicionario_dfs.keys()))
    if st.button("Executar Otimização 🚀"):
        df_categoria = dicionario_dfs[categoria_auto]
        resultados_auto = [avaliar_perfil(row) for idx, row in df_categoria.iterrows()]
        df_res_auto = pd.DataFrame(resultados_auto)
        df_aprovadas = df_res_auto[df_res_auto["Aprovada"] == True].copy()
        
        if df_aprovadas.empty:
            st.error(f"Nenhum perfil resiste aos esforços! Reduza as cargas ou os vãos.")
        else:
            df_aprovadas = df_aprovadas.sort_values(by="Peso (kg/m)")
            st.success(f"Encontradas {len(df_aprovadas)} opções viáveis! A primeira é a mais leve.")
            st.dataframe(aplicar_estilo(df_aprovadas), use_container_width=True, column_config={"Eficiência Máxima (%)": st.column_config.NumberColumn("Uso Máximo (%)", format="%.1f%%")})

# ABA 3: MEMORIAL E DIAGNÓSTICO
with tab_memorial:
    st.warning("⚠️ **Nota Normativa:** Este memorial realiza as verificações **Globais**. Por se tratar de Perfis Formados a Frio (PFF), a NBR 14762 exige, para projeto executivo final, a verificação da Flambagem Local e Distorcional (cálculo da Área Efetiva - Aef).")
    
    if pecas_selecionadas_globais:
        perfil_memorial = st.selectbox("Selecione qual das peças você quer visualizar em detalhe:", options=df_resultados_manuais["Perfil"].tolist())
        res = df_resultados_manuais[df_resultados_manuais["Perfil"] == perfil_memorial].iloc[0]
        
        st.header(f"Diagnóstico NBR 14762: {res['Perfil']}")
        st.info(f"**Dados Extraídos:** h = {res['h']:.2f} mm | t = {res['t']:.2f} mm | Ag = {res['area']:.2f} cm²")
        
        col_diag1, col_diag2 = st.columns(2)
        with col_diag1:
            st.markdown(render_status("Esforço Normal de Tração", res["T_Tracao"]))
            st.markdown(render_status("Compressão Global de Euler", res["T_Compressao"]))
            st.markdown(render_status("Esforço Cortante na Alma", res["T_Cortante"]))
        with col_diag2:
            st.markdown(render_status("Flexo-Compressão Biaxial", res["T_FlexoComp"]))
            st.markdown(render_status("Flexão + Cisalhamento", res["T_FlexoCort"]))

        st.markdown("---")
        st.subheader("Fórmulas Matemáticas do Desempenho")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Compressão e Momento")
            st.latex(r"N_{c,Rd} = \frac{\chi \cdot A_g \cdot f_y}{\gamma_m}")
            st.latex(f"N_{{c,Rd}} = {res['Nc_Rd (kN)']:.2f} \\text{{ kN}}")
            st.latex(r"M_{x,Rd} = \frac{\min(M_{pl}, M_{cr})}{\gamma_m}")
            st.latex(f"M_{{x,Rd}} = {res['Mx_Rd (kNm)']:.2f} \\text{{ kNm}}")

        with col2:
            st.markdown("### Cortante (Flambagem na Alma)")
            st.write(f"Esbeltez da alma ($h_w/t$): **{res['h_t']:.2f}**")
            st.write(f"Fase Normativa de Falha: **{res['fase_cortante']}**")
            st.latex(r"V_{Rd} = \frac{A_w \cdot \tau_c}{\gamma_m}")
            st.latex(f"V_{{Rd}} = {res['V_Rd (kN)']:.2f} \\text{{ kN}}")

    else:
        st.info("⚠️ Vá até a aba 'Seleção Manual', marque pelo menos um perfil e retorne aqui.")

st.markdown("<br><hr><div style='text-align: center; color: gray;'>Criado por João Luiz<br>Email: joaoluiz@outlook.com</div>", unsafe_allow_html=True)