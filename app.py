import os
import streamlit as st
import pandas as pd
import numpy as np

# ==============================================================================
# MÓDULO MATEMÁTICO DE ENGENHARIA (NBR 14762)
# ==============================================================================

def calc_esbeltez(rx, ry, lx, ly):
    """ Verificação do Índice de Esbeltez Máximo (Limites: 200 Comp. / 300 Tração) """
    lambda_x = lx / rx if rx > 0 else 999.0
    lambda_y = ly / ry if ry > 0 else 999.0
    lambda_max = max(lambda_x, lambda_y)
    return lambda_x, lambda_y, lambda_max

def calc_tracao(area_g, fy, gama_m):
    """ Resistência à Tração (Escoamento da Seção Bruta) """
    nt_rd = (area_g * fy) / gama_m
    return nt_rd

def calc_compressao_global(area_g, lambda_x, lambda_y, fy, E, gama_m):
    """ Resistência à Compressão Global (Flambagem de Euler) """
    fe_x = (np.pi**2 * E) / (lambda_x**2) if lambda_x > 0 else 0.001
    fe_y = (np.pi**2 * E) / (lambda_y**2) if lambda_y > 0 else 0.001
    fe = min(fe_x, fe_y)
    
    lambda_0 = np.sqrt(fy / fe) if fe > 0 else 999.0
    
    if lambda_0 <= 1.5:
        fator_rho = 0.658**(lambda_0**2)
    else:
        fator_rho = 0.877 / (lambda_0**2)
        
    nc_rd = (fator_rho * area_g * fy) / gama_m
    return nc_rd, fe, lambda_0, fator_rho

def calc_momentos_resistentes(wx, wy, iy, it, cw, lt, fy, E, G, gama_m):
    """ Resistência à Flexão (Considerando Flambagem Lateral com Torção - FLT) """
    m_pl_x = (wx * fy / 100.0) 
    m_pl_y = (wy * fy / 100.0)
    
    if it > 0.001 and cw > 0.001:
        termo_torcao = E * iy * G * it
        termo_empenamento = ((np.pi * E / lt)**2) * iy * cw
        m_cr_flt = (np.pi / lt) * np.sqrt(termo_torcao + termo_empenamento) / 100.0
    else:
        m_cr_flt = 9999.0
        
    mx_rd = min(m_pl_x, m_cr_flt) / gama_m if gama_m > 0 else 1.0
    my_rd = m_pl_y / gama_m if gama_m > 0 else 1.0
    
    return mx_rd, my_rd, m_cr_flt, m_pl_x, m_pl_y

def calc_cortante(h, t, fy, E, gama_m):
    """ Resistência ao Cortante da Alma (Fases Plástica, Inelástica e Elástica) """
    h_w = max(h - (2 * t), 0.1) 
    h_t = h_w / t
    kv = 5.34 
    
    limite_escoamento = 1.08 * np.sqrt((E * kv) / fy)
    limite_inelastico = 1.40 * np.sqrt((E * kv) / fy)
    
    if h_t <= limite_escoamento:
        tau_c = 0.60 * fy
        fase = "Plástica (Escoamento Puro)"
    elif h_t <= limite_inelastico:
        tau_c = (0.64 * np.sqrt(E * kv * fy)) / h_t
        fase = "Inelástica (Transição)"
    else:
        tau_c = (0.90 * E * kv) / (h_t**2)
        fase = "Elástica (Flambagem Local da Alma)"
        
    area_alma = (h * t) / 100.0
    v_rd = (area_alma * tau_c) / gama_m
    
    return v_rd, h_t, tau_c, fase, limite_escoamento, limite_inelastico

def calc_interacoes(n_sd_comp, n_sd_trac, m_sd_x, m_sd_y, v_sd, nt_rd, nc_rd, mx_rd, my_rd, v_rd, lambda_max):
    """ Lógica Corrigida: As equações calculam a flexão mesmo com forças axiais nulas """
    taxa_tracao = (n_sd_trac / nt_rd) if nt_rd > 0 else 0.0
    taxa_compressao = (n_sd_comp / nc_rd) if nc_rd > 0 else 0.0
    taxa_cortante = (v_sd / v_rd) if v_rd > 0 else 0.0
    
    limite_esb = 200.0 if n_sd_comp > 0 else 300.0
    taxa_esbeltez = lambda_max / limite_esb
    
    taxa_momento_puro = (m_sd_x / mx_rd) + (m_sd_y / my_rd)
    
    # Cálculo contínuo para manter a consistência absoluta com o que é impresso no ecrã
    taxa_flexo_comp = taxa_compressao + taxa_momento_puro
    taxa_flexo_trac = taxa_tracao + taxa_momento_puro
    taxa_flexo_cortante = ((m_sd_x / mx_rd)**2) + ((v_sd / v_rd)**2)
    
    taxa_maxima = max(taxa_tracao, taxa_compressao, taxa_cortante, taxa_esbeltez, taxa_flexo_comp, taxa_flexo_trac, taxa_flexo_cortante)
    
    return {
        "T_Esbeltez": taxa_esbeltez, "T_Tracao": taxa_tracao, "T_Compressao": taxa_compressao, 
        "T_Cortante": taxa_cortante, "T_FlexoComp": taxa_flexo_comp, "T_FlexoTrac": taxa_flexo_trac,
        "T_FlexoCort": taxa_flexo_cortante, "Max_Global": taxa_maxima
    }

