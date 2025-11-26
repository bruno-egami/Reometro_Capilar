# -*- coding: utf-8 -*-
import os
import pandas as pd
import utils_reologia
from datetime import datetime

def gerar_relatorio_texto(timestamp_str_report, rho_g_cm3, tempo_extrusao_info,
                          metodo_entrada_rel, json_files_usados_rel, csv_path_rel,
                          realizar_bagley, D_bagley_comum, L_bagley_lista,
                          realizar_mooney, L_mooney_comum, D_mooney_lista,
                          D_unico, L_unico,
                          caminho_calibracao_usada,
                          df_res, df_sum_modelo, best_model_nome,
                          comportamento_fluido_relatorio,
                          lista_arquivos_gerados, output_folder, fator_calibracao):
    """
    Gera um relatório de texto completo (.txt) com o resumo de toda a análise.
    """
    filepath = os.path.join(output_folder, f"{timestamp_str_report}_relatorio_analise.txt")
    
    conteudo_list = []
    conteudo_list.append("="*70 + "\n")
    conteudo_list.append(f"RELATÓRIO DE ANÁLISE REOLÓGICA - {timestamp_str_report}\n")
    conteudo_list.append("="*70 + "\n\n")
    
    conteudo_list.append("--- PARÂMETROS GERAIS ---\n")
    conteudo_list.append(f"Densidade da Pasta: {rho_g_cm3:.3f} g/cm³\n")
    
    # Formatação inteligente do tempo
    if isinstance(tempo_extrusao_info, (float, int)):
        conteudo_list.append(f"Tempo de Extrusão (Fixo): {tempo_extrusao_info:.2f} s\n")
    else:
        conteudo_list.append(f"Tempo de Extrusão: {tempo_extrusao_info}\n")
        
    conteudo_list.append(f"Método de Entrada: {metodo_entrada_rel}\n")
    if fator_calibracao != 1.0:
        conteudo_list.append(f"Fator de Calibração Empírico Aplicado: {fator_calibracao:.4f}\n")
    
    conteudo_list.append("\n--- ORIGEM DOS DADOS ---\n")
    if metodo_entrada_rel == "Arquivo(s) JSON":
        conteudo_list.append("Arquivos JSON utilizados:\n")
        for jf in json_files_usados_rel:
            conteudo_list.append(f"  - {jf}\n")
    elif metodo_entrada_rel == "Arquivo CSV":
        conteudo_list.append(f"Arquivo CSV: {csv_path_rel}\n")
    
    conteudo_list.append("\n--- CONFIGURAÇÃO GEOMÉTRICA E CORREÇÕES ---\n")
    if realizar_bagley:
        conteudo_list.append(f"Correção de Bagley: SIM\n")
        conteudo_list.append(f"  Diâmetro Comum: {D_bagley_comum} mm\n")
        conteudo_list.append(f"  Comprimentos (L) usados: {L_bagley_lista} mm\n")
    else:
        conteudo_list.append(f"Correção de Bagley: NÃO\n")
    
    if realizar_mooney:
        conteudo_list.append(f"Correção de Mooney: SIM\n")
        conteudo_list.append(f"  Comprimento Comum: {L_mooney_comum} mm\n")
        conteudo_list.append(f"  Diâmetros (D) usados: {D_mooney_lista} mm\n")
    else:
        conteudo_list.append(f"Correção de Mooney: NÃO\n")
        
    if not realizar_bagley and not realizar_mooney:
        conteudo_list.append("Análise de Capilar Único (Sem correções geométricas)\n")
        conteudo_list.append(f"  Diâmetro (D): {D_unico} mm\n")
        conteudo_list.append(f"  Comprimento (L): {L_unico} mm\n")
        if caminho_calibracao_usada:
             conteudo_list.append(f"  Calibração Externa Aplicada: SIM\n")
             conteudo_list.append(f"  Arquivo: {os.path.basename(caminho_calibracao_usada)}\n")
        else:
             conteudo_list.append(f"  Calibração Externa Aplicada: NÃO\n")

    conteudo_list.append("\n--- DADOS REOLÓGICOS PROCESSADOS (Amostra) ---\n")
    if not df_res.empty:
        # Formata colunas float para string bonita
        df_print = df_res.copy()
        for col in df_print.columns:
            if df_print[col].dtype == float:
                df_print[col] = df_print[col].apply(lambda x: utils_reologia.format_float_for_table(x))
        conteudo_list.append(df_print.to_string(index=False))
    else:
        conteudo_list.append("Nenhum dado processado disponível.\n")
    
    if best_model_nome and df_sum_modelo is not None and not df_sum_modelo.empty:
        conteudo_list.append("\n\n--- MELHOR MODELO REOLÓGICO AJUSTADO ---\n")
        conteudo_list.append(df_sum_modelo.to_string(index=False) + "\n")
        conteudo_list.append(f"\nComportamento do Fluido Inferido: {comportamento_fluido_relatorio}\n")
    else:
        conteudo_list.append("\n\nNenhum modelo foi ajustado ou selecionado como o melhor.\n")

    conteudo_list.append("\n--- ARQUIVOS GERADOS NESTA SESSÃO ---\n")
    if not lista_arquivos_gerados:
        conteudo_list.append("Nenhum arquivo adicional foi gerado.\n")
    else:
        for arq in sorted(lista_arquivos_gerados):
            conteudo_list.append(f"- {arq}\n")

    conteudo_list.append("\n" + "="*70 + "\nFIM DO RELATÓRIO\n" + "="*70 + "\n")
    
    conteudo = "".join(conteudo_list)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        print(f"\nRelatório de texto salvo em: {filepath}")
        return filepath
    except Exception as e:
        print(f"ERRO ao gerar relatório de texto: {e}")
        return None

def gerar_relatorio_estatistico(df_metricas, metricas_resumo, parecer_texto, output_folder, timestamp_str):
    """
    Gera relatório de análise estatística.
    """
    filepath = os.path.join(output_folder, f"{timestamp_str}_relatorio_estatistico.txt")
    
    conteudo = f"""======================================================================
--- RELATÓRIO DE ANÁLISE ESTATÍSTICA REOLÓGICA ---
Data/Hora: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
======================================================================

--- MÉTRICAS GERAIS (Média dos CVs) ---
CV Médio (Tensão): {metricas_resumo.get('cv_medio_tau', 0):.2f}%
CV Médio (Viscosidade): {metricas_resumo.get('cv_medio_eta', 0):.2f}%
CV Máximo (Tensão): {metricas_resumo.get('cv_max_tau', 0):.2f}%

--- PARECER QUALITATIVO ---
{parecer_texto}

--- DETALHAMENTO POR PONTO ---
{df_metricas.to_string()}
"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        return filepath
    except Exception: return None

def gerar_relatorio_comparativo(dados_analises, output_folder, timestamp_str):
    """
    Gera relatório simples listando as análises comparadas.
    """
    filepath = os.path.join(output_folder, f"{timestamp_str}_relatorio_comparativo.txt")
    
    conteudo = f"""======================================================================
--- RELATÓRIO COMPARATIVO DE ANÁLISES ---
Data/Hora: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
======================================================================

Análises Comparadas:
"""
    for nome, df in dados_analises.items():
        conteudo += f"- {nome}: {len(df)} pontos\n"
        
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        return filepath
    except Exception: return None
