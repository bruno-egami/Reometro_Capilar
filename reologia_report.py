# -*- coding: utf-8 -*-
import os
import pandas as pd
import utils_reologia

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
    filename = os.path.join(output_folder, f"{timestamp_str_report}_relatorio_analise.txt")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write(f"RELATÓRIO DE ANÁLISE REOLÓGICA - {timestamp_str_report}\n")
            f.write("="*70 + "\n\n")
            
            f.write("--- PARÂMETROS GERAIS ---\n")
            f.write(f"Densidade da Pasta: {rho_g_cm3:.3f} g/cm³\n")
            
            # Formatação inteligente do tempo
            if isinstance(tempo_extrusao_info, (float, int)):
                f.write(f"Tempo de Extrusão (Fixo): {tempo_extrusao_info:.2f} s\n")
            else:
                f.write(f"Tempo de Extrusão: {tempo_extrusao_info}\n")
                
            f.write(f"Método de Entrada: {metodo_entrada_rel}\n")
            if fator_calibracao != 1.0:
                f.write(f"Fator de Calibração Empírico Aplicado: {fator_calibracao:.4f}\n")
            
            f.write("\n--- ORIGEM DOS DADOS ---\n")
            if metodo_entrada_rel == "Arquivo(s) JSON":
                f.write("Arquivos JSON utilizados:\n")
                for jf in json_files_usados_rel:
                    f.write(f"  - {jf}\n")
            elif metodo_entrada_rel == "Arquivo CSV":
                f.write(f"Arquivo CSV: {csv_path_rel}\n")
            
            f.write("\n--- CONFIGURAÇÃO GEOMÉTRICA E CORREÇÕES ---\n")
            if realizar_bagley:
                f.write(f"Correção de Bagley: SIM\n")
                f.write(f"  Diâmetro Comum: {D_bagley_comum} mm\n")
                f.write(f"  Comprimentos (L) usados: {L_bagley_lista} mm\n")
            else:
                f.write(f"Correção de Bagley: NÃO\n")
            
            if realizar_mooney:
                f.write(f"Correção de Mooney: SIM\n")
                f.write(f"  Comprimento Comum: {L_mooney_comum} mm\n")
                f.write(f"  Diâmetros (D) usados: {D_mooney_lista} mm\n")
            else:
                f.write(f"Correção de Mooney: NÃO\n")
                
            if not realizar_bagley and not realizar_mooney:
                f.write("Análise de Capilar Único (Sem correções geométricas)\n")
                f.write(f"  Diâmetro (D): {D_unico} mm\n")
                f.write(f"  Comprimento (L): {L_unico} mm\n")
                if caminho_calibracao_usada:
                     f.write(f"  Calibração Externa Aplicada: SIM\n")
                     f.write(f"  Arquivo: {os.path.basename(caminho_calibracao_usada)}\n")
                else:
                     f.write(f"  Calibração Externa Aplicada: NÃO\n")

            f.write("\n--- DADOS REOLÓGICOS PROCESSADOS (Amostra) ---\n")
            if not df_res.empty:
                # Formata colunas float para string bonita
                df_print = df_res.copy()
                for col in df_print.columns:
                    if df_print[col].dtype == float:
                        df_print[col] = df_print[col].apply(lambda x: utils_reologia.format_float_for_table(x))
                f.write(df_print.to_string(index=False))
            else:
                f.write("Nenhum dado processado disponível.\n")
            
            if best_model_nome and df_sum_modelo is not None and not df_sum_modelo.empty:
                f.write("\n\n--- MELHOR MODELO REOLÓGICO AJUSTADO ---\n")
                f.write(df_sum_modelo.to_string(index=False) + "\n")
                f.write(f"\nComportamento do Fluido Inferido: {comportamento_fluido_relatorio}\n")
            else:
                f.write("\n\nNenhum modelo foi ajustado ou selecionado como o melhor.\n")

            f.write("\n--- ARQUIVOS GERADOS NESTA SESSÃO ---\n")
            if not lista_arquivos_gerados:
                f.write("Nenhum arquivo adicional foi gerado.\n")
            else:
                for arq in sorted(lista_arquivos_gerados):
                    f.write(f"- {arq}\n")

            f.write("\n" + "="*70 + "\nFIM DO RELATÓRIO\n" + "="*70 + "\n")
        print(f"\nRelatório de texto salvo em: {filename}")
    except Exception as e: print(f"ERRO ao gerar relatório de texto: {e}")
