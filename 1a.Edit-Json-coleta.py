# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# SCRIPT 1a.EDIT-JSON-COLETA.PY
# Ferramenta para visualizar, excluir pontos, reordenar, limpar massas 0g
# e UNIR JSONs semelhantes.
# -----------------------------------------------------------------------------

import os
import glob
import json
import pandas as pd
import re # Importado para expressões regulares
from datetime import datetime

# --- CONFIGURAÇÃO DE PASTAS ---
JSON_INPUT_DIR = "resultados_testes_reometro"

# --- FUNÇÕES AUXILIARES ---

def buscar_arquivos_json(pasta_json):
    """
    Busca todos os arquivos .json na pasta que são arquivos de "origem".
    IGNORA arquivos já unidos (que terminam com _YYYY-MM-DD.json).
    """
    if not os.path.exists(pasta_json):
        print(f"AVISO: A pasta '{pasta_json}' não existe.")
        return []
    
    # Regex para identificar arquivos já unidos (ex: ..._2025-10-29.json)
    merged_file_pattern = re.compile(r'_\d{4}-\d{2}-\d{2}\.json$')
    
    # Busca por arquivos JSON que sejam arquivos de origem
    # E que estejam na pasta raiz (ignora subpastas)
    arquivos = sorted([
        os.path.join(pasta_json, f) 
        for f in os.listdir(pasta_json) 
        if f.endswith('.json') and \
           not merged_file_pattern.search(f) and \
           os.path.isfile(os.path.join(pasta_json, f))
    ])
    return arquivos

def listar_arquivos_json_numerados(pasta_json):
# ... (código existente inalterado) ...
    """Lista todos os arquivos .json em uma pasta para que o usuário possa escolher pelo número."""
    arquivos_paths = buscar_arquivos_json(pasta_json)
    arquivos_nomes = [os.path.basename(p) for p in arquivos_paths]
    
    if not arquivos_nomes:
        print(f"Nenhum arquivo .json de origem encontrado na pasta '{pasta_json}'.")
        return [], []
    else:
        print(f"\nArquivos JSON de origem disponíveis em '{pasta_json}':")
        for i, arq in enumerate(arquivos_nomes):
            print(f"  {i+1}: {arq}")
    return arquivos_nomes, arquivos_paths # Retorna nomes e caminhos completos

def selecionar_arquivo_json(pasta_json):
# ... (código existente inalterado) ...
    """Gerencia o menu para o usuário escolher um arquivo JSON da lista."""
    arquivos_nomes, arquivos_paths = listar_arquivos_json_numerados(pasta_json)
    if not arquivos_nomes:
        return None 
    while True:
        try:
            escolha_str = input("\nEscolha o NÚMERO do arquivo JSON a ser editado (ou '0' para sair): ").strip()
            if escolha_str == '0':
                return None
            
            escolha_num = int(escolha_str)
            if 1 <= escolha_num <= len(arquivos_nomes):
                return arquivos_paths[escolha_num - 1] # Retorna o caminho completo
            else:
                print(f"ERRO: Escolha inválida. Digite um número entre 1 e {len(arquivos_nomes)}, ou '0'.")
        except ValueError:
            print("ERRO: Entrada inválida. Por favor, digite um número ou '0'.")
        except Exception as e:
            print(f"Ocorreu um erro inesperado na seleção: {e}")
            return None

# --- NOVAS FUNÇÕES (OPÇÃO 3) ---

def extrair_percentual(nome_arquivo):
# ... (código existente inalterado) ...
    """Extrai o primeiro valor de percentual (ex: 40%, 37.5%) do nome do arquivo."""
    # Procura por um ou mais dígitos, opcionalmente um ponto e mais dígitos, seguido por '%'
    match = re.search(r'(\d+(\.\d+)?%)', nome_arquivo)
    return match.group(0) if match else None

