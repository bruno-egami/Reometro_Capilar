import os
import sys
import subprocess
import time

def limpar_tela():
    os.system('cls' if os.name == 'nt' else 'clear')

def exibir_menu():
    limpar_tela()
    print("="*70)
    print("   SISTEMA DE CONTROLE - REÔMETRO CAPILAR & ANÁLISE REOLÓGICA")
    print("="*70)
    print("\n--- COLETA E PRÉ-PROCESSAMENTO ---")
    print("1. Controle do Reômetro (Coleta de Dados)       [1.Controle_Reometro.py]")
    print("2. Editar JSON de Coleta (Correção Manual)      [1a.Edit-Json-coleta.py]")
    print("3. Pré-Análise e Filtro (Gera CSV/JSON Final)   [1b.Pre-analise-filtro.py]")
    
    print("\n--- ANÁLISE E MODELAGEM ---")
    print("4. Análise Reológica (Modelos, Bagley, Mooney)  [2.Analise_reologica.py]")
    print("5. Filtro de Outliers por Resíduos (Refino)     [2cFiltro_Residuos_Modelo.py]")
    print("6. Tratamento Estatístico (Média de Testes)     [2b.Tratamento_Estatistico.py]")
    
    print("\n--- VISUALIZAÇÃO E COMPARAÇÃO ---")
    print("7. Visualizar Resultados (Gráficos Rápidos)     [3.Visualizar_resultados.py]")
    print("8. Comparativo de Análises (Capilar vs Rot.)    [4.Comparativo-Analises.py]")
    
    print("\n--- REÔMETRO ROTACIONAL ---")
    print("9. Processador de Dados Rotacionais (Converter Dados)   [5.Processador_Rotacional_Completo.py]")
    
    print("\n" + "-"*70)
    print("0. Sair")
    print("-"*70)

def executar_script(nome_script):
    if not os.path.exists(nome_script):
        print(f"\nERRO: O arquivo '{nome_script}' não foi encontrado neste diretório.")
        input("Pressione Enter para voltar...")
        return

    print(f"\nIniciando {nome_script}...\n")
    try:
        # Usa sys.executable para garantir que usa o mesmo interpretador Python
        subprocess.run([sys.executable, nome_script], check=False)
    except Exception as e:
        print(f"\nErro ao executar o script: {e}")
    
    input("\nScript finalizado. Pressione Enter para voltar ao menu...")

def main():
    scripts_map = {
        '1': '1.Controle_Reometro.py',
        '2': '1a.Edit-Json-coleta.py',
        '3': '1b.Pre-analise-filtro.py',
        '4': '2.Analise_reologica.py',
        '5': '2cFiltro_Residuos_Modelo.py',
        '6': '2b.Tratamento_Estatistico.py',
        '7': '3.Visualizar_resultados.py',
        '8': '4.Comparativo-Analises.py',
        '9': '5.Processador_Rotacional_Completo.py'
    }

    while True:
        exibir_menu()
        escolha = input("\nEscolha uma opção: ").strip()

        if escolha == '0':
            print("\nSaindo...")
            break
        elif escolha in scripts_map:
            executar_script(scripts_map[escolha])
        else:
            print("\nOpção inválida!")
            time.sleep(1)

if __name__ == "__main__":
    main()
