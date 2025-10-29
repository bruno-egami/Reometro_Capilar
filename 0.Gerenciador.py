import subprocess
import sys
import os
import datetime
import re
import json

# --- Configuração dos Diretórios ---
DIRETORIO_RESULTADOS_BASE = "Resultados_Reometro"
DIRETORIO_TESTES_REOMETRO = "resultados_testes_reometro" # Onde o Script 1 salva o JSON original

# --- Configuração dos Scripts ---
# Mapeia um nome amigável para o nome do arquivo do script
scripts = {
    "1": {"nome": "Controle Reômetro (Gera JSON inicial)", "arquivo": "1.Controle_Reometro.py", "etapa_sugerida": "coleta"},
    "2": {"nome": "Editar JSON Coleta", "arquivo": "1a.Edit-Json-coleta.py", "etapa_sugerida": "coleta_editada"},
    "3": {"nome": "Pré-análise e Filtro", "arquivo": "1b.Pre-analise-filtro.py", "etapa_sugerida": "pre_analise"},
    "4": {"nome": "Análise Reológica", "arquivo": "2.Analise_reologica.py", "etapa_sugerida": "analise_reologica"},
    "5": {"nome": "Tratamento Estatístico", "arquivo": "2b.Tratamento_Estatistico.py", "etapa_sugerida": "analise_estatistica"},
    "6": {"nome": "Filtro de Resíduos do Modelo", "arquivo": "2cFiltro_Residuos_Modelo.py", "etapa_sugerida": "filtro_residuos"},
    "7": {"nome": "Visualizar Resultados", "arquivo": "3.Visualizar_resultados.py", "etapa_sugerida": "visualizacao"},
    "8": {"nome": "Comparativo entre Análises", "arquivo": "4.Comparativo-Analises.py", "etapa_sugerida": "comparativo"},
    "9": {"nome": "Processador Rotacional Completo", "arquivo": "5.Processador_Rotacional_Completo.py", "etapa_sugerida": "rotacional"},
}

# --- Variáveis Globais para Gerenciamento da Análise Atual ---
analise_id_atual = None
diretorio_analise_atual = None
metadados_analise_atual = {}