def extrair_criterios(caminho_arquivo):
# ... (código existente inalterado) ...
    """
    Extrai os critérios de união de um arquivo JSON.
    Pressupõe que os metadados estão em data['metadata']['capilar'] e data['metadata']['densidade_g_cm3']
    """
    nome_arquivo = os.path.basename(caminho_arquivo)
    percentual = extrair_percentual(nome_arquivo)
    
    if not percentual:
# ... (código existente inalterado) ...
        print(f"AVISO: Não foi possível extrair o percentual (%) do nome do arquivo: {nome_arquivo}. Pulando.")
        return None, None, None, None

    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # --- AJUSTE FEITO COM BASE NO JSON DE EXEMPLO ---
        # Os dados de capilar e densidade estão na raiz do JSON
        
        # Cria um dicionário com as informações do capilar
        capilar_info = {
            "diametro_mm": data.get('diametro_capilar_mm', 0.0),
            "comprimento_mm": data.get('comprimento_capilar_mm', 0.0)
        }
        
        # Pega a informação de densidade
        densidade_info = data.get('densidade_pasta_g_cm3', 0.0)
        # --- FIM DA ÁREA DE AJUSTE ---

        # Converte o dicionário do capilar em uma string "hasheável" para usar como chave
        capilar_key = json.dumps(capilar_info, sort_keys=True)
        
        return percentual, capilar_key, densidade_info, data

    except json.JSONDecodeError:
# ... (código existente inalterado) ...
        print(f"ERRO: Falha ao decodificar o arquivo {nome_arquivo}. Pulando.")
        return None, None, None, None
    except Exception as e:
# ... (código existente inalterado) ...
        print(f"ERRO ao ler {nome_arquivo}: {e}. Pulando.")
        return None, None, None, None

def processar_uniao_arquivos():
# ... (código existente inalterado) ...
    """
    NOVA FUNÇÃO: Analisa, agrupa e une arquivos JSON semelhantes.
    """
    print("\n--- Iniciando União Automática de Arquivos ---")
    arquivos_json = buscar_arquivos_json(JSON_INPUT_DIR)
    
    if not arquivos_json:
# ... (código existente inalterado) ...
        print(f"Nenhum arquivo .json de origem encontrado em '{JSON_INPUT_DIR}'.")
        return

    grupos_para_unir = {} # Chave: (percentual, capilar_key, densidade), Valor: [lista de caminhos]
    dados_arquivos = {}   # Chave: caminho, Valor: dados do json (para evitar releitura)

    # 1. Agrupar arquivos
    print("Analisando e agrupando arquivos por critérios...")
    for caminho_arquivo in arquivos_json:
# ... (código existente inalterado) ...
        percentual, capilar_key, densidade, data = extrair_criterios(caminho_arquivo)
        
        if not percentual:
            continue
            
        grupo_key = (percentual, capilar_key, densidade)
        
        if grupo_key not in grupos_para_unir:
            grupos_para_unir[grupo_key] = []
            
        grupos_para_unir[grupo_key].append(caminho_arquivo)
        dados_arquivos[caminho_arquivo] = data

    # 2. Filtrar grupos que realmente precisam de união (mais de 1 arquivo)
    grupos_validos = {k: v for k, v in grupos_para_unir.items() if len(v) > 1}

    # 3. Relatório e Confirmação
    if not grupos_validos:
# ... (código existente inalterado) ...
        print("\nNenhum grupo de arquivos com critérios idênticos (e mais de 1 arquivo) foi encontrado para unir.")
        return

    print("\n" + "="*70)
    print("RELATÓRIO DE UNIÃO DE ARQUIVOS")
# ... (código existente inalterado) ...
    print("="*70)
    print("Os seguintes grupos de arquivos foram encontrados e podem ser unidos:")

    for i, (grupo_key, arquivos_do_grupo) in enumerate(grupos_validos.items()):