# ==============================================================================
# INTERFACE GRÁFICA INTERATIVA (STREAMLIT)
# ==============================================================================

st.set_page_config(layout="wide", page_title="Dimensionamento NBR 14762")
st.title("Sistema de Dimensionamento - NBR 6355 / NBR 14762")

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
    alvos_excel = [caminho_excel, os.path.join(pasta_do_script, "Perfim NBR 6355.xlsx")]
    sucesso = False
    for alvo in alvos_excel:
        if os.path.exists(alvo):
            xls = pd.ExcelFile(alvo)
            sucesso = True
            break
    if not scenario_ok := sucesso:
        st.error("Arquivo Excel de perfis não foi encontrado.")
        st.stop()
        
    dfs = {}
    for sheet in xls.sheet_names:
        df_sheet = pd.read_excel(xls, sheet_name=sheet, skiprows=2)
        df_sheet.rename(columns={df_sheet.columns[0]: "Perfil"}, inplace=True)
        df_sheet.insert(0, "Selecionar", False)
        dfs[sheet] = df_sheet
    return dfs

dicionario_dfs = carregar_dados()

# --- INPUTS LATERAIS COM PRECISÃO DE CASAS DECIMAIS ---
st.sidebar.header("1. Cargas (ex: Ftool)")
n_sd_comp = st.sidebar.number_input("Compressão N_Sd (kN)", value=10.0000, format="%.4f", step=0.0001)
n_sd_trac = st.sidebar.number_input("Tração N_t,Sd (kN)", value=0.0000, format="%.4f", step=0.0001)
m_sd_x = st.sidebar.number_input("Momento M_x,Sd (kNm)", value=1.5000, format="%.4f", step=0.0001)
m_sd_y = st.sidebar.number_input("Momento M_y,Sd (kNm)", value=0.2000, format="%.4f", step=0.0001)
v_sd = st.sidebar.number_input("Esforço Cortante V_Sd (kN)", value=3.0000, format="%.4f", step=0.0001)

st.sidebar.markdown("---")
st.sidebar.header("2. Geometria e Vãos")
fy_mpa = st.sidebar.number_input("Escoamento do Aço f_y (MPa)", value=250.0)
lx = st.sidebar.number_input("Comprimento Livre L_x (cm)", value=300.0)
ly = st.sidebar.number_input("Comprimento Livre L_y (cm)", value=150.0)
lt = st.sidebar.number_input("Comprimento de Torção L_t (cm)", value=150.0)

fy = fy_mpa / 10.0  
E = 20000.0         
G = 7700.0          
gama_m = 1.10

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

