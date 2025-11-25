# -*- coding: utf-8 -*-
import os
import numpy as np
import matplotlib.pyplot as plt
import utils_reologia

# Importa modelos para plotagem
from modelos_reologicos import MODELS

def plotar_ajuste_bagley(L_over_R_vals, P_vals, slope, intercept, target_gamma_aw_str, output_folder, timestamp):
    """Gera e salva um gráfico do ajuste de Bagley para uma taxa de cisalhamento específica."""
    if len(L_over_R_vals) < 2: return
    plt.figure(figsize=(8, 6))
    plt.scatter(L_over_R_vals, np.array(P_vals) / 1e5, marker='o', label='Dados Interpolados')
    line_x = np.array(sorted(L_over_R_vals))
    line_y_pa = slope * line_x + intercept
    plt.plot(line_x, line_y_pa / 1e5, color='red', label=rf"Ajuste Linear ($\tau_{{w,\text{{corr}}}} = {slope/2:.1f}$ Pa)")
    plt.xlabel('Razão Comprimento/Raio (L/R) (adimensional)')
    plt.ylabel("Pressão Total Medida (" + r"$\Delta P$" + ") (bar)")
    title_str = f"Plot de Bagley para " + \
                rf"$\dot{{\gamma}}_{{\text{{ap}}}}^* \approx {float(target_gamma_aw_str):.1f} \text{{ s}}^{{-1}}$"
    plt.title(title_str)
    plt.legend(); plt.grid(True)
    filename = os.path.join(output_folder, f"{timestamp}_bagley_plot_gamma_aw_{float(target_gamma_aw_str):.0f}.png")
    try:
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"  Plot de Bagley salvo em: {filename}")
    except Exception as e: print(f"  ERRO ao salvar plot de Bagley: {e}")
    plt.close()