# ... (código existente inalterado) ...
        percentual, capilar_key, densidade = grupo_key
        print(f"\n--- GRUPO {i+1} ---")
        print(f"  Critérios de União:")
        print(f"    - Formulação (Nome): {percentual}")
        print(f"    - Densidade (Meta):  {densidade}")
        try:
            # Tenta decodificar o JSON do capilar para exibição amigável
            capilar_info_str = json.dumps(json.loads(capilar_key))
        except:
            capilar_info_str = capilar_key
        print(f"    - Capilar (Meta):    {capilar_info_str}")
        print(f"  Arquivos a serem unidos:")
        for caminho_arquivo in arquivos_do_grupo:
            print(f"    - {os.path.basename(caminho_arquivo)}")

    print("="*70)

    while True:
# ... (código existente inalterado) ...
        confirm = input("\nDeseja continuar e UNIR os grupos listados acima? (s/n): ").strip().lower()
        if confirm == 's':
            break
        if confirm == 'n':
            print("\nOperação de união cancelada pelo usuário.")
            return

    # 4. Executar União e Limpeza
    print("\nIniciando união, limpeza e renumeração...")
    
    for grupo_key, arquivos_do_grupo in grupos_validos.items():
        
        # --- AJUSTE SOLICITADO ---
# ... (código existente inalterado) ...
        # Extrai todos os critérios da chave para exibição
        percentual = grupo_key[0]
        capilar_key = grupo_key[1]
        densidade = grupo_key[2]
        
        # Formatar o capilar_key e extrair dados para sugestão
# ... (código existente inalterado) ...
        capilar_info_str = ""
        diametro_str = ""
        compr_str = ""
        capilar_info = {} # Armazena o dict do capilar
        try:
            # Carrega a string JSON da chave
            capilar_info = json.loads(capilar_key) 
            # Formata como string para exibição
            capilar_info_str = json.dumps(capilar_info) 
            
            # Tenta formatar '3.0' para '3' e '1.5' para '1p5'
            diametro = capilar_info.get('diametro_mm', 'D')
            compr = capilar_info.get('comprimento_mm', 'C')
            
            # --- ALTERAÇÃO AQUI ---
            # Remove '.0' se for inteiro, mantém o float como está (ex: 1.5)
            diametro_str = f"{diametro:.0f}" if diametro == int(diametro) else f"{diametro:.1f}"
            compr_str = f"{compr:.0f}" if compr == int(compr) else f"{compr:.1f}"
            # --- FIM DA ALTERAÇÃO ---
            
        except:
            # Fallback se a chave não for um JSON válido (não deve acontecer)
            capilar_info_str = capilar_key
            
        print(f"\nProcessando Grupo...")
        print(f"  - Formulação: {percentual}")
        print(f"  - Capilar:    {capilar_info_str}")
        print(f"  - Densidade:  {densidade}")
        # --- FIM DO AJUSTE ---

        # --- ALTERAÇÃO AQUI ---
        # 4a. Gerar nome do arquivo de saída automaticamente
        pct_str = percentual # Mantém o '%' original
        data_hoje_str = datetime.now().strftime('%Y-%m-%d')
        
        # Formato: 40%1.5x43mm_2025-10-29.json
        nome_saida = f"{pct_str}{diametro_str}x{compr_str}mm_{data_hoje_str}.json"
        # --- FIM DA ALTERAÇÃO ---
        
        print(f"  -> Nome do arquivo de saída gerado: {nome_saida}")
        
        caminho_saida = os.path.join(JSON_INPUT_DIR, nome_saida)
        
        if os.path.exists(caminho_saida):
# ... (código existente inalterado) ...
            print(f"  AVISO: O arquivo '{nome_saida}' já existe. Ele será sobrescrito.")
            
        testes_unidos = []
        novo_json_data = {}
        primeiro_arquivo = True

        # --- NOVOS CONTADORES PARA O RELATÓRIO ---
        total_pontos_brutos = 0
        total_pontos_massa_zero_removidos = 0
        
        # --- NOVO RELATÓRIO PARA EMBUTIR ---
        relatorio_uniao = {
            "arquivos_unidos": [os.path.basename(p) for p in arquivos_do_grupo],
            "criterios_uniao": {
                "percentual": percentual,
                "capilar": capilar_info, # Usa o dict decodificado
                "densidade": densidade
            },
            "data_uniao": datetime.now().isoformat()
        }
        # --- FIM NOVO RELATÓRIO ---

        # 4b. Coletar todos os 'testes'
        for caminho_arquivo in arquivos_do_grupo:
# ... (código existente inalterado) ...
            data = dados_arquivos[caminho_arquivo]
            
            # Pega os metadados e cabeçalho do *primeiro* arquivo do grupo
            if primeiro_arquivo:
                novo_json_data = {k: v for k, v in data.items() if k != 'testes'}
                primeiro_arquivo = False
            
            testes = data.get("testes", [])
            total_pontos_brutos += len(testes) # Contagem
            
            # Limpeza de Massa 0g (Sua solicitação 3)
            testes_limpos_massa = [t for t in testes if t.get('massa_g_registrada', 0.0) != 0.0]
            
            # Contagem de removidos
            removidos_neste_arquivo = len(testes) - len(testes_limpos_massa)
            total_pontos_massa_zero_removidos += removidos_neste_arquivo
            
            testes_unidos.extend(testes_limpos_massa)

        # Total de pontos após a limpeza de massa 0g
        pontos_apos_limpeza_massa = len(testes_unidos)

        # 4c. Limpeza de Duplicados (Sua solicitação 4)
        testes_sem_duplicatas = []
        vistos = set()
# ... (código existente inalterado) ...
        # Define um "ponto duplicado" como tendo a mesma pressão, duração e massa.
        # Ajuste esta chave se a definição de duplicata for outra.
        for teste in testes_unidos:
            chave_teste = (
                teste.get('media_pressao_final_ponto_bar'), 
                teste.get('duracao_real_s'), 
                teste.get('massa_g_registrada')
            )
            
            if chave_teste not in vistos:
                testes_sem_duplicatas.append(teste)
                vistos.add(chave_teste)
        
        # Total de pontos após a limpeza de duplicatas
        pontos_apos_limpeza_duplicatas = len(testes_sem_duplicatas)
        total_pontos_duplicados_removidos = pontos_apos_limpeza_massa - pontos_apos_limpeza_duplicatas
            
        # Adiciona estatísticas ao relatório
        relatorio_uniao['estatisticas_limpeza'] = {
            'total_pontos_brutos': total_pontos_brutos,
            'pontos_massa_zero_removidos': total_pontos_massa_zero_removidos,
            'pontos_duplicados_removidos': total_pontos_duplicados_removidos,
            'total_pontos_finais': pontos_apos_limpeza_duplicatas
        }

        # 4d. Renumerar pontos
        for i, teste in enumerate(testes_sem_duplicatas):
# ... (código existente inalterado) ...
            teste['ponto_n'] = i + 1

        # 4e. Salvar arquivo final
        novo_json_data['testes'] = testes_sem_duplicatas
        novo_json_data['relatorio_uniao'] = relatorio_uniao # Adiciona o relatório ao JSON
        
        # Opcional: Atualizar a contagem de pontos no cabeçalho, se existir