# --- Funções Auxiliares ---
def limpar_tela():
    """Limpa o terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')

def sanitizar_nome(nome):
    """Remove caracteres inválidos para nomes de arquivos/diretórios."""
    nome = re.sub(r'[^\w\-_\. ]', '_', nome) # Mantém letras, números, -, _, ., espaço
    nome = nome.strip().replace(' ', '_')    # Remove espaços extras e substitui por _
    return nome

def iniciar_nova_analise():
    """Solicita informações e cria um diretório para uma nova análise."""
    global analise_id_atual, diretorio_analise_atual, metadados_analise_atual

    limpar_tela()
    print("--- Iniciar Nova Análise ---")
    material = input("Nome do Material: ")
    capilar = input("Informação do Capilar (ex: 1.5x43): ")
    descricao = input("Descrição curta (opcional): ")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_id = f"{timestamp}_{sanitizar_nome(material)}_{sanitizar_nome(capilar)}"
    if descricao:
        base_id += f"_{sanitizar_nome(descricao)}"

    analise_id_atual = base_id
    diretorio_analise_atual = os.path.join(DIRETORIO_RESULTADOS_BASE, analise_id_atual)

    try:
        os.makedirs(diretorio_analise_atual, exist_ok=True)
        print(f"\nDiretório da análise criado: {diretorio_analise_atual}")

        # Inicializa metadados
        metadados_analise_atual = {
            "id": analise_id_atual,
            "material": material,
            "capilar": capilar,
            "descricao": descricao,
            "timestamp_inicio": timestamp,
            "arquivos_gerados": {}, # Para rastrear arquivos por etapa
            "fc_calculado": None
        }
        salvar_metadados() # Salva o arquivo inicial de metadados

    except OSError as e:
        print(f"\nErro ao criar o diretório '{diretorio_analise_atual}': {e}")
        analise_id_atual = None
        diretorio_analise_atual = None
        metadados_analise_atual = {}
        input("Pressione Enter para continuar...")
        return # Retorna ao menu se não conseguir criar o diretório

    print(f"Análise '{analise_id_atual}' iniciada.")
    input("Pressione Enter para voltar ao menu...")

def salvar_metadados():
    """Salva o dicionário de metadados em um arquivo JSON no diretório da análise."""
    if diretorio_analise_atual:
        caminho_meta = os.path.join(diretorio_analise_atual, f"{analise_id_atual}_metadados.json")
        try:
            with open(caminho_meta, 'w', encoding='utf-8') as f:
                json.dump(metadados_analise_atual, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar metadados em {caminho_meta}: {e}")

def carregar_analise_existente():
    """Permite ao usuário selecionar um diretório de análise existente."""
    global analise_id_atual, diretorio_analise_atual, metadados_analise_atual
    limpar_tela()
    print("--- Carregar Análise Existente ---")
    if not os.path.exists(DIRETORIO_RESULTADOS_BASE):
        print(f"Diretório base '{DIRETORIO_RESULTADOS_BASE}' não encontrado.")
        input("Pressione Enter para voltar...")
        return

    try:
        analises = [d for d in os.listdir(DIRETORIO_RESULTADOS_BASE) if os.path.isdir(os.path.join(DIRETORIO_RESULTADOS_BASE, d))]
    except Exception as e:
        print(f"Erro ao listar análises em '{DIRETORIO_RESULTADOS_BASE}': {e}")
        input("Pressione Enter para voltar...")
        return

    if not analises:
        print("Nenhuma análise encontrada.")
        input("Pressione Enter para voltar...")
        return

    print("Análises encontradas:")
    for i, nome_analise in enumerate(analises):
        print(f"  {i+1} - {nome_analise}")

    while True:
        escolha = input("Digite o número da análise a carregar (ou 0 para cancelar): ")
        if escolha == '0':
            return
        if escolha.isdigit() and 1 <= int(escolha) <= len(analises):
            analise_id_selecionado = analises[int(escolha)-1]
            diretorio_selecionado = os.path.join(DIRETORIO_RESULTADOS_BASE, analise_id_selecionado)
            caminho_meta = os.path.join(diretorio_selecionado, f"{analise_id_selecionado}_metadados.json")

            if os.path.exists(caminho_meta):
                try:
                    with open(caminho_meta, 'r', encoding='utf-8') as f:
                        metadados_carregados = json.load(f)
                    analise_id_atual = analise_id_selecionado
                    diretorio_analise_atual = diretorio_selecionado
                    metadados_analise_atual = metadados_carregados
                    print(f"\nAnálise '{analise_id_atual}' carregada.")
                    input("Pressione Enter para continuar...")
                    return
                except Exception as e:
                    print(f"Erro ao carregar metadados de '{caminho_meta}': {e}")
                    print("Carregando análise sem metadados anteriores.")
                    analise_id_atual = analise_id_selecionado
                    diretorio_analise_atual = diretorio_selecionado
                    # Resetar metadados ou tentar inferir? Por enquanto, reseta.
                    metadados_analise_atual = {"id": analise_id_atual, "arquivos_gerados": {}}
                    input("Pressione Enter para continuar...")
                    return
            else:
                 print(f"Aviso: Arquivo de metadados não encontrado em '{diretorio_selecionado}'.")
                 print("Carregando análise sem metadados.")
                 analise_id_atual = analise_id_selecionado
                 diretorio_analise_atual = diretorio_selecionado
                 metadados_analise_atual = {"id": analise_id_atual, "arquivos_gerados": {}}
                 input("Pressione Enter para continuar...")
                 return
        else:
            print("Seleção inválida.")


def gerar_caminho_arquivo(etapa, extensao, subdiretorio=None):
    """Gera um caminho completo padronizado para um arquivo da análise atual."""
    if not analise_id_atual or not diretorio_analise_atual:
        return None # Nenhuma análise ativa

    nome_base = f"{analise_id_atual}_{etapa}{extensao}"

    if subdiretorio:
        # Cria o subdiretório se não existir
        path_subdiretorio = os.path.join(diretorio_analise_atual, subdiretorio)
        os.makedirs(path_subdiretorio, exist_ok=True)
        return os.path.join(path_subdiretorio, nome_base)
    else:
        return os.path.join(diretorio_analise_atual, nome_base)

def exibir_menu():
    """Exibe o menu de opções para o usuário."""
    limpar_tela()
    print("--- Gerenciador de Scripts Reômetro ---")
    if analise_id_atual:
        print(f"Análise Atual: {analise_id_atual}")
    else:
        print("Nenhuma análise ativa.")
    print("-" * 39)

    print("\nOpções:")
    print("  N - Iniciar Nova Análise")
    print("  L - Carregar Análise Existente")
    print("\nExecutar Script:")
    for key, value in scripts.items():
        print(f"  {key} - {value['nome']}")
    print("\n  0 - Sair")
    print("-" * 39)

def sugerir_arquivos(numero_script):
    """Sugere nomes de arquivos de entrada/saída para o script selecionado."""
    if not analise_id_atual:
        print("\nAVISO: Nenhuma análise ativa. Inicie ou carregue uma análise primeiro.")
        return

    script_info = scripts.get(numero_script)
    if not script_info:
        return

    etapa = script_info['etapa_sugerida']
    print("\n--- Sugestões de Arquivos/Diretórios ---")

    # Sugestões específicas para cada script
    if numero_script == "1": # Controle Reômetro
        # Assume que este script salva diretamente em 'resultados_testes_reometro'
        # com um nome que ele próprio gera. Precisamos *encontrar* esse arquivo depois.
        print(f"  - O Script 1 salva o JSON inicial em '{DIRETORIO_TESTES_REOMETRO}'.")
        print(f"  - Após a execução, anote o nome do arquivo JSON gerado.")
        # Poderíamos tentar listar o diretório e pegar o mais recente, mas é arriscado.
        # Por enquanto, deixamos manual.

    elif numero_script == "2": # Editar JSON Coleta
        # Precisa do JSON original do Script 1
        json_original = metadados_analise_atual['arquivos_gerados'].get("coleta_original_path")
        if json_original:
             print(f"  Arquivo de Entrada (JSON original): {json_original}")
        else:
             print(f"  Arquivo de Entrada: Informe o caminho completo do JSON gerado pelo Script 1.")

        sugestao_saida = gerar_caminho_arquivo("coleta_editada", ".json")
        print(f"  Arquivo de Saída Sugerido: {sugestao_saida}")
        metadados_analise_atual['arquivos_gerados']['coleta_editada'] = sugestao_saida # Assume que será usado

    elif numero_script == "3": # Pré-análise e Filtro
        entrada_sugerida = gerar_caminho_arquivo("coleta_editada", ".json")
        saida_sugerida_csv = gerar_caminho_arquivo("pre_analise", ".csv")
        saida_sugerida_png = gerar_caminho_arquivo("pre_analise", ".png")
        print(f"  Arquivo de Entrada Sugerido (JSON editado): {entrada_sugerida}")
        print(f"  Arquivo de Saída CSV Sugerido: {saida_sugerida_csv}")
        print(f"  Arquivo de Saída PNG Sugerido: {saida_sugerida_png}")
        metadados_analise_atual['arquivos_gerados']['pre_analise_csv'] = saida_sugerida_csv
        metadados_analise_atual['arquivos_gerados']['pre_analise_png'] = saida_sugerida_png

    elif numero_script == "4": # Análise Reológica
        entrada_sugerida = gerar_caminho_arquivo("pre_analise", ".csv")
        # Este script pode ser executado mais de uma vez (FC1, FC calculado)
        # Vamos sugerir nomes baseados em subdiretórios
        fc_atual = metadados_analise_atual.get('fc_calculado')
        subpasta = f"analise_FC_{fc_atual}" if fc_atual else "analise_FC1"

        saida_sugerida_base = gerar_caminho_arquivo(etapa, "", subdiretorio=subpasta)
        print(f"  Arquivo de Entrada Sugerido (CSV pré-análise): {entrada_sugerida}")
        print(f"  Diretório de Saída Sugerido: {os.path.dirname(saida_sugerida_base)}")
        print(f"  (O script provavelmente pedirá um diretório e salvará vários arquivos lá dentro)")
        metadados_analise_atual['arquivos_gerados'][subpasta] = os.path.dirname(saida_sugerida_base)

    elif numero_script == "8": # Comparativo entre Análises
        # Este script precisa de DOIS inputs. O gerenciador atual não lida bem com isso.
        print("  Este script compara duas análises.")
        print(f"  Análise 1 (Atual): {diretorio_analise_atual}")
        print(f"  Análise 2: Você precisará informar o diretório da outra análise.")
        print(f"  Diretório de Saída Sugerido: {gerar_caminho_arquivo('comparativo', '', subdiretorio='comparativos')}")
        # Idealmente, o script 4 seria modificado para aceitar os IDs/Paths como argumentos.

    # Adicionar sugestões para outros scripts conforme necessário
    else:
        print(f"  (Sugestões de arquivos para '{script_info['nome']}' ainda não implementadas)")

    print("-" * 39)
    # Salva os metadados com os caminhos sugeridos (mesmo que o usuário use outros)
    salvar_metadados()

def executar_script(numero_script):
    """Executa o script selecionado pelo usuário, mostrando sugestões de nomes."""
    if numero_script not in scripts:
        print("\nOpção inválida!")
        input("Pressione Enter para tentar novamente...")
        return

    if not analise_id_atual and numero_script != "1": # Permite executar o script 1 sem análise ativa
         print("\nErro: Nenhuma análise ativa. Use 'N' para iniciar ou 'L' para carregar.")
         input("Pressione Enter para continuar...")
         return

    script_info = scripts[numero_script]
    nome_arquivo = script_info['arquivo']

    # Mostra sugestões ANTES de executar
    sugerir_arquivos(numero_script)

    print(f"\n>>> Executando: {script_info['nome']}...")
    print(f"(Script: {nome_arquivo})")
    print("Por favor, forneça os nomes de arquivos/diretórios solicitados pelo script.")
    print("-" * 39 + "\n")

    try:
        if not os.path.exists(nome_arquivo):
            print(f"Erro: O arquivo '{nome_arquivo}' não foi encontrado.")
            input("Pressione Enter para continuar...")
            return

        # Executa o script interativamente no terminal atual
        # Permite que os inputs() do script funcionem
        # NOTA: A captura de output é perdida com este método
        processo = subprocess.Popen([sys.executable, nome_arquivo],
                                     stdin=sys.stdin, # Conecta o input do terminal ao script
                                     # stdout=sys.stdout, # Descomente se quiser ver a saída em tempo real
                                     # stderr=sys.stderr  # Descomente para ver erros em tempo real
                                     text=True, encoding='utf-8' # Adicionado encoding
                                     )
        processo.wait() # Espera o script terminar
        retorno = processo.returncode

        print("\n" + "-" * 39)
        if retorno != 0:
            print(f"AVISO: O script {nome_arquivo} terminou com código de erro {retorno}.")
        print(f">>> {script_info['nome']} finalizado.")

        # --- Pós-execução específica ---
        if numero_script == "1": # Controle Reômetro
             print("\n--- Ação Pós-Script 1 ---")
             arquivo_json_gerado = input("Cole aqui o caminho COMPLETO do arquivo JSON gerado pelo Script 1: ")
             if os.path.exists(arquivo_json_gerado):
                 metadados_analise_atual['arquivos_gerados']['coleta_original_path'] = arquivo_json_gerado
                 # Opcional: Copiar o arquivo original para a pasta da análise para centralizar
                 try:
                     nome_destino = gerar_caminho_arquivo("coleta_original", ".json")
                     import shutil
                     shutil.copy2(arquivo_json_gerado, nome_destino)
                     metadados_analise_atual['arquivos_gerados']['coleta_original_copia'] = nome_destino
                     print(f"Arquivo original copiado para: {nome_destino}")
                 except Exception as e:
                     print(f"Não foi possível copiar o arquivo original: {e}")
                 salvar_metadados()
             else:
                 print("Arquivo não encontrado. O caminho não foi salvo nos metadados.")

        # Adicionar lógicas pós-execução para outros scripts se necessário
        # Ex: Ler o FC calculado pelo script 4 e salvar nos metadados

    except FileNotFoundError:
        print(f"Erro: O arquivo '{nome_arquivo}' não foi encontrado ou Python não está no PATH.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao tentar executar '{nome_arquivo}': {e}")

    input("\nPressione Enter para voltar ao menu...")


# --- Loop Principal ---
def main():
    """Função principal que controla o fluxo do menu."""
    # Cria o diretório base de resultados se não existir
    os.makedirs(DIRETORIO_RESULTADOS_BASE, exist_ok=True)

    while True:
        exibir_menu()
        escolha = input("Digite a opção desejada: ").upper() # Converte para maiúscula

        if escolha == '0':
            print("\nSaindo do gerenciador...")
            break
        elif escolha == 'N':
            iniciar_nova_analise()
        elif escolha == 'L':
            carregar_analise_existente()
        elif escolha.isdigit() and escolha in scripts:
            executar_script(escolha)
        else:
            print("\nEntrada inválida. Por favor, digite uma opção válida.")
            input("Pressione Enter para continuar...")

if __name__ == "__main__":
    main()