def avaliar_perfil(peca):
    area = get_val(peca, ["acm2", "acm"])
    peso = get_val(peca, ["mkg/m", "kg/m"])
    ix, iy = get_val(peca, ["ixcm4", "ix=iycm4"]), get_val(peca, ["iycm4", "ix=iycm4"])
    wx, wy = get_val(peca, ["wxcm3", "wx=wycm3"]), get_val(peca, ["wycm3", "wx=wycm3"])
    rx, ry = get_val(peca, ["rxcm", "rx=rycm"]), get_val(peca, ["rycm", "rx=rycm"])
    it, cw = get_val(peca, ["itcm4"]), get_val(peca, ["cwcm6"])
    h, t = get_val(peca, ["bwmm", "bfmm"]), get_val(peca, ["tnmm", "t=tnmm"])
    
    lambda_x, lambda_y, lambda_max = calc_esbeltez(rx, ry, lx, ly)
    nt_rd = calc_tracao(area, fy, gama_m)
    nc_rd, fe, lambda_0, fator_rho = calc_compressao_global(area, lambda_x, lambda_y, fy, E, gama_m)
    mx_rd, my_rd, m_cr_flt, m_pl_x, m_pl_y = calc_momentos_resistentes(wx, wy, iy, it, cw, lt, fy, E, G, gama_m)
    v_rd, h_t, tau_c, fase_cortante, lim1, lim2 = calc_cortante(h, t, fy, E, gama_m)
    
    taxas = calc_interacoes(n_sd_comp, n_sd_trac, m_sd_x, m_sd_y, v_sd, nt_rd, nc_rd, mx_rd, my_rd, v_rd, lambda_max)
    
    return {
        "Perfil": peca["Perfil"], "Peso (kg/m)": peso, "Eficiência Máxima (%)": taxas["Max_Global"] * 100,
        "Nc_Rd (kN)": nc_rd, "Mx_Rd (kNm)": mx_rd, "V_Rd (kN)": v_rd, "Nt_Rd (kN)": nt_rd, "My_Rd (kNm)": my_rd,
        "T_Esbeltez": taxas["T_Esbeltez"], "T_Tracao": taxas["T_Tracao"], "T_Compressao": taxas["T_Compressao"], 
        "T_Cortante": taxas["T_Cortante"], "T_FlexoComp": taxas["T_FlexoComp"], 
        "T_FlexoTrac": taxas["T_FlexoTrac"], "T_FlexoCort": taxas["T_FlexoCort"],
        "Aprovada": taxas["Max_Global"] <= 1.0,
        "h": h, "t": t, "area": area, "h_t": h_t, "tau_c": tau_c, "fase_cortante": fase_cortante,
        "lambda_x": lambda_x, "lambda_y": lambda_y, "lambda_max": lambda_max, "fe": fe, "lambda_0": lambda_0, "fator_rho": fator_rho,
        "m_cr_flt": m_cr_flt, "m_pl_x": m_pl_x, "m_pl_y": m_pl_y, "limite_1": lim1, "limite_2": lim2
    }

def render_status(nome, taxa):
    if taxa <= 1.0:
        return f"✅ **{nome}**: {taxa*100:.1f}% (Aprovado)"
    else:
        return f"❌ **{nome}**: {taxa*100:.1f}% (FALHOU)"

def aplicar_estilo(df):
    def cor_status(val):
        return 'background-color: #198754; color: white;' if val <= 100.0 else 'background-color: #dc3545; color: white;'
    df_reduzido = df[["Perfil", "Peso (kg/m)", "Eficiência Máxima (%)", "Nc_Rd (kN)", "Mx_Rd (kNm)", "V_Rd (kN)"]].round(2)
    if hasattr(df_reduzido.style, "map"):
        return df_reduzido.style.map(cor_status, subset=["Eficiência Máxima (%)"])
    return df_reduzido.style.applymap(cor_status, subset=["Eficiência Máxima (%)"])

# --- ABAS DA APLICAÇÃO ---
tab_manual, tab_auto, tab_memorial = st.tabs(["🛠️ Seleção Manual", "🚀 Auto-Dimensionamento", "📐 Memorial Detalhado"])

pecas_selecionadas_globais = []

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
        st.subheader("Painel Comparativo")
        st.dataframe(aplicar_estilo(df_resultados_manuais), use_container_width=True, column_config={"Eficiência Máxima (%)": st.column_config.NumberColumn("Uso Máximo (%)", format="%.1f%%")})

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