def gerar_graficos_finais(output_folder, timestamp_str, 
                          gamma_dot_aw_an, tau_w_an, 
                          gamma_dot_w_an_wr, eta_true_an, eta_a_an,
                          n_prime, log_K_prime,
                          model_results, best_model_nome,
                          pressoes_bar_display_tab, D_cap_mm_unico_val, L_cap_mm_unico_val,
                          realizar_bagley, realizar_mooney, calibracao_aplicada):
    """
    Gera e salva os 5 gráficos principais da análise reológica.
    
    Args:
        output_folder: Pasta para salvar os arquivos.
        timestamp_str: String de data/hora para nomes de arquivo.
        gamma_dot_aw_an: Array de taxa de cisalhamento aparente.
        tau_w_an: Array de tensão de cisalhamento na parede (corrigida ou não).
        gamma_dot_w_an_wr: Array de taxa de cisalhamento corrigida (Weissenberg-Rabinowitsch).
        eta_true_an: Array de viscosidade real.
        eta_a_an: Array de viscosidade aparente.
        n_prime: Índice de comportamento de fluxo (n').
        log_K_prime: Logaritmo do índice de consistência (ln(K')).
        model_results: Dicionário com resultados dos ajustes de modelos.
        best_model_nome: Nome do melhor modelo ajustado.
        pressoes_bar_display_tab: Lista de pressões (para gráfico P vs Visc).
        D_cap_mm_unico_val: Diâmetro do capilar (para gráfico P vs Visc).
        L_cap_mm_unico_val: Comprimento do capilar (para gráfico P vs Visc).
        realizar_bagley: Booleano indicando se Bagley foi feito.
        realizar_mooney: Booleano indicando se Mooney foi feito.
        calibracao_aplicada: Booleano indicando se Calibração externa foi aplicada.
        
    Returns:
        list: Lista de nomes dos arquivos gerados.
    """
    
    arquivos_gerados_lista = []
    
    # Prepara dados para plotagem dos modelos (linha suave)
    valid_fit = ~np.isnan(tau_w_an) & ~np.isnan(gamma_dot_w_an_wr) & (gamma_dot_w_an_wr > 0)
    if np.any(valid_fit):
        min_gd, max_gd = np.min(gamma_dot_w_an_wr[valid_fit]), np.max(gamma_dot_w_an_wr[valid_fit])
        gd_plot = np.geomspace(min_gd * 0.8, max_gd * 1.2, 100)
    else:
        gd_plot = np.array([])

    # --- Gráfico 1: Curva de Fluxo (Tensão vs Taxa de Cisalhamento) ---
    fig1, ax1 = plt.subplots(figsize=(10, 7))
    if np.any(valid_fit):
        ax1.scatter(gamma_dot_w_an_wr[valid_fit], tau_w_an[valid_fit], label='Dados Experimentais (Corrigidos)', c='b', marker='o', s=60, zorder=10)
        # Linha conectando os pontos experimentais
        ax1.plot(gamma_dot_w_an_wr[valid_fit], tau_w_an[valid_fit], c='b', linestyle='-', linewidth=1, alpha=0.5, zorder=9)

    if len(gd_plot) > 0:
        for n_model_name, (func_modelo, param_names, initial_guess_func, bounds) in MODELS.items():
            if n_model_name not in model_results: continue
            d_model_data = model_results[n_model_name]
            try:
                tau_m = func_modelo(gd_plot, *d_model_data['params'])
                label_m = f"{n_model_name} (R²={d_model_data['R2']:.4f})"
                if n_model_name == best_model_nome:
                    ax1.plot(gd_plot, tau_m, label=label_m + " [MELHOR]", linestyle='-', linewidth=2.5, color='red', zorder=20)
                else:
                    ax1.plot(gd_plot, tau_m, label=label_m, linestyle='--', linewidth=1.5, alpha=0.7)
            except Exception as e_plot_model: print(f"  Aviso ao plotar modelo {n_model_name}: {e_plot_model}")

    ax1.set_xlabel("Taxa de Cisalhamento Corrigida (γ̇w, s⁻¹)")
    ax1.set_ylabel("Tensão de Cisalhamento na Parede (τw, Pa)")
    ax1.set_title("Curva de Fluxo: Tensão vs. Taxa de Cisalhamento")
    ax1.legend(); ax1.grid(True, which="both", ls="--"); ax1.set_xscale('log'); ax1.set_yscale('log'); fig1.tight_layout()
    f1_name = os.path.join(output_folder, f"{timestamp_str}_curva_fluxo.png"); arquivos_gerados_lista.append(os.path.basename(f1_name))
    try: fig1.savefig(f1_name, dpi=300); print(f"Gráfico Curva de Fluxo salvo: {f1_name}")
    except Exception as e: print(f"ERRO ao salvar Curva de Fluxo: {e}")

    # --- Gráfico 2: Determinação de n' (ln(tau) vs ln(gamma_ap)) ---
    # Nota: Usa gamma_dot_aw_an (aparente) e tau_w_an (que pode ser Bagley-corrigido, mas para n' usa-se dados brutos idealmente, 
    # mas o script original usa os dados disponíveis no momento. Mantendo lógica original.)
    valid_log = (gamma_dot_aw_an > 0) & (tau_w_an > 0) & (~np.isnan(gamma_dot_aw_an)) & (~np.isnan(tau_w_an))
    if np.any(valid_log):
        # Filtra para evitar log(0) ou log(negativo)
        valid_log_np = np.where(valid_log)[0]
        if len(valid_log_np) > 1:
            log_t_p, log_g_aw_p = np.log(tau_w_an[valid_log_np]), np.log(gamma_dot_aw_an[valid_log_np])
            fig2, ax2 = plt.subplots(figsize=(10, 7))
            ax2.scatter(log_g_aw_p, log_t_p, label='Dados Experimentais ln(γ̇aw) vs ln(τw)', c='r', marker='x', s=60)
            if len(log_g_aw_p) > 1:
                min_lg, max_lg = np.min(log_g_aw_p), np.max(log_g_aw_p)
                if max_lg > min_lg: 
                    log_g_line = np.linspace(min_lg, max_lg, 50)
                    ax2.plot(log_g_line, n_prime * log_g_line + log_K_prime, '--', c='b', lw=2, label=fr'Ajuste Linear (n\'={n_prime:.3f})')
            ax2.set_xlabel("ln(Taxa de Cis. Apar. na Parede) (ln(γ̇aw))")
            ax2.set_ylabel("ln(Tensão de Cis. na Parede) (ln(τw))")
            ax2.set_title("Determinação de n' (Índice da Lei de Potência Aparente)")
            ax2.legend(); ax2.grid(True, which="both", ls="--"); fig2.tight_layout()
            f2_name = os.path.join(output_folder, f"{timestamp_str}_n_prime.png"); arquivos_gerados_lista.append(os.path.basename(f2_name))
            try: fig2.savefig(f2_name, dpi=300); print(f"Gráfico n' salvo: {f2_name}")
            except Exception as e: print(f"ERRO ao salvar n': {e}")

    # --- Gráfico 3: Curva de Viscosidade ---
    fig3, ax3 = plt.subplots(figsize=(10, 7))
    valid_eta = ~np.isnan(eta_true_an) & (gamma_dot_w_an_wr > 0) & (eta_true_an > 0) & (~np.isinf(eta_true_an))
    if np.any(valid_eta): 
        ax3.plot(gamma_dot_w_an_wr[valid_eta], eta_true_an[valid_eta], label='Viscosidade Real Experimental (η)', c='g', marker='s', linestyle='-', linewidth=1.5, markersize=8, zorder=10)
    
    if len(gd_plot) > 0:
        for n_model_name, (func_modelo, param_names, initial_guess_func, bounds) in MODELS.items():
            if n_model_name not in model_results: continue
            d_model_data = model_results[n_model_name]
            try:
                tau_m = func_modelo(gd_plot, *d_model_data['params'])
                eta_m = tau_m / gd_plot
                if n_model_name == "Newtoniano": eta_m = np.full_like(gd_plot, d_model_data['params'][0])
                ax3.plot(gd_plot, eta_m, label=fr'Modelo {n_model_name} ($\eta$)', lw=2.5, alpha=0.8)
            except Exception as e_plot_model_eta: print(f"  Aviso ao plotar modelo {n_model_name}: {e_plot_model_eta}")
    ax3.set_xlabel("Taxa de Cisalhamento Corrigida (γ̇w, s⁻¹)")
    ax3.set_ylabel("Viscosidade Real (η, Pa·s)")
    ax3.set_title("Viscosidade Real (η) vs. Taxa de Cisalhamento Corrigida (γ̇w)")
    ax3.legend(); ax3.grid(True, which="both", ls="--"); ax3.set_xscale('log'); ax3.set_yscale('log'); fig3.tight_layout()
    f3_name = os.path.join(output_folder, f"{timestamp_str}_curva_viscosidade.png"); arquivos_gerados_lista.append(os.path.basename(f3_name))
    try: fig3.savefig(f3_name, dpi=300); print(f"Gráfico Viscosidade salvo: {f3_name}")
    except Exception as e: print(f"ERRO ao salvar Viscosidade: {e}")

    # --- Gráfico 4: Pressão vs Viscosidade (Apenas para capilar único sem correções) ---
    if not realizar_bagley and not realizar_mooney and not calibracao_aplicada:
        pressoes_bar_np_plot = np.array(pressoes_bar_display_tab, dtype=float)
        if len(pressoes_bar_np_plot) == len(eta_true_an):
            valid_pv = (~np.isnan(eta_true_an)) & (~np.isnan(pressoes_bar_np_plot)) & (eta_true_an > 0) & (pressoes_bar_np_plot > 0)
            if np.any(valid_pv):
                P_Pa_plot, eta_plot = pressoes_bar_np_plot[valid_pv] * 1e5, eta_true_an[valid_pv]
                fig4, ax4 = plt.subplots(figsize=(10, 7))
                ax4.plot(P_Pa_plot, eta_plot, label='Viscosidade Real Experimental', color='purple', marker='D', linestyle='-', linewidth=1.5, markersize=8, zorder=10)
                
                # Curva do melhor modelo para comparação
                if model_results and best_model_nome and len(gd_plot) > 0:
                    try:
                        best_model_data = model_results[best_model_nome]
                        tau_modelo = MODELS[best_model_nome][0](gd_plot, *best_model_data['params'])
                        
                        if best_model_nome == "Newtoniano":
                            eta_modelo = np.full_like(gd_plot, best_model_data['params'][0])
                        else:
                            eta_modelo = tau_modelo / gd_plot
                        
                        R_cap_m = D_cap_mm_unico_val / 2000
                        L_cap_m = L_cap_mm_unico_val / 1000
                        P_modelo_Pa = tau_modelo * (2 * L_cap_m / R_cap_m)
                        
                        valid_modelo = (P_modelo_Pa > 0) & (eta_modelo > 0) & (~np.isnan(eta_modelo)) & (~np.isinf(eta_modelo))
                        
                        if np.any(valid_modelo):
                            ax4.plot(P_modelo_Pa[valid_modelo], eta_modelo[valid_modelo], 
                                    label=f'Modelo {best_model_nome}', 
                                    color='red', linestyle='-', linewidth=2.5, alpha=0.8, zorder=5)
                    except Exception as e_plot_modelo_p:
                        print(f"  Aviso: Não foi possível plotar curva do modelo em P vs η: {e_plot_modelo_p}")
                
                ax4.set_xlabel("Pressao Total Aplicada (ΔPtotal, Pa)")
                ax4.set_ylabel("Viscosidade Real (η, Pa·s)")
                ax4.set_title("Pressao Aplicada vs. Viscosidade Real (Capilar Unico s/ Correcoes)")
                ax4.legend(); ax4.grid(True, which="both", ls="--"); ax4.set_xscale('linear'); ax4.set_yscale('linear'); fig4.tight_layout()
                f4_name = os.path.join(output_folder, f"{timestamp_str}_pressao_vs_viscosidade.png"); arquivos_gerados_lista.append(os.path.basename(f4_name))
                try: fig4.savefig(f4_name, dpi=300); print(f"Gráfico P vs Visc salvo: {f4_name}")
                except Exception as e: print(f"ERRO ao Salvar P vs Visc: {e}")

    # --- Gráfico 5: Comparativo de Viscosidades ---
    fig5, ax5 = plt.subplots(figsize=(10, 7))
    valid_apparent_idx = (gamma_dot_aw_an > 0) & (~np.isnan(eta_a_an)) & (eta_a_an > 0) & (~np.isinf(eta_a_an))
    if np.any(valid_apparent_idx):
        ax5.plot(gamma_dot_aw_an[valid_apparent_idx], eta_a_an[valid_apparent_idx],
                    label=r'Viscosidade Aparente ($\eta_a$ vs $\dot{\gamma}_{aw}$)',
                    marker='o', linestyle='--', color='blue', alpha=0.7, linewidth=1.5)
    if np.any(valid_eta):
         ax5.plot(gamma_dot_w_an_wr[valid_eta], eta_true_an[valid_eta],
                     label=r'Viscosidade Real ($\eta$ vs $\dot{\gamma}_w$)',
                     marker='s', linestyle='-', color='green', alpha=0.7, linewidth=1.5, markersize=6, zorder=5)
    
    # Curva do melhor modelo para comparação
    if model_results and best_model_nome and len(gd_plot) > 0:
        try:
            best_model_data = model_results[best_model_nome]
            tau_modelo = MODELS[best_model_nome][0](gd_plot, *best_model_data['params'])
            
            if best_model_nome == "Newtoniano":
                eta_modelo = np.full_like(gd_plot, best_model_data['params'][0])
            else:
                eta_modelo = tau_modelo / gd_plot
            
            valid_modelo_eta = (eta_modelo > 0) & (~np.isnan(eta_modelo)) & (~np.isinf(eta_modelo))
            
            if np.any(valid_modelo_eta):
                ax5.plot(gd_plot[valid_modelo_eta], eta_modelo[valid_modelo_eta], 
                        label=f'Modelo {best_model_nome} (η)', 
                        color='red', linestyle='-', linewidth=2.5, alpha=0.85, zorder=6)
        except Exception as e_plot_modelo_eta:
            print(f"  Aviso: Não foi possível plotar curva do modelo em Comparativo: {e_plot_modelo_eta}")
    
    ax5.set_xlabel("Taxa de Cisalhamento (s⁻¹)")
    ax5.set_ylabel("Viscosidade (Pa·s)")
    ax5.set_title("Comparativo: Viscosidade Aparente vs. Viscosidade Real vs. Modelo")
    ax5.legend(); ax5.grid(True, which="both", ls="--"); ax5.set_xscale('log'); ax5.set_yscale('log'); fig5.tight_layout()
    f5_name = os.path.join(output_folder, f"{timestamp_str}_comparativo_viscosidades.png"); arquivos_gerados_lista.append(os.path.basename(f5_name))
    try: fig5.savefig(f5_name, dpi=300); print(f"Gráfico Comparativo Viscosidades salvo: {f5_name}")
    except Exception as e: print(f"ERRO ao salvar Comparativo Viscosidades: {e}")

    print("\nFeche as janelas dos gráficos para finalizar a execução."); plt.show()
    
    return arquivos_gerados_lista
