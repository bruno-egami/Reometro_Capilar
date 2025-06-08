# -----------------------------------------------------------------------------
# SCRIPT PARA VISUALIZAÇÃO DE RESULTADOS DE ANÁLISE REOLÓGICA
# Versão 4.1 - Correção de Gráficos em Branco
# -----------------------------------------------------------------------------

import os
import glob
import json
import numpy as np
import pandas as pd
import matplotlib
try:
    matplotlib.use('Qt5Agg')
except ImportError:
    print("Aviso: Backend Qt5Agg não encontrado, usando o padrão do sistema.")
import matplotlib.pyplot as plt

# --- Definições dos Modelos Reológicos ---
def model_newtonian(gd,eta): return eta*gd
def model_power_law(gd,K_pl,n_pl): return K_pl*np.power(np.maximum(gd, 1e-9),n_pl)
def model_bingham(gd,t0,ep): return t0+ep*gd
def model_hb(gd,t0,K_hb,n_hb): return t0+K_hb*np.power(np.maximum(gd, 1e-9),n_hb)
def model_casson(gd, tau0_cas, eta_cas): 
    sqrt_tau0 = np.sqrt(np.maximum(tau0_cas, 0))
    sqrt_eta_cas_val = np.sqrt(np.maximum(eta_cas, 1e-9))
    sqrt_gd_val = np.sqrt(np.maximum(gd, 1e-9))
    return (sqrt_tau0 + sqrt_eta_cas_val * sqrt_gd_val)**2

models = {
    "Newtoniano": model_newtonian, "Lei da Potência": model_power_law, 
    "Bingham": model_bingham, "Herschel-Bulkley": model_hb, "Casson": model_casson
}

# --- Função Auxiliar para Adicionar Texto ---
def adicionar_texto_explicativo(fig, texto):
    fig.subplots_adjust(bottom=0.25)
    fig.text(0.5, 0.01, texto, ha='center', va='bottom', fontsize=9, wrap=True,
             bbox=dict(boxstyle='round,pad=0.5', fc='wheat', alpha=0.5))