# ... (código existente inalterado) ...
        # ATUALIZADO: com base no exemplo, não existe 'dados_cabecalho'
        # Vamos apenas garantir que 'testes' seja atualizado.
        # if 'dados_cabecalho' in novo_json_data and 'n_pontos_total' in novo_json_data.get('dados_cabecalho', {}):
        #    novo_json_data['dados_cabecalho']['n_pontos_total'] = len(testes_sem_duplicatas)

        try:
            # Salva o arquivo unido
            with open(caminho_saida, 'w', encoding='utf-8') as f:
                json.dump(novo_json_data, f, indent=4, ensure_ascii=False)
            
            # Mensagem de sucesso existente
            print(f"  -> SUCESSO: Grupo salvo em '{nome_saida}' com {pontos_apos_limpeza_duplicatas} pontos limpos e unidos.")
            
            # --- NOVO RELATÓRIO DO GRUPO ---
            print("  --- Relatório do Grupo (impresso e salvo no JSON) ---")
            print(f"    Arquivos unidos ({len(arquivos_do_grupo)}):")
            for f_path in arquivos_do_grupo:
                print(f"      - {os.path.basename(f_path)}")
            print(f"    Pontos com massa 0g removidos: {total_pontos_massa_zero_removidos}")
            print(f"    Pontos duplicados removidos:   {total_pontos_duplicados_removidos}")
            print(f"    Total de pontos brutos:        {total_pontos_brutos}")
            print(f"    Total de pontos finais:        {pontos_apos_limpeza_duplicatas}")
            print("  ----------------------------")
            # --- FIM DO NOVO RELATÓRIO ---
            
            # --- NOVO: Mover arquivos de origem para a subpasta ---
            # 1. Criar o nome e o caminho da pasta
            # Remove .json do nome do arquivo salvo para criar o nome da pasta
            nome_pasta_arquivados = nome_saida.replace('.json', '')
            caminho_pasta_arquivados = os.path.join(JSON_INPUT_DIR, nome_pasta_arquivados)
            
            # 2. Criar a pasta
            os.makedirs(caminho_pasta_arquivados, exist_ok=True)
            
            # 3. Mover os arquivos
            print(f"  Movendo arquivos de origem para '{nome_pasta_arquivados}'...")
            arquivos_movidos_count = 0
            for caminho_arquivo_original in arquivos_do_grupo:
                nome_arquivo_original = os.path.basename(caminho_arquivo_original)
                novo_caminho = os.path.join(caminho_pasta_arquivados, nome_arquivo_original)
                
                # Usa os.rename para mover o arquivo
                os.rename(caminho_arquivo_original, novo_caminho)
                arquivos_movidos_count += 1
            
            print(f"  -> SUCESSO: {arquivos_movidos_count} arquivos de origem movidos.")
            # --- FIM DA NOVA SEÇÃO ---

        except Exception as e:
            print(f"  -> ERRO: Ocorreu um erro durante o salvamento ou movimentação de arquivos para '{nome_saida}': {e}")
            print("     Verifique se o arquivo unido foi salvo. Os arquivos de origem não foram movidos.")
            # Se deu erro, pula para o próximo grupo
            continue

    print(f"\n--- União de arquivos concluída. ---")


# --- FUNÇÕES EXISTENTES (OPÇÕES 1 e 2) ---

def processar_limpeza_massa_zero():
# ... (código existente inalterado) ...
    """
    Analisa TODOS os JSONs, reporta amostras com massa 0g
    e permite ao usuário removê-las, salvando no MESMO arquivo.
    """
    print("\n--- Iniciando Verificação de Massa 0g ---")
    arquivos_json = buscar_arquivos_json(JSON_INPUT_DIR)
    
    if not arquivos_json:
# ... (código existente inalterado) ...
        print(f"Nenhum arquivo .json de origem encontrado em '{JSON_INPUT_DIR}'.")
        return

    arquivos_para_modificar = {} # Dicionário para guardar {caminho: [amostras_com_massa_zero]}

    # 1. Escanear e encontrar amostras
    print("Analisando arquivos...")
    for caminho_arquivo in arquivos_json:
        try:
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            testes = data.get("testes", [])
            # Usamos 0.0 para garantir a comparação com float
            amostras_massa_zero = [t for t in testes if t.get('massa_g_registrada', 0.0) == 0.0] 
            
            if amostras_massa_zero:
                arquivos_para_modificar[caminho_arquivo] = amostras_massa_zero
        except json.JSONDecodeError:
            print(f"ERRO: Falha ao decodificar o arquivo {os.path.basename(caminho_arquivo)}. Pulando.")
        except Exception as e:
            print(f"ERRO ao ler {os.path.basename(caminho_arquivo)}: {e}. Pulando.")
            
    # 2. Relatório e Confirmação
    if not arquivos_para_modificar:
        print("\nSUCESSO: Nenhuma amostra com massa 0g encontrada nos arquivos.")
        return

    print("\n" + "="*70)
    print("RELATÓRIO DE LIMPEZA (AMOSTRAS COM MASSA 0g)")
    print("="*70)
    print("Os seguintes arquivos contêm amostras com massa 0g e serão modificados:")
    
    for caminho_arquivo, amostras in arquivos_para_modificar.items():
        print(f"\n[ Arquivo: {os.path.basename(caminho_arquivo)} ]")
        print("  Amostras a serem removidas:")
        for amostra in amostras:
            print(f"    - Ponto No.: {amostra.get('ponto_n')}, Massa: {amostra.get('massa_g_registrada', 0.0):.3f}g")

    print("="*70)
    
    # 3. Pedir confirmação
    while True:
        confirm = input("\nDeseja continuar e remover estas amostras dos arquivos ORIGINAIS? (s/n): ").strip().lower()
        if confirm == 's':
            break
        if confirm == 'n':
            print("\nOperação de limpeza cancelada pelo usuário.")
            return

    # 4. Executar Limpeza
    print("\nIniciando limpeza e renumeração...")
    total_amostras_removidas = 0
    
    for caminho_arquivo in arquivos_para_modificar.keys():
        print(f"Processando: {os.path.basename(caminho_arquivo)}...")
        try:
            # Recarrega o arquivo para garantir
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            testes_originais = data.get("testes", [])
            testes_limpos = []
            novo_indice = 1
            
            # Filtra e renumera
            for teste in testes_originais:
                if teste.get('massa_g_registrada', 0.0) != 0.0:
                    teste["ponto_n"] = novo_indice
                    testes_limpos.append(teste)
                    novo_indice += 1
            
            data["testes"] = testes_limpos
            removidas = len(testes_originais) - len(testes_limpos)
            total_amostras_removidas += removidas
            
            # Salva no MESMO arquivo
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"  -> SUCESSO: Arquivo salvo. {removidas} amostra(s) removida(s).")
            
        except Exception as e:
            print(f"  -> ERRO ao salvar {os.path.basename(caminho_arquivo)}: {e}")

    print(f"\n--- Limpeza de massa 0g concluída. Total de {total_amostras_removidas} amostra(s) removida(s). ---")


