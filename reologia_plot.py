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
                          realizar_bagley, realizar_mooney, calibracao_aplicada,
                          only_show=False,
                          std_tau_w=None, std_eta=None,
                          show_plots=False):
    """
    Gera e salva os 5 gráficos principais da análise reológica.
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
        # Plota pontos com barras de erro se disponíveis
        if std_tau_w is not None and len(std_tau_w) == len(tau_w_an):
            ax1.errorbar(gamma_dot_w_an_wr[valid_fit], tau_w_an[valid_fit], 
                        yerr=std_tau_w[valid_fit], 
                        label='Dados Experimentais (Corrigidos)', 
                        fmt='o', color='b', markersize=6, capsize=4, 
                        elinewidth=1.5, alpha=0.7, zorder=10)
        else:
            ax1.scatter(gamma_dot_w_an_wr[valid_fit], tau_w_an[valid_fit], 
                       label='Dados Experimentais (Corrigidos)', 
                       c='b', marker='o', s=60, zorder=10)
            # Linha conectando os pontos experimentais
            ax1.plot(gamma_dot_w_an_wr[valid_fit], tau_w_an[valid_fit], 
                    c='b', linestyle='-', linewidth=1, alpha=0.5, zorder=9)

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
    
    if not only_show:
        f1_name = os.path.join(output_folder, f"{timestamp_str}_curva_fluxo.png")
        arquivos_gerados_lista.append(os.path.basename(f1_name))
        try: fig1.savefig(f1_name, dpi=300); print(f"Gráfico Curva de Fluxo salvo: {f1_name}")
        except Exception as e: print(f"ERRO ao salvar Curva de Fluxo: {e}")

    # --- Gráfico 2: Determinação de n' (ln(tau) vs ln(gamma_ap)) ---
    valid_log = (gamma_dot_aw_an > 0) & (tau_w_an > 0) & (~np.isnan(gamma_dot_aw_an)) & (~np.isnan(tau_w_an))
    if np.any(valid_log):
        valid_log_np = np.where(valid_log)[0]
        if len(valid_log_np) > 1:
            log_t_p, log_g_aw_p = np.log(tau_w_an[valid_log_np]), np.log(gamma_dot_aw_an[valid_log_np])
            fig2, ax2 = plt.subplots(figsize=(10, 7))
            
            if std_tau_w is not None and len(std_tau_w) == len(tau_w_an):
                log_err_y = std_tau_w[valid_log_np] / tau_w_an[valid_log_np]
                ax2.errorbar(log_g_aw_p, log_t_p, yerr=log_err_y,
                           label='Dados Experimentais ln(γ̇aw) vs ln(τw)', 
                           fmt='x', color='r', markersize=8, capsize=4,
                           elinewidth=1.5, alpha=0.7)
            else:
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
            
            if not only_show:
                f2_name = os.path.join(output_folder, f"{timestamp_str}_n_prime.png")
                arquivos_gerados_lista.append(os.path.basename(f2_name))
                try: fig2.savefig(f2_name, dpi=300); print(f"Gráfico n' salvo: {f2_name}")
                except Exception as e: print(f"ERRO ao salvar n': {e}")

    # --- Gráfico 3: Curva de Viscosidade ---
    fig3, ax3 = plt.subplots(figsize=(10, 7))
    valid_eta = ~np.isnan(eta_true_an) & (gamma_dot_w_an_wr > 0) & (eta_true_an > 0) & (~np.isinf(eta_true_an))
    if np.any(valid_eta): 
        if std_eta is not None and len(std_eta) == len(eta_true_an):
            ax3.errorbar(gamma_dot_w_an_wr[valid_eta], eta_true_an[valid_eta],
                        yerr=std_eta[valid_eta],
                        label='Viscosidade Real Experimental (η)',
                        fmt='s', color='g', markersize=6, capsize=4,
                        elinewidth=1.5, alpha=0.7, zorder=10)
        else:
            ax3.plot(gamma_dot_w_an_wr[valid_eta], eta_true_an[valid_eta], 
                    label='Viscosidade Real Experimental (η)', 
                    c='g', marker='s', linestyle='-', linewidth=1.5, markersize=8, zorder=10)
    
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
    
    if not only_show:
        f3_name = os.path.join(output_folder, f"{timestamp_str}_curva_viscosidade.png")
        arquivos_gerados_lista.append(os.path.basename(f3_name))
        try: fig3.savefig(f3_name, dpi=300); print(f"Gráfico Viscosidade salvo: {f3_name}")
        except Exception as e: print(f"ERRO ao salvar Viscosidade: {e}")

    # --- Gráfico 4: Pressão vs Viscosidade (Apenas para capilar único sem correções) ---
    if not realizar_bagley and not realizar_mooney and not calibracao_aplicada:
        pressoes_bar_np_plot = np.array(pressoes_bar_display_tab, dtype=float)
        if len(pressoes_bar_np_plot) == len(eta_true_an):
            valid_pv = (~np.isnan(eta_true_an)) & (~np.isnan(pressoes_bar_np_plot)) & (eta_true_an > 0) & (pressoes_bar_np_plot > 0)
            if np.any(valid_pv):
                P_Pa_plot = pressoes_bar_np_plot[valid_pv] * 1e5
                eta_plot = eta_true_an[valid_pv]
                fig4, ax4 = plt.subplots(figsize=(10, 7))

                # Plot experimental viscosity with error bars if available
                if std_eta is not None and len(std_eta) == len(eta_true_an):
                    ax4.errorbar(P_Pa_plot, eta_plot, yerr=std_eta[valid_pv],
                                 label='Viscosidade Real Experimental',
                                 fmt='D', color='purple', markersize=6, capsize=4)
                else:
                    ax4.plot(P_Pa_plot, eta_plot,
                             label='Viscosidade Real Experimental',
                             marker='D', color='purple', markersize=6)

                # Plot model curve (pressure vs viscosity)
                if model_results and best_model_nome:
                    try:
                        best_model_data = model_results[best_model_nome]
                        tau_modelo = MODELS[best_model_nome][0](gd_plot, *best_model_data['params'])
                        if best_model_nome == "Newtoniano":
                            eta_modelo = np.full_like(gd_plot, best_model_data['params'][0])
                        else:
                            eta_modelo = tau_modelo / gd_plot
                        
                        # Determine x-axis values: pressure if geometry available, else experimental pressure
                        if D_cap_mm_unico_val > 0 and L_cap_mm_unico_val > 0:
                            R_cap_m = D_cap_mm_unico_val / 2000
                            L_cap_m = L_cap_mm_unico_val / 1000
                            P_modelo_Pa = tau_modelo * (2 * L_cap_m / R_cap_m)
                            x_vals = P_modelo_Pa
                        else:
                            x_vals = None
                            pass

                        if x_vals is not None:
                            valid = (x_vals > 0) & (~np.isnan(x_vals)) & (~np.isinf(x_vals))
                            if np.any(valid):
                                ax4.plot(x_vals[valid], eta_modelo[valid],
                                         label=f'Modelo {best_model_nome}',
                                         color='red', linestyle='-', linewidth=2.5, alpha=0.8, zorder=5)
                    except Exception as e_plot_modelo:
                        print(f"  Aviso: Não foi possível plotar curva do modelo em P vs η: {e_plot_modelo}")

                ax4.set_xlabel("Pressão Total Aplicada (ΔPtotal, Pa)")
                ax4.set_ylabel("Viscosidade Real (η, Pa·s)")
                ax4.set_title("Pressão Aplicada vs. Viscosidade Real (Capilar Único s/ Correções)")
                ax4.legend(); ax4.grid(True, which="both", ls="--")
                ax4.set_xscale('linear'); ax4.set_yscale('linear')
                fig4.tight_layout()
                if not only_show:
                    f4_name = os.path.join(output_folder, f"{timestamp_str}_pressao_vs_viscosidade.png")
                    arquivos_gerados_lista.append(os.path.basename(f4_name))
                    try:
                        fig4.savefig(f4_name, dpi=300)
                        print(f"Gráfico P vs Visc salvo: {f4_name}")
                    except Exception as e:
                        print(f"ERRO ao Salvar P vs Visc: {e}")

    # --- Gráfico 5: Comparativo de Viscosidades ---
    fig5, ax5 = plt.subplots(figsize=(10, 7))
    valid_apparent_idx = (gamma_dot_aw_an > 0) & (~np.isnan(eta_a_an)) & (eta_a_an > 0) & (~np.isinf(eta_a_an))
    if np.any(valid_apparent_idx):
        ax5.plot(gamma_dot_aw_an[valid_apparent_idx], eta_a_an[valid_apparent_idx],
                 label='Viscosidade Aparente (η_a)',
                 marker='^', linestyle='--', color='orange', alpha=0.7)

    if np.any(valid_eta):
        if std_eta is not None and len(std_eta) == len(eta_true_an):
            ax5.errorbar(gamma_dot_w_an_wr[valid_eta], eta_true_an[valid_eta],
                        yerr=std_eta[valid_eta],
                        label='Viscosidade Real (η)',
                        fmt='s', color='g', markersize=6, capsize=4, alpha=0.9)
        else:
            ax5.plot(gamma_dot_w_an_wr[valid_eta], eta_true_an[valid_eta],
                    label='Viscosidade Real (η)',
                    marker='s', linestyle='-', color='g', alpha=0.9)

    ax5.set_xlabel("Taxa de Cisalhamento (s⁻¹)")
    ax5.set_ylabel("Viscosidade (Pa·s)")
    ax5.set_title("Comparativo: Viscosidade Aparente vs. Real")
    ax5.legend(); ax5.grid(True, which="both", ls="--"); ax5.set_xscale('log'); ax5.set_yscale('log'); fig5.tight_layout()
    
    # Adiciona curva do modelo se disponível
    if len(gd_plot) > 0 and model_results and best_model_nome:
        try:
            best_model_data = model_results[best_model_nome]
            tau_modelo = MODELS[best_model_nome][0](gd_plot, *best_model_data['params'])
            if best_model_nome == "Newtoniano":
                eta_modelo = np.full_like(gd_plot, best_model_data['params'][0])
            else:
                eta_modelo = tau_modelo / gd_plot
            ax5.plot(gd_plot, eta_modelo, label=f'Modelo {best_model_nome} (Real)', 
                     color='red', linestyle='-', linewidth=2, alpha=0.6, zorder=5)
            # Atualiza legenda
            ax5.legend()
        except Exception: pass

    if not only_show:
        f5_name = os.path.join(output_folder, f"{timestamp_str}_comparativo_viscosidades.png")
        arquivos_gerados_lista.append(os.path.basename(f5_name))
        try: fig5.savefig(f5_name, dpi=300); print(f"Gráfico Comparativo salvo: {f5_name}")
        except Exception as e: print(f"ERRO ao salvar Comparativo: {e}")
    
    if show_plots or only_show:
        plt.show()
    
    # Fecha todas as figuras após mostrar
    plt.close('all')
    
    return arquivos_gerados_lista

def plotar_curva_fluxo_estatistica(gamma_dot_mean, tau_w_mean, tau_w_std, model_results, best_model_nome, output_folder, timestamp_str):
    """
    Plota curva de fluxo com barras de erro (desvio padrão).
    """
    fig, ax = plt.subplots(figsize=(10, 7))
    
    # Plota dados experimentais com erro
    ax.errorbar(gamma_dot_mean, tau_w_mean, yerr=tau_w_std, fmt='o', color='blue', 
                ecolor='gray', elinewidth=2, capsize=4, label='Média Experimental ± Desvio Padrão')
    
    # Plota modelos
    if model_results and best_model_nome:
        min_gd, max_gd = np.min(gamma_dot_mean), np.max(gamma_dot_mean)
        gd_plot = np.geomspace(min_gd * 0.8, max_gd * 1.2, 100)
        
        for n_model_name, (func_modelo, param_names, initial_guess_func, bounds) in MODELS.items():
            if n_model_name not in model_results: continue
            d_model_data = model_results[n_model_name]
            try:
                tau_m = func_modelo(gd_plot, *d_model_data['params'])
                label_m = f"{n_model_name} (R²={d_model_data['R2']:.4f})"
                if n_model_name == best_model_nome:
                    ax.plot(gd_plot, tau_m, label=label_m + " [MELHOR]", linestyle='-', linewidth=2.5, color='red', zorder=20)
                else:
                    ax.plot(gd_plot, tau_m, label=label_m, linestyle='--', linewidth=1.5, alpha=0.7)
            except Exception: pass

    ax.set_xlabel("Taxa de Cisalhamento (s⁻¹)")
    ax.set_ylabel("Tensão de Cisalhamento (Pa)")
    ax.set_title("Curva de Fluxo Estatística (Média ± Std)")
    ax.legend()
    ax.grid(True, which="both", ls="--")
    ax.set_xscale('log'); ax.set_yscale('log')
    
    f_name = os.path.join(output_folder, f"{timestamp_str}_fluxo_estatistico.png")
    try: 
        fig.savefig(f_name, dpi=300)
        # plt.show() # Não mostrar para não bloquear execução em loop
        plt.close(fig)
        return f_name
    except: 
        plt.close(fig)
        return None

def plotar_comparativo_multiplo(dados_analises, coluna_x, coluna_y, titulo, xlabel, ylabel, output_folder, timestamp_str, usar_log=True, show_plots=False, only_show=False, modelos_dict=None):
    """
    Plota comparativo de múltiplas análises.
    dados_analises: dict {nome_legenda: df}
    modelos_dict: dict {nome_legenda: {'model_name': str, 'params': list}} (Opcional)
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    
    marcadores = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
    cores = plt.cm.tab10(np.linspace(0, 1, len(dados_analises)))
    
    for i, (nome, df) in enumerate(dados_analises.items()):
        cor = cores[i]
        marcador = marcadores[i % len(marcadores)]
        
        if coluna_x in df.columns and coluna_y in df.columns:
            x = df[coluna_x]
            y = df[coluna_y]
            # Filtra NaNs e infinitos
            valid = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
            if np.any(valid):
                ax.plot(x[valid], y[valid], marker=marcador, 
                        color=cor, label=nome, linestyle='-', alpha=0.7, markersize=6)
                
                # --- Plota Curva do Modelo (Se disponível) ---
                if modelos_dict and nome in modelos_dict:
                    print(f"    [DEBUG] Plotando modelo para '{nome}'...")
                    try:
                        dados_modelo = modelos_dict[nome]
                        nome_modelo = dados_modelo.get('Melhor Modelo')
                        params = dados_modelo.get('Parametros')
                        
                        print(f"    [DEBUG] Modelo: {nome_modelo}, Params: {params}")
                        
                        if nome_modelo and params and nome_modelo in MODELS:
                            func_modelo = MODELS[nome_modelo][0]
                            
                            # Gera pontos para a curva suave
                            min_x, max_x = x[valid].min(), x[valid].max()
                            x_model = np.geomspace(min_x, max_x, 100)
                            
                            # Calcula Y do modelo
                            # Se o eixo Y for Tensão (Pa)
                            if 'Pa' in ylabel and 'Viscosidade' not in ylabel:
                                y_model = func_modelo(x_model, *params)
                            # Se o eixo Y for Viscosidade (Pa.s)
                            elif 'Viscosidade' in ylabel:
                                tau_model = func_modelo(x_model, *params)
                                y_model = tau_model / x_model
                            else:
                                y_model = None
                                
                            if y_model is not None:
                                ax.plot(x_model, y_model, color=cor, linestyle='--', linewidth=2, 
                                        alpha=0.9, label=f"Modelo {nome_modelo} ({nome})")
                                print(f"    [DEBUG] Curva do modelo plotada com sucesso.")
                        else:
                            print(f"    [DEBUG] Modelo inválido ou não encontrado em MODELS.")
                    except Exception as e:
                        print(f"  Erro ao plotar modelo para {nome}: {e}")
    
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, which="both", ls="--")
    
    if usar_log:
        ax.set_xscale('log'); ax.set_yscale('log')
        
    plt.tight_layout()
    
    f_name = None
    if not only_show:
        safe_title = "".join([c if c.isalnum() else "_" for c in titulo])
        f_name = os.path.join(output_folder, f"{timestamp_str}_comparativo_{safe_title}.png")
        try: 
            fig.savefig(f_name, dpi=300)
            print(f"  Gráfico salvo: {os.path.basename(f_name)}")
        except Exception as e:
            print(f"  Erro ao salvar gráfico: {e}")
            
    if show_plots or only_show:
        plt.show()
        
    plt.close(fig)
    return f_name