# ==========================================
# ABA 3: MEMORIAL COMPLETO AUDITÁVEL
# ==========================================
with tab_memorial:
    st.warning("⚠️ **Aviso:** A verificação das seções pelo método das larguras efetivas não foi implementada neste script. Os cálculos assumem que não há redução da área bruta por flambagem local.")
    
    if pecas_selecionadas_globais:
        perfil_memorial = st.selectbox("Selecione qual das peças você quer visualizar em detalhe:", options=df_resultados_manuais["Perfil"].tolist())
        res = df_resultados_manuais[df_resultados_manuais["Perfil"] == perfil_memorial].iloc[0]
        
        st.header(f"Laudo Crítico NBR 14762: {res['Perfil']}")
        st.info(f"**Geometria:** h = {res['h']:.2f} mm | t = {res['t']:.2f} mm | Área Bruta ($A_g$) = {res['area']:.2f} cm²")
        
        col_laudo1, col_laudo2 = st.columns(2)
        with col_laudo1:
            st.subheader("Verificações Automatizadas")
            st.markdown(render_status("Limitação de Esbeltez Geral", res["T_Esbeltez"]))
            st.markdown(render_status("Resistência à Tração Axial", res["T_Tracao"]))
            st.markdown(render_status("Resistência à Compressão Global", res["T_Compressao"]))
            st.markdown(render_status("Resistência ao Esforço Cortante", res["T_Cortante"]))
            st.markdown(render_status("Interação: Flexo-Compressão Biaxial", res["T_FlexoComp"]))
            st.markdown(render_status("Interação: Flexo-Tração Biaxial", res["T_FlexoTrac"]))
            st.markdown(render_status("Interação: Momento + Cortante", res["T_FlexoCort"]))
            
        with col_laudo2:
            st.subheader("Verificações Externas Requeridas (Avisos Informativos)")
            st.info("ℹ️ **Flambagem Local (Chapa):** Deve ser avaliada pelo projetista via Larguras Efetivas (MLE) ou Resistência Direta (MRD).")
            st.info("ℹ️ **Flambagem Distorcional:** Requer análise de estabilidade elástica do enrijecedor de borda (abas abertas/fechadas).")
            st.info("ℹ️ **Enrugamento da Alma (Web Crippling):** Verificar tensões nos apoios concentrados das terças/vigas.")
            st.info("ℹ️ **Flecha (Deflexão):** Coletar deslocamento máximo no Ftool e garantir que $\delta \le L/\text{limite}$.")

        st.markdown("---")
        st.subheader("Auditoria Matemática (Passo a Passo)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 1. Parâmetros da Flambagem Global")
            st.write(f"Índice de Esbeltez Real: $\lambda_{{max}} = {res['lambda_max']:.2f}$")
            st.write(f"Tensão Crítica de Euler ($f_e$): {res['fe']:.2f} kN/cm²")
            st.write(f"Esbeltez Reduzida ($\lambda_0$): {res['lambda_0']:.2f}")
            st.write(f"Fator de Redução Global ($\chi$): {res['fator_rho']:.3f}")
            st.latex(r"N_{c,Rd} = \frac{\chi \cdot A_g \cdot f_y}{\gamma_m}")
            st.latex(f"N_{{c,Rd}} = \\frac{{{res['fator_rho']:.3f} \\cdot {res['area']:.2f} \\cdot {fy:.1f}}}{{{gama_m}}} = {res['Nc_Rd (kN)']:.2f} \\text{{ kN}}")
            
            st.markdown("### 2. Estabilidade Lateral à Flexão (FLT)")
            st.latex(r"M_{x,Rd} = \frac{\min(M_{pl,x}, M_{cr})}{\gamma_m}")
            st.latex(f"M_{{x,Rd}} = {res['Mx_Rd (kNm)']:.2f} \\text{{ kNm}}")

        with col2:
            st.markdown("### 3. Esforço Cortante e Tensões na Alma")
            st.write(f"Esbeltez da alma ($h_w/t$): {res['h_t']:.2f}")
            st.write(f"Fase de Falha do Aço: **{res['fase_cortante']}**")
            st.latex(r"V_{Rd} = \frac{A_w \cdot \tau_c}{\gamma_m}")
            st.latex(f"V_{{Rd}} = {res['V_Rd (kN)']:.2f} \\text{{ kN}}")
            
            st.markdown("### 4. Formulações Interativas de Esforços Combinados")
            st.markdown("**Flexo-Compressão Biaxial:**")
            st.latex(r"\frac{N_{Sd}}{N_{c,Rd}} + \frac{M_{x,Sd}}{M_{x,Rd}} + \frac{M_{y,Sd}}{M_{y,Rd}} \le 1.0")
            st.latex(f"\\frac{{{n_sd_comp:.4f}}}{{{res['Nc_Rd (kN)']:.2f}}} + \\frac{{{m_sd_x:.4f}}}{{{res['Mx_Rd (kNm)']:.2f}}} + \\frac{{{m_sd_y:.4f}}}{{{res['My_Rd (kNm)']:.2f}}} = {res['T_FlexoComp']:.3f}")
            
            st.markdown("**Flexo-Tração Biaxial (Matemática Corrigida):**")
            st.latex(r"\frac{N_{t,Sd}}{N_{t,Rd}} + \frac{M_{x,Sd}}{M_{x,Rd}} + \frac{M_{y,Sd}}{M_{y,Rd}} \le 1.0")
            st.latex(f"\\frac{{{n_sd_trac:.4f}}}{{{res['Nt_Rd (kN)']:.2f}}} + \\frac{{{m_sd_x:.4f}}}{{{res['Mx_Rd (kNm)']:.2f}}} + \\frac{{{m_sd_y:.4f}}}{{{res['My_Rd (kNm)']:.2f}}} = {res['T_FlexoTrac']:.3f}")

    else:
        st.info("⚠️ Vá até a aba 'Seleção Manual', marque pelo menos um perfil e retorne aqui para carregar as contas.")

st.markdown("<br><hr><div style='text-align: center; color: gray;'>Criado por João Luiz<br>Email: joaoluiz@outlook.com</div>", unsafe_allow_html=True)