def processar_limpeza_manual():
# ... (código existente inalterado) ...
    """Função original de limpeza e reordenação MANUAL."""
    caminho_arquivo_original = selecionar_arquivo_json(JSON_INPUT_DIR)
    
    if not caminho_arquivo_original:
        print("\nProcessamento manual cancelado.")
        return

    nome_arquivo_original = os.path.basename(caminho_arquivo_original)
    print(f"\nCarregando arquivo: {nome_arquivo_original}")

    # 1. Carregar o JSON
    try:
        with open(caminho_arquivo_original, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERRO: Arquivo não encontrado.")
        return
    except json.JSONDecodeError:
        print("ERRO: Falha ao decodificar o arquivo JSON. Verifique o formato.")
        return
    except Exception as e:
        print(f"ERRO ao carregar o arquivo: {e}")
        return

    testes_originais = data.get("testes", [])
    if not testes_originais:
        print("AVISO: O arquivo JSON não contém nenhum teste para editar.")
        return

    # 2. Exibir Tabela de Pontos para Edição
    pontos_para_tabela = []
    for teste in testes_originais:
        pontos_para_tabela.append({
            "Ponto No.": teste.get("ponto_n"),
            "Massa (g)": f"{teste.get('massa_g_registrada', 0.0):.3f}",
            "Duracao (s)": f"{teste.get('duracao_real_s', 0.0):.3f}",
            "Pressao Media (bar)": f"{teste.get('media_pressao_final_ponto_bar', 0.0):.3f}"
        })
    
    df_pontos = pd.DataFrame(pontos_para_tabela)
    
    print("\n" + "="*70)
    print("VISUALIZAÇÃO DOS PONTOS DISPONÍVEIS PARA EDIÇÃO")
    print("="*70)
    # Garante que a coluna de ponto_n esteja sempre visível e não truncada
    with pd.option_context('display.max_rows', None, 'display.width', 150):
        print(df_pontos.to_string(index=False))
    print("="*70)

    # 3. Solicitar Pontos a Excluir
    while True:
        pontos_str = input("\nDigite os NÚMEROS de 'Ponto No.' a EXCLUIR, separados por vírgula (ex: 4, 36). Pressione Enter para NÃO excluir nenhum: ").strip()
        
        if not pontos_str:
            indices_para_remover = set()
            print("Nenhum ponto será excluído.")
            break
            
        try:
            # Converte a entrada do usuário para um set de inteiros
            partes = pontos_str.replace(' ', '').split(',')
            indices_para_remover = set(int(p) for p in partes if p.isdigit())
            
            pontos_validos = set(t.get("ponto_n") for t in testes_originais)
            
            # Valida se todos os pontos a remover existem
            if not indices_para_remover.issubset(pontos_validos):
                pontos_invalidos = indices_para_remover.difference(pontos_validos)
                print(f"ERRO: Os seguintes números de ponto não existem: {list(pontos_invalidos)}. Tente novamente.")
                continue
            
            break
        except ValueError:
            print("ERRO: Entrada inválida. Use apenas números separados por vírgula.")
        except Exception as e:
            print(f"Ocorreu um erro: {e}")
            return

    # 4. Remover e Renumerar
    testes_limpos = []
    novo_indice = 1
    
    for teste in testes_originais:
        if teste.get("ponto_n") not in indices_para_remover:
            # Renumera o ponto
            teste["ponto_n"] = novo_indice
            testes_limpos.append(teste)
            novo_indice += 1

    pontos_removidos_count = len(testes_originais) - len(testes_limpos)
    
    if pontos_removidos_count == 0 and not indices_para_remover:
         print("\nNenhum ponto selecionado para remoção.")
         # Mesmo que nada mude, podemos querer salvar um 'edit_' para consistência
         # ou podemos simplesmente sair. Vamos sair se nada mudou.
         if not pontos_str: # Se o usuário apertou Enter
             print("Nenhuma alteração feita.")
             return

    print(f"\n--- Processamento Concluído ---")
    print(f"{pontos_removidos_count} ponto(s) removido(s) do total. {len(testes_limpos)} ponto(s) restante(s).")
    
    # 5. Atualizar o Objeto JSON e Salvar NOVO Arquivo (padrão 'edit_')
    data["testes"] = testes_limpos
    
    caminho_saida = os.path.join(JSON_INPUT_DIR, f"edit_{nome_arquivo_original}")
    
    try:
        with open(caminho_saida, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"SUCESSO: Arquivo limpo e reordenado salvo em: {caminho_saida}")
        print("\nVocê deve usar este novo arquivo ('edit_...') nos scripts de análise (2.Analise_reologica.py e 2b.Tratamento_Estatistico.py).")
    except Exception as e:
        print(f"ERRO ao salvar o novo arquivo JSON: {e}")

# --- Bloco Principal ---
if __name__ == "__main__":
# ... (código existente inalterado) ...
    if not os.path.exists(JSON_INPUT_DIR):
        os.makedirs(JSON_INPUT_DIR)
        print(f"A pasta de entrada '{JSON_INPUT_DIR}' foi criada. Por favor, coloque os arquivos JSON de ensaio aqui.")
    
    while True:
# ... (código existente inalterado) ...
        print("\n" + "="*50)
        print("MENU DE EDIÇÃO E UNIÃO DE ARQUIVOS JSON")
        print("="*50)
        print("1. Remover pontos manualmente (interativo)")
        print("2. Limpar amostras com massa 0g (automático)")
        print("3. Unir arquivos JSON semelhantes (automático)")
        print("0. Sair")
        
        escolha_menu = input("Escolha uma opção: ").strip()
        
        if escolha_menu == '1':
            processar_limpeza_manual()
        elif escolha_menu == '2':
            processar_limpeza_massa_zero()
        elif escolha_menu == '3':
            processar_uniao_arquivos()
        elif escolha_menu == '0':
            print("\n--- FIM DO SCRIPT ---")
            break
        else:
            print("ERRO: Opção inválida. Tente novamente.")