def visualizador_principal():
    base_folder = "resultados_analise_reologica"
    if not os.path.exists(base_folder):
        print(f"ERRO: A pasta '{base_folder}' não foi encontrada."); return

    sessoes = sorted([d for d in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, d))], reverse=True)
    if not sessoes:
        print(f"Nenhuma sessão de análise encontrada em '{base_folder}'."); return

    print("\n--- Sessões de Análise Disponíveis ---")
    for i, sessao in enumerate(sessoes): print(f"  {i+1}: {sessao}")

    escolha = -1
    while escolha < 1 or escolha > len(sessoes):
        try:
            escolha = int(input(f"Escolha o número da sessão que deseja visualizar (1-{len(sessoes)}): "))
        except ValueError: print("Entrada inválida.")
    
    pasta_selecionada = os.path.join(base_folder, sessoes[escolha - 1])
    print(f"\nCarregando dados da sessão: {pasta_selecionada}")

    try:
        path_resultados = glob.glob(os.path.join(pasta_selecionada, '*_resultados_reologicos.csv'))[0]
        path_resumo_modelo = glob.glob(os.path.join(pasta_selecionada, '*_resumo_melhor_modelo.csv'))[0]
        path_parametros = glob.glob(os.path.join(pasta_selecionada, '*_parametros_modelos.json'))[0]
        df_res = pd.read_csv(path_resultados, sep=';', decimal=',')
        df_summary = pd.read_csv(path_resumo_modelo, sep=';', decimal=',')
        with open(path_parametros, 'r') as f:
            dados_modelos_completos = json.load(f)
        model_results = dados_modelos_completos.get("modelos_ajustados", {})
    except Exception as e: print(f"ERRO ao carregar arquivos de resultado: {e}"); return

    # Extração de dados
    best_model_nome = df_summary.loc[df_summary['Parâmetro'] == 'Modelo Reológico Ajustado', 'Valor Estimado'].iloc[0]
    tau_w_an = df_res['τw (Pa)'].values
    gamma_dot_w_an_wr = df_res['γ̇w (s⁻¹)'].values
    eta_true_an = df_res['η (Pa·s)'].values

    valid_fit = ~np.isnan(tau_w_an) & ~np.isnan(gamma_dot_w_an_wr) & (gamma_dot_w_an_wr > 0)
    gd_fit = gamma_dot_w_an_wr[valid_fit]
    if len(gd_fit) == 0: print("Não há dados válidos para gerar gráficos."); return

    print("Gerando gráficos...")
    min_gp_val = np.min(gd_fit) if np.any(gd_fit) else 1e-3
    max_gp_val = np.max(gd_fit) if np.any(gd_fit) else 1.0
    min_gp, max_gp = max(1e-9, min_gp_val * 0.5), max_gp_val * 1.5
    gd_plot = np.geomspace(min_gp, max_gp, 200)

    # --- GRUPO 1: GRÁFICOS INDIVIDUAIS ---
    print("\nGerando gráficos individuais...")
    
    # Gráfico 1: Curva de Fluxo (Comparativo)
    fig1, ax1 = plt.subplots(figsize=(10,7))
    ax1.scatter(gamma_dot_w_an_wr[valid_fit], tau_w_an[valid_fit], label='Dados Processados', c='k', marker='o', s=60, zorder=10)
    if model_results:
        for n_model_name, d_model_data in model_results.items():
            tau_plot_model = models[n_model_name](gd_plot, *d_model_data['params'])
            if n_model_name == best_model_nome:
                ax1.plot(gd_plot, tau_plot_model, label=fr'**Melhor Modelo: {n_model_name}** (R²={d_model_data["R2"]:.4f})', linewidth=3.5, linestyle='--', color='red', zorder=20)
            else:
                ax1.plot(gd_plot, tau_plot_model, label=fr'Modelo {n_model_name} (R²={d_model_data["R2"]:.4f})', linewidth=2, alpha=0.6)
    ax1.set_title(f"Curva de Fluxo (Comparativo de Modelos)\nSessão: {os.path.basename(pasta_selecionada)}")
    ax1.set_xlabel("Taxa de Cisalhamento Corrigida (" + r"$\dot{\gamma}_w$" + ", s⁻¹)"); ax1.set_ylabel("Tensão de Cisalhamento (" + r"$\tau_w$" + ", Pa)")
    ax1.legend(); ax1.grid(True,which="both",ls="--"); ax1.set_xscale('log'); ax1.set_yscale('log')
    texto_fig1 = "Este gráfico mostra a relação entre a Tensão de Cisalhamento (τw, força aplicada) e a Taxa de Cisalhamento (γ̇w, velocidade de deformação).\nA forma da curva indica o comportamento do fluido. As linhas coloridas representam modelos matemáticos ajustados aos dados."
    adicionar_texto_explicativo(fig1, texto_fig1)
    fig1.tight_layout(rect=[0, 0.05, 1, 0.95])

    # Gráfico 2: Curva de Viscosidade (Comparativo)
    fig2, ax2 = plt.subplots(figsize=(10,7))
    ax2.scatter(gamma_dot_w_an_wr[valid_fit], eta_true_an[valid_fit], label='Viscosidade Real (η)', c='g', marker='s', s=60, zorder=10)
    if model_results:
        for n_model_name,d_model_data in model_results.items():
            tau_m = models[n_model_name](gd_plot, *d_model_data['params'])
            eta_m = tau_m / gd_plot
            if n_model_name == best_model_nome:
                ax2.plot(gd_plot, eta_m, label=fr'**Melhor Modelo: {n_model_name}**', linewidth=3.5, linestyle='--', color='red')
            else:
                ax2.plot(gd_plot, eta_m, label=fr'Modelo {n_model_name} ($\eta$)', linewidth=2, alpha=0.6)
    ax2.set_title(f"Curva de Viscosidade (Comparativo de Modelos)\nSessão: {os.path.basename(pasta_selecionada)}")
    ax2.set_xlabel("Taxa de Cisalhamento Corrigida (γ̇w, s⁻¹)"); ax2.set_ylabel("Viscosidade Real (η, Pa·s)")
    ax2.legend(); ax2.grid(True,which="both",ls="--"); ax2.set_xscale('log'); ax2.set_yscale('log')
    texto_fig2 = "Este gráfico mostra como a Viscosidade (η, resistência ao fluxo) do material muda com a Taxa de Cisalhamento.\nUma linha descendente indica um comportamento Pseudoplástico (o fluido se torna 'mais fino' com o cisalhamento)."
    adicionar_texto_explicativo(fig2, texto_fig2)
    fig2.tight_layout(rect=[0, 0.05, 1, 0.95])

    # --- GRUPO 2: DASHBOARD CONSOLIDADO ---
    print("Gerando dashboard consolidado...")
    fig_dash, axs = plt.subplots(2, 2, figsize=(18, 12), constrained_layout=True)
    fig_dash.suptitle(f"Dashboard Reológico da Sessão: {os.path.basename(pasta_selecionada)}", fontsize=18)

    # Plot 1: Curva de Fluxo (Melhor Modelo)
    axs[0, 0].scatter(gamma_dot_w_an_wr[valid_fit], tau_w_an[valid_fit], c='k', marker='o', label='Dados')
    if model_results:
        best_model_params = model_results[best_model_nome]['params']
        best_model_r2 = model_results[best_model_nome]['R2']
        tau_plot_best_model = models[best_model_nome](gd_plot, *best_model_params)
        axs[0, 0].plot(gd_plot, tau_plot_best_model, color='red', label=f'{best_model_nome} (R²={best_model_r2:.4f})')
    axs[0, 0].set_title("Curva de Fluxo (Melhor Modelo)"); axs[0, 0].set_xlabel("γ̇w (s⁻¹)"); axs[0, 0].set_ylabel("τw (Pa)")
    axs[0, 0].legend(); axs[0, 0].grid(True, which="both", ls="--"); axs[0, 0].set_xscale('log'); axs[0, 0].set_yscale('log')

    # Plot 2: Curva de Viscosidade (Melhor Modelo)
    axs[0, 1].scatter(gamma_dot_w_an_wr[valid_fit], eta_true_an[valid_fit], c='g', marker='s', label='Dados')
    if model_results:
        eta_plot_best_model = models[best_model_nome](gd_plot, *best_model_params) / gd_plot
        axs[0, 1].plot(gd_plot, eta_plot_best_model, color='red', label=f'{best_model_nome}')
    axs[0, 1].set_title("Curva de Viscosidade (Melhor Modelo)"); axs[0, 1].set_xlabel("γ̇w (s⁻¹)"); axs[0, 1].set_ylabel("η (Pa·s)")
    axs[0, 1].legend(); axs[0, 1].grid(True, which="both", ls="--"); axs[0, 1].set_xscale('log'); axs[0, 1].set_yscale('log')

    # Plot 3: Gráfico de Resíduos
    if model_results:
        tau_w_predito = models[best_model_nome](gd_fit, *model_results[best_model_nome]['params'])
        residuos = tau_w_an[valid_fit] - tau_w_predito
        axs[1, 0].scatter(gd_fit, residuos, c='purple', marker='x')
    axs[1, 0].axhline(y=0, color='k', linestyle='--')
    axs[1, 0].set_title("Gráfico de Resíduos"); axs[1, 0].set_xlabel("γ̇w (s⁻¹)"); axs[1, 0].set_ylabel("Resíduo (Pa)")
    axs[1, 0].set_xscale('log'); axs[1, 0].grid(True)
    
    # Plot 4: Comparativo de Viscosidades (se dados disponíveis)
    eta_a_an_valid = df_res['ηa (Pa·s)'].dropna()
    gamma_dot_aw_an_valid = df_res['γ̇aw (s⁻¹)'][eta_a_an_valid.index]
    if not eta_a_an_valid.empty:
        axs[1, 1].plot(gamma_dot_aw_an_valid, eta_a_an_valid, label=r'Aparente ($\eta_a$)', marker='o', linestyle='--')
        axs[1, 1].plot(gamma_dot_w_an_wr[valid_fit], eta_true_an[valid_fit], label=r'Real ($\eta$)', marker='s', linestyle='-')
        axs[1, 1].set_title("Comparativo de Viscosidades"); axs[1, 1].set_xlabel("γ̇ (s⁻¹)"); axs[1, 1].set_ylabel("Viscosidade (Pa·s)")
        axs[1, 1].legend(); axs[1, 1].grid(True, which="both", ls="--"); axs[1, 1].set_xscale('log'); axs[1, 1].set_yscale('log')
    else:
        axs[1, 1].text(0.5, 0.5, 'Dados de Viscosidade Aparente\n não disponíveis para este plot.', ha='center', va='center')
        axs[1, 1].set_title("Comparativo de Viscosidades")

    # fig_dash.tight_layout(rect=[0, 0, 1, 0.96])
    
    print("\nVisualização pronta. Feche as janelas dos gráficos para encerrar.")
    plt.show()

if __name__ == "__main__":
    visualizador_principal()