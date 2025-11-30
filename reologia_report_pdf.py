# -*- coding: utf-8 -*-
import os
import pandas as pd
from datetime import datetime
import math

try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    class FPDF: pass # Dummy class to avoid NameError in definition if not available

class PDFReport(FPDF):
    def __init__(self, title_str):
        super().__init__()
        self.title_str = title_str
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font('helvetica', 'B', 14)
        self.cell(0, 10, self.title_str, border=False, align='C', new_x="LMARGIN", new_y="NEXT")
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 5, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", border=False, align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', align='C')

    def section_title(self, label):
        self.set_font('helvetica', 'B', 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 8, label, border=0, fill=True, align='L', new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def chapter_body(self, text):
        self.set_font('helvetica', '', 10)
        self.multi_cell(0, 5, text)
        self.ln()

    def add_table(self, df, col_widths=None, max_char=None):
        """
        Adiciona uma tabela com suporte a quebra de linha (multiline).
        """
        self.set_font('helvetica', 'B', 9)
        line_height = 5 # Altura de uma linha de texto

        # Determine col widths
        if col_widths is None:
            page_width = self.w - 2 * self.l_margin
            col_widths = [page_width / len(df.columns)] * len(df.columns)

        def get_num_lines(text, width):
            if not text: return 1
            # Estimativa: largura do texto / (largura da coluna - margem)
            # Margem de segurança de 2mm
            text_width = self.get_string_width(text)
            return max(1, math.ceil(text_width / (width - 2)))

        def print_row(data, is_header=False):
            # 1. Calcula altura da linha (baseado na célula com mais linhas)
            max_lines = 1
            
            # Configura fonte para cálculo correto da largura
            if is_header: self.set_font('helvetica', 'B', 9)
            else: self.set_font('helvetica', '', 9)

            for i, item in enumerate(data):
                text = str(item)
                lines = get_num_lines(text, col_widths[i])
                if lines > max_lines: max_lines = lines
            
            row_height = max_lines * line_height

            # 2. Verifica quebra de página
            if self.get_y() + row_height > (self.h - 15):
                self.add_page()
                # Se for linha de dados, repete cabeçalho
                if not is_header:
                    print_row(df.columns, is_header=True)
                    # Restaura fonte normal
                    self.set_font('helvetica', '', 9)

            # 3. Imprime células
            x_start = self.get_x()
            y_start = self.get_y()
            
            for i, item in enumerate(data):
                text = str(item)
                w = col_widths[i]
                
                # Configura fonte
                if is_header: self.set_font('helvetica', 'B', 9)
                else: self.set_font('helvetica', '', 9)
                
                # Salva posição atual
                x_curr = self.get_x()
                y_curr = self.get_y()
                
                # Imprime texto com MultiCell
                # border=0 pois desenharemos o retângulo depois para garantir altura uniforme
                self.multi_cell(w, line_height, text, border=0, align='C')
                
                # Desenha borda da célula com a altura total da linha
                self.rect(x_curr, y_curr, w, row_height)
                
                # Move para a próxima coluna (volta para y_start)
                self.set_xy(x_curr + w, y_start)
            
            # 4. Move para a próxima linha
            self.set_xy(x_start, y_start + row_height)

        # Imprime Cabeçalho
        print_row(df.columns, is_header=True)

        # Imprime Dados
        self.set_font('helvetica', '', 9)
        for _, row in df.iterrows():
            print_row(row.values)
        
        self.ln(5)

    def add_image_centered(self, img_path, width=150):
        if os.path.exists(img_path):
            # Check space
            if self.get_y() + (width * 0.75) > (self.h - 20): # Approx aspect ratio
                self.add_page()
            
            self.image(img_path, w=width, x=(self.w - width)/2)
            self.ln(5)
        else:
            self.set_text_color(255, 0, 0)
            self.cell(0, 10, f"Imagem não encontrada: {os.path.basename(img_path)}", align='C', new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(0, 0, 0)

def gerar_analise_qualiquantitativa(best_model_nome, comportamento, df_sum_modelo, n_prime):
    """Gera um texto de análise baseado nos resultados."""
    texto = "ANÁLISE DOS RESULTADOS:\n\n"
    
    # 1. Ajuste de Modelos
    texto += f"O modelo reológico que melhor se ajustou aos dados experimentais foi o '{best_model_nome}'. "
    
    if df_sum_modelo is not None and not df_sum_modelo.empty:
        best_r2 = df_sum_modelo.iloc[0]['R2']
        if best_r2 > 0.99:
            texto += f"O ajuste apresentou excelente correlação (R² = {best_r2:.4f}), indicando alta confiabilidade na representação do comportamento do fluido.\n"
        elif best_r2 > 0.95:
            texto += f"O ajuste apresentou boa correlação (R² = {best_r2:.4f}).\n"
        else:
            texto += f"O ajuste apresentou correlação moderada/baixa (R² = {best_r2:.4f}), sugerindo dispersão nos dados ou comportamento complexo.\n"
            
    # 2. Comportamento do Fluido
    texto += f"\nComportamento Inferido: {comportamento}.\n"
    
    if "Pseudoplastico" in comportamento:
        texto += "Isso indica que a viscosidade do material diminui com o aumento da taxa de cisalhamento, característica comum em polímeros fundidos e suspensões concentradas. "
        if n_prime < 1:
            texto += f"O índice de comportamento de fluxo (n') calculado foi de {n_prime:.3f}, confirmando a pseudoplasticidade (n < 1).\n"
    elif "Dilatante" in comportamento:
        texto += "Isso indica que a viscosidade aumenta com a taxa de cisalhamento. "
        if n_prime > 1:
            texto += f"O índice de comportamento de fluxo (n') foi de {n_prime:.3f} (n > 1).\n"
    elif "Viscoplastico" in comportamento:
        texto += "O material apresenta uma tensão de escoamento (Yield Stress), ou seja, requer uma tensão mínima para iniciar o fluxo.\n"
    elif "Newtoniano" in comportamento:
        texto += "A viscosidade é constante independentemente da taxa de cisalhamento aplicada.\n"
        
    return texto

def get_graph_explanation(img_name):
    """Retorna uma explicação baseada no nome do arquivo do gráfico."""
    name = img_name.lower()
    if "curva_fluxo" in name:
        return "Figura 1: Curva de Fluxo. Este gráfico relaciona a Tensão de Cisalhamento (eixo Y) com a Taxa de Cisalhamento (eixo X). A inclinação e o formato da curva indicam o tipo de fluido (Newtoniano, Pseudoplástico, etc.). As linhas representam os modelos reológicos ajustados."
    elif "viscosidade" in name and "comparativo" not in name:
        return "Figura 2: Curva de Viscosidade. Mostra como a viscosidade real (eta) varia com a taxa de cisalhamento. Para fluidos pseudoplásticos, espera-se que a viscosidade diminua à medida que a taxa aumenta (Shear Thinning)."
    elif "n_prime" in name:
        return "Figura 3: Determinação de n'. Gráfico log-log da Tensão vs Taxa de Cisalhamento Aparente. A inclinação da reta (n') é usada na correção de Weissenberg-Rabinowitsch para obter a taxa de cisalhamento real na parede."
    elif "bagley" in name:
        return "Figura Extra: Correção de Bagley. Utilizada para determinar a perda de carga na entrada do capilar e corrigir a tensão de cisalhamento."
    elif "comparativo" in name:
        return "Figura Comparativa: Viscosidade Real vs Aparente. Ilustra a diferença entre os dados brutos (aparente) e os dados corrigidos (real) após as correções de Weissenberg e/ou Bagley."
    elif "pressao" in name:
        return "Figura Extra: Pressão vs Viscosidade. Relação direta entre a pressão aplicada e a viscosidade resultante (útil para controle de processo)."
    else:
        return f"Figura: {img_name}"

def gerar_pdf(timestamp_str, rho_g_cm3, tempo_extrusao_info,
              metodo_entrada, json_files, csv_path,
              realizar_bagley, D_bagley, L_bagley_list,
              realizar_mooney, L_mooney, D_mooney_list,
              D_unico, L_unico, calib_path,
              df_res, df_sum_modelo, best_model_nome, comportamento,
              lista_imgs, output_folder, fator_calibracao, stats_details=None, df_raw_data=None, df_outliers=None):
    
    if not PDF_AVAILABLE:
        print("AVISO: Biblioteca 'fpdf' não encontrada. Relatório PDF não será gerado.")
        return None

    pdf_filename = os.path.join(output_folder, f"{timestamp_str}_relatorio_analise.pdf")
    
    try:
        pdf = PDFReport("Relatório de Análise Reológica")
        pdf.add_page()

        # --- 1. Parâmetros Gerais ---
        pdf.section_title("1. Parâmetros Gerais e Identificação")
        
        info_text = f"Data da Análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        info_text += f"Densidade da Pasta: {rho_g_cm3:.3f} g/cm3\n"
        
        # if isinstance(tempo_extrusao_info, (float, int)):
        #     info_text += f"Tempo de Extrusão: {tempo_extrusao_info:.2f} s\n"
        # else:
        #     info_text += f"Tempo de Extrusão: {tempo_extrusao_info}\n"
            
        info_text += f"Método de Entrada: {metodo_entrada}\n"
        
        # Identificação dos Arquivos
        if metodo_entrada == "Arquivo(s) JSON" and json_files:
            info_text += "\nArquivos Fonte:\n"
            for jf in json_files:
                info_text += f"- {jf}\n"
        elif metodo_entrada == "Arquivo CSV":
            info_text += f"\nArquivo Fonte: {os.path.basename(csv_path)}\n"
            
        if fator_calibracao != 1.0:
            info_text += f"\nFator de Calibração Empírico: {fator_calibracao:.4f}\n"

        # Geometria
        info_text += "\nConfiguração Geométrica:\n"
        if realizar_bagley:
            info_text += f"- Correção de Bagley: SIM (D={D_bagley} mm, L={L_bagley_list} mm)\n"
        else:
            info_text += "- Correção de Bagley: NÃO\n"
            
        if realizar_mooney:
            info_text += f"- Correção de Mooney: SIM (L={L_mooney} mm, D={D_mooney_list} mm)\n"
        else:
            info_text += "- Correção de Mooney: NÃO\n"
            
        if not realizar_bagley and not realizar_mooney:
            info_text += f"- Capilar Único: D={D_unico} mm, L={L_unico} mm\n"
            if calib_path:
                info_text += f"- Calibração Externa: SIM ({os.path.basename(calib_path)})\n"

        pdf.chapter_body(info_text)

        # --- Se for Estatístico, adiciona detalhes ---
        if metodo_entrada == "Média Estatística":
            pdf.section_title("1.1. Detalhes do Tratamento Estatístico")
            # Cálculo do Coeficiente de Variação (CV) médio
            cv_visc_medio = 0.0
            if not df_res.empty and 'Viscosidade Real (Pa.s)' in df_res.columns and 'Desvio Padrao Viscosidade (Pa.s)' in df_res.columns:
                try:
                    # Filtra zeros para evitar divisão por zero
                    valid_cv = df_res['Viscosidade Real (Pa.s)'] > 0
                    if valid_cv.any():
                        cvs = (df_res.loc[valid_cv, 'Desvio Padrao Viscosidade (Pa.s)'] / df_res.loc[valid_cv, 'Viscosidade Real (Pa.s)']) * 100
                        cv_visc_medio = cvs.mean()
                except: pass

            stat_text = (
                "METODOLOGIA:\n"
                "Os resultados apresentados foram obtidos através do tratamento estatístico de múltiplos ensaios (réplicas). "
                "Os dados brutos de todos os arquivos selecionados foram agrupados por faixas de taxa de cisalhamento (escala logarítmica). "
                "Para cada faixa, foram calculadas a MÉDIA ARITMÉTICA e o DESVIO PADRÃO (sigma) das propriedades reológicas.\n\n"
                "INTERPRETAÇÃO DOS RESULTADOS:\n"
                "- Tensão/Viscosidade: Valores médios representativos da amostra.\n"
                "- Barras de Erro: Representam o desvio padrão (+/- 1 sigma), indicando a dispersão dos dados experimentais em torno da média.\n"
            )
            
            if cv_visc_medio > 0:
                stat_text += f"- Coeficiente de Variação (CV) Médio da Viscosidade: {cv_visc_medio:.2f}%\n"
                if cv_visc_medio < 5:
                    stat_text += "  -> Alta repetibilidade (CV < 5%). Os dados são consistentes e o processo de medição é estável.\n"
                elif cv_visc_medio < 10:
                    stat_text += "  -> Repetibilidade aceitável (5% < CV < 10%). Variação esperada para fluidos complexos.\n"
                else:
                    stat_text += "  -> Alta dispersão (CV > 10%). Sugere heterogeneidade da amostra, instabilidade no fluxo ou presença de efeitos de parede/deslizamento.\n"
            
            stat_text += "\nO ajuste dos modelos reológicos (Seção 2) foi realizado sobre a CURVA MÉDIA calculada."
            
            pdf.chapter_body(stat_text)
            
            # --- Tabela de Detalhamento dos Grupos (Solicitação do Usuário) ---
            if stats_details and 'df_cv' in stats_details:
                df_cv_source = stats_details['df_cv']
                if 'raw_values' in df_cv_source.columns:
                    pdf.chapter_body("Detalhamento dos Grupos (Valores Brutos de Tensão):")
                    
                    df_groups = pd.DataFrame({
                        'Taxa (s-1)': df_cv_source['gamma_dot_w_mean'],
                        'N': df_cv_source['num_points'],
                        'Valores Individuais (Pa)': df_cv_source['raw_values'],
                        'Media (Pa)': df_cv_source['tau_w_mean'],
                        'Desvio (Pa)': df_cv_source['tau_w_std'] if 'tau_w_std' in df_cv_source.columns else 0.0
                    })
                    
                    # Formata
                    for c in df_groups.columns:
                        if c != 'Valores Individuais (Pa)':
                            df_groups[c] = df_groups[c].apply(lambda x: f"{x:.4g}" if isinstance(x, (float, int)) else x)
                            
                    # Ajusta larguras: Valores Individuais precisa de mais espaço
                    # Page width ~190mm. 5 cols.
                    # Taxa: 25, N: 15, Valores: 90, Media: 30, Desvio: 30
                    col_widths = [25, 15, 90, 30, 30]
                    pdf.add_table(df_groups, col_widths=col_widths, max_char=80)
                    pdf.ln(2)
            
            # --- SEÇÃO DE ESTATÍSTICA APROFUNDADA (Se disponível) ---
            if stats_details:
                pdf.add_page()
                pdf.section_title("1.2. Relatório de Variação Estatística Aprofundada")
                
                # Métricas Globais
                metrics = stats_details.get('metrics', {})
                metrics_text = (
                    "--- RESUMO DAS MÉTRICAS GLOBAIS (Ponderado por Tensão) ---\n"
                    f"CV Médio Ponderado de Tensão (tau_w): {metrics.get('cv_tau_global', 0):.2f} %\n"
                    f"CV Médio Ponderado de Taxa (gamma_dot): {metrics.get('cv_gamma_global', 0):.2f} %\n"
                    f"CV Médio Ponderado de Viscosidade (eta): {metrics.get('cv_eta_global', 0):.2f} %\n"
                    f"CV Máximo de Tensão (Pior Ponto): {metrics.get('cv_tau_max', 0):.2f} %\n"
                    f"Pontos Analisados: {metrics.get('num_pontos', 0)}\n"
                )
                pdf.chapter_body(metrics_text)
                
                # Parecer Qualitativo
                pdf.section_title("1.3. Parecer Geral da Variação Estatística")
                parecer = stats_details.get('parecer', "")
                pdf.chapter_body(parecer)
                
                # Tabela Detalhada de CVs
                pdf.section_title("1.4. Tabela de Coeficiente de Variação (CV) por Ponto")
                df_cv = stats_details.get('df_cv', pd.DataFrame())
                if not df_cv.empty:
                    # Formata colunas
                    df_cv_print = df_cv.copy()
                    cols_map_cv = {
                        'tau_w_mean': 'Tensao Media (Pa)',
                        'cv_tau': 'CV Tensao (%)',
                        'gamma_dot_w_mean': 'Taxa Media (s-1)',
                        'cv_gamma': 'CV Taxa (%)',
                        'cv_eta': 'CV Visc (%)',
                        'tempo_mean': 'Tempo Medio (s)',
                        'massa_mean': 'Massa Media (g)'
                    }
                    df_cv_print.rename(columns=cols_map_cv, inplace=True)
                    
                    # Adiciona coluna Item
                    df_cv_print.insert(0, 'Item', range(1, len(df_cv_print) + 1))
                    
                    # Seleciona e ordena colunas
                    cols_order = ['Item', 'Tensao Media (Pa)', 'CV Tensao (%)', 'Taxa Media (s-1)', 'CV Taxa (%)', 'CV Visc (%)', 'Tempo Medio (s)', 'Massa Media (g)']
                    cols_final_cv = [c for c in cols_order if c in df_cv_print.columns]
                    
                    for c in cols_final_cv:
                        if c != 'Item':
                            df_cv_print[c] = df_cv_print[c].apply(lambda x: f"{x:.4g}" if isinstance(x, (float, int)) else x)
                        
                    pdf.add_table(df_cv_print[cols_final_cv])

            # --- 1.5 Pontos Descartados (Outliers) ---
            pdf.section_title("1.5. Pontos Descartados (Outliers)")
            if df_outliers is not None and not df_outliers.empty:
                pdf.chapter_body(f"Total de pontos removidos: {len(df_outliers)}")
                
                df_out_print = df_outliers.copy()
                # Seleciona colunas relevantes
                cols_out = ['gamma_dot_w', 'tau_w', 'eta_true', 'tempo_s', 'Limite Inf', 'Limite Sup']
                cols_out_map = {
                    'gamma_dot_w': 'Taxa (s-1)',
                    'tau_w': 'Tensao (Pa)',
                    'eta_true': 'Visc (Pa.s)',
                    'tempo_s': 'Tempo (s)',
                    'Limite Inf': 'Lim Inf (Pa)',
                    'Limite Sup': 'Lim Sup (Pa)'
                }
                
                # Filtra colunas existentes
                cols_to_use = [c for c in cols_out if c in df_out_print.columns]
                df_out_print = df_out_print[cols_to_use].rename(columns=cols_out_map)
                
                # Formata
                for c in df_out_print.columns:
                    df_out_print[c] = df_out_print[c].apply(lambda x: f"{x:.4g}" if isinstance(x, (float, int)) else x)
                    
                pdf.add_table(df_out_print)
            else:
                pdf.chapter_body("Nenhum outlier foi detectado ou removido nesta análise.")

        if df_sum_modelo is not None and not df_sum_modelo.empty:
            pdf.chapter_body("Resumo dos Ajustes dos Modelos:")
            df_mod = df_sum_modelo.copy()
            df_mod['R2'] = df_mod['R2'].apply(lambda x: f"{x:.4f}")
            pdf.add_table(df_mod)
            pdf.ln(2)

        # Texto de Análise
        n_val = 1.0
        if df_sum_modelo is not None:
            row_pl = df_sum_modelo[df_sum_modelo['Modelo'] == 'Lei de Potencia']
            if not row_pl.empty:
                try:
                    params_str = row_pl.iloc[0]['Parametros']
                    parts = params_str.split(',')
                    for p in parts:
                        if 'n=' in p:
                            n_val = float(p.split('=')[1])
                except: pass

        analise_texto = gerar_analise_qualiquantitativa(best_model_nome, comportamento, df_sum_modelo, n_val)
        pdf.chapter_body(analise_texto)

        # --- 3. Gráficos ---
        pdf.add_page()
        pdf.section_title("3. Gráficos Gerados")
        
        imgs_sorted = sorted(lista_imgs)
        order_keywords = ['fluxo', 'viscosidade', 'n_prime', 'pressao', 'comparativo']
        ordered_imgs = []
        for kw in order_keywords:
            for img in imgs_sorted:
                if kw in img and img not in ordered_imgs:
                    ordered_imgs.append(img)
        for img in imgs_sorted:
            if img not in ordered_imgs: ordered_imgs.append(img)
            
        for img_name in ordered_imgs:
            if img_name.lower().endswith('.png'):
                full_path = os.path.join(output_folder, img_name)
                
                # Adiciona explicação
                explanation = get_graph_explanation(img_name)
                pdf.set_font('helvetica', 'B', 10)
                pdf.multi_cell(0, 5, explanation)
                pdf.ln(2)
                
                pdf.add_image_centered(full_path, width=140)
                pdf.ln(5)

        # --- 4. Dados Detalhados (No final) ---
        pdf.add_page()
        pdf.section_title("4. Dados Reológicos Processados (Completo)")
        
        if not df_res.empty:
            cols_map = {
                'Taxa de Cisalhamento Corrigida (s-1)': 'Taxa Corr (s-1)',
                'Tensao de Cisalhamento (Pa)': 'Tensao (Pa)',
                'Viscosidade Real (Pa.s)': 'Visc Real (Pa.s)',
                'Desvio Padrao Tensao (Pa)': 'Std Tensao',
                'Desvio Padrao Viscosidade (Pa.s)': 'Std Visc'
            }
            
            df_print = df_res.copy()
            new_cols = []
            for c in df_print.columns:
                found = False
                for k, v in cols_map.items():
                    if k in c:
                        new_cols.append(v)
                        found = True
                        break
                if not found: new_cols.append(c)
            
            df_print.columns = new_cols
            
            # Define colunas de interesse (incluindo estatísticas se existirem)
            possible_cols = ['Taxa (s-1)', 'Tensao (Pa)', 'Std Tensao', 'Visc. (Pa.s)', 'Std Visc']
            cols_final = [c for c in possible_cols if c in df_print.columns]
            
            if not cols_final: cols_final = df_print.columns[:5] # Fallback
            
            for c in cols_final:
                df_print[c] = df_print[c].apply(lambda x: f"{x:.4g}" if isinstance(x, (float, int)) else x)
                
            pdf.add_table(df_print[cols_final])

        # --- 5. Dados Brutos (Opcional) ---
        if df_raw_data is not None and not df_raw_data.empty:
            pdf.add_page()
            pdf.section_title("5. Dados Brutos Consolidados")
            
            # Prepara dados brutos para impressão
            df_raw_print = df_raw_data.copy()
            
            # Seleciona colunas relevantes para não estourar a largura
            cols_raw_map = {
                'gamma_dot_w': 'Taxa (s-1)',
                'tau_w': 'Tensao (Pa)',
                'eta_true': 'Visc (Pa.s)',
                'tempo_s': 'Tempo (s)',
                'massa_g': 'Massa (g)',
                'pressao': 'Pressao (bar)'
            }
            
            # Renomeia e filtra
            new_cols_raw = []
            for c in df_raw_print.columns:
                if c in cols_raw_map:
                    new_cols_raw.append(cols_raw_map[c])
                else:
                    # Mantém outras se quiser, ou ignora
                    pass
            
            df_raw_print.rename(columns=cols_raw_map, inplace=True)
            
            # Adiciona coluna Item
            df_raw_print.insert(0, 'Item', range(1, len(df_raw_print) + 1))
            
            cols_to_show = ['Item'] + [c for c in cols_raw_map.values() if c in df_raw_print.columns]
            
            # Formata
            for c in cols_to_show:
                df_raw_print[c] = df_raw_print[c].apply(lambda x: f"{x:.4g}" if isinstance(x, (float, int)) else x)
                
            pdf.add_table(df_raw_print[cols_to_show])

        pdf.output(pdf_filename)
        print(f"Relatório PDF gerado com sucesso: {pdf_filename}")
        return pdf_filename

    except Exception as e:
        print(f"ERRO ao gerar PDF: {e}")
        return None

def gerar_pdf_comparativo(output_folder, timestamp_str, dados_analises, lista_imgs, df_mape=None):
    """
    Gera um relatório PDF para análise comparativa.
    """
    if not PDF_AVAILABLE:
        print("AVISO: Biblioteca 'fpdf' não encontrada. Relatório PDF não será gerado.")
        return None

    pdf_filename = os.path.join(output_folder, f"{timestamp_str}_relatorio_comparativo.pdf")
    
    try:
        pdf = PDFReport("Relatório Comparativo de Análises")
        pdf.add_page()

        # --- 1. Identificação ---
        pdf.section_title("1. Identificação da Comparação")
        info_text = f"Data da Comparação: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        info_text += f"Total de Análises Comparadas: {len(dados_analises)}\n\n"
        info_text += "Análises Incluídas:\n"
        for nome in dados_analises.keys():
            info_text += f"- {nome}\n"
        pdf.chapter_body(info_text)

        # --- 2. Análise de Erro (MAPE) ---
        if df_mape is not None and not df_mape.empty:
            pdf.section_title("2. Análise de Discrepância (MAPE)")
            pdf.chapter_body("Tabela de Erro Percentual Absoluto Médio (MAPE) em relação à referência:")
            
            # Formata tabela
            df_print = df_mape.copy()
            if 'MAPE (%)' in df_print.columns:
                df_print['MAPE (%)'] = df_print['MAPE (%)'].apply(lambda x: f"{x:.2f}%" if isinstance(x, (float, int)) else x)
            
            pdf.add_table(df_print)
            pdf.ln(2)

        # --- 3. Gráficos Comparativos ---
        pdf.add_page()
        pdf.section_title("3. Gráficos Comparativos")
        
        # Ordena imagens
        imgs_sorted = sorted(lista_imgs)
        order_keywords = ['fluxo', 'viscosidade', 'n_prime', 'pressao']
        ordered_imgs = []
        for kw in order_keywords:
            for img in imgs_sorted:
                if kw in img and img not in ordered_imgs:
                    ordered_imgs.append(img)
        for img in imgs_sorted:
            if img not in ordered_imgs: ordered_imgs.append(img)
            
        for img_name in ordered_imgs:
            if img_name.lower().endswith('.png'):
                full_path = os.path.join(output_folder, img_name)
                
                # Explicação
                explanation = get_graph_explanation(img_name)
                pdf.set_font('helvetica', 'B', 10)
                pdf.multi_cell(0, 5, explanation)
                pdf.ln(2)
                
                pdf.add_image_centered(full_path, width=150)
                pdf.ln(5)

        pdf.output(pdf_filename)
        print(f"Relatório Comparativo PDF gerado: {pdf_filename}")
        return pdf_filename

    except Exception as e:
        print(f"ERRO ao gerar PDF Comparativo: {e}")
        return None
