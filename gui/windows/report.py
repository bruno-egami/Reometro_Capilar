import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.ticker as ticker
import modelos_reologicos as models
from gui.utils import adjust_column_widths

class RelatorioWindow(ctk.CTkToplevel):
    def __init__(self, parent, analysis_data, export_callback=None):
        super().__init__(parent)
        self.analysis_data = analysis_data.copy()  # Use copy to avoid side effects
        self.export_callback = export_callback
        
        # Sort data by gamma_dot to avoid zigzagging in plots
        idx = np.argsort(self.analysis_data['gamma_dot'])
        self.analysis_data['gamma_dot'] = np.array(self.analysis_data['gamma_dot'])[idx]
        self.analysis_data['tau_w'] = np.array(self.analysis_data['tau_w'])[idx]
        self.analysis_data['eta'] = np.array(self.analysis_data['eta'])[idx]
        
        self.title(f"Relatório de Análise - {self.analysis_data['amostra']['nome']}")
        self.geometry("1000x800")
        
        # Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_resumo = self.tabview.add("Resumo")
        self.tab_graficos = self.tabview.add("Gráficos")
        self.tab_dados = self.tabview.add("Dados Calculados")
        
        self._init_resumo()
        self._init_graficos()
        self._init_dados()
        
        # Footer Actions
        self.footer = ctk.CTkFrame(self, height=50)
        self.footer.pack(fill="x", padx=10, pady=10)
        
        if export_callback:
            self.btn_pdf = ctk.CTkButton(self.footer, text="Salvar PDF", command=self.export_callback, fg_color="green")
            self.btn_pdf.pack(side="right", padx=10)
        
        self.btn_close = ctk.CTkButton(self.footer, text="Fechar", command=self.destroy, fg_color="red")
        self.btn_close.pack(side="right", padx=10)
        
        self.lift()
        self.focus_force()

    def _init_resumo(self):
        self.txt_resumo = ctk.CTkTextbox(self.tab_resumo, font=("Consolas", 14), wrap="word")
        self.txt_resumo.pack(fill="both", expand=True, padx=10, pady=10)
        
        d = self.analysis_data
        text = f"AMOSTRA: {d['amostra']['nome']}\n"
        text += f"Data Análise: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        text += "-"*40 + "\n"
        text += f"Modelo Melhor Ajuste: {d['best_model']}\n"
        text += f"R²: {d['best_r2']:.4f}\n"
        text += f"Índice de Comportamento (n): {d['n_prime']:.4f}\n"
        text += f"Classificação: {d['comportamento']}\n"
        text += "-"*40 + "\n\n"
        
        text += "PARÂMETROS DOS MODELOS:\n"
        for model_name, fit in d['model_fits'].items():
            if fit.get('params') is not None:
                text += f"{model_name}: R²={fit.get('r2', 0):.4f}, AIC={fit.get('aic', 0):.1f}\n"
                for i, n in enumerate(fit['param_names']):
                    v = fit['params'][i]
                    margin = fit.get('ic', {}).get(n, 0.0)
                    marg_str = f" ± {margin:.2g}" if margin > 0 else ""
                    text += f"  {n}: {v:.4g}{marg_str}\n"
                text += "\n"
        
        text += "-"*40 + "\n"
        text += "METODOLOGIA ESTATÍSTICA:\n"
        text += "-"*40 + "\n"
        text += "1. Agrupamento: Os pontos experimentais foram agrupados por Taxa de Cisalhamento (log-arredondado).\n"
        text += "2. Cálculo: Para cada grupo, calculou-se a Média e o Desvio Padrão da Tensão e Viscosidade.\n"
        text += "3. Ajuste: Os modelos reológicos foram ajustados aos valores MÉDIOS, reduzindo o impacto de ruído experimental.\n"
        text += "4. Visualização: As barras de erro nos gráficos representam ±1 Desvio Padrão.\n\n"
        
        text += "-"*40 + "\n"
        text += "ANÁLISE QUALITATIVA:\n"
        text += "-"*40 + "\n"
        
        # Qualitative analysis logic
        if d['best_r2'] > 0.99:
            text += f"O modelo '{d['best_model']}' apresentou excelente correlação (R²={d['best_r2']:.4f}). "
        elif d['best_r2'] > 0.95:
            text += f"O modelo '{d['best_model']}' apresentou boa correlação (R²={d['best_r2']:.4f}). "
        else:
            text += f"O modelo '{d['best_model']}' apresentou correlação moderada (R²={d['best_r2']:.4f}). "
            
        text += f"\n\nComportamento: {d['comportamento']}.\n"
        
        if "Pseudoplastico" in d['comportamento']:
            text += "Este material apresenta 'Shear Thinning', onde a viscosidade diminui com o aumento da taxa de cisalhamento. "
            if d['n_prime'] < 1:
                text += f"O índice n'={d['n_prime']:.3f} confirma este comportamento não-Newtoniano."
        elif "Dilatante" in d['comportamento']:
            text += "Este material apresenta 'Shear Thickening', onde a viscosidade aumenta com a taxa de cisalhamento."
        elif "Viscoplastico" in d['comportamento']:
            text += "O material exige uma tensão mínima (Yield Stress) para iniciar o fluxo, característica de pastas concentradas."
        elif "Newtoniano" in d['comportamento']:
            text += "A viscosidade permanece constante independente da taxa de cisalhamento."
            
        # --- Statistical Details ---
        if d.get('stats_details'):
            sd = d['stats_details']
            metrics = sd.get('metrics', {})
            
            text += "\n\n" + "-"*40 + "\n"
            text += "ANÁLISE DE VARIAÇÃO ESTATÍSTICA (CV):\n"
            text += "-"*40 + "\n"
            
            text += f"CV Médio (Tensão): {metrics.get('cv_tau_global', 0):.2f}%\n"
            text += f"CV Médio (Viscosidade): {metrics.get('cv_eta_global', 0):.2f}%\n"
            text += f"Pontos Analisados: {metrics.get('num_pontos', 0)}\n\n"
            
            text += "PARECER AUTOMÁTICO:\n"
            text += sd.get('parecer', 'N/A')
            
        self.txt_resumo.insert("1.0", text)
        self.txt_resumo.configure(state="disabled")

    def _init_graficos(self):
        self.graph_tabs = ctk.CTkTabview(self.tab_graficos)
        self.graph_tabs.pack(fill="both", expand=True)
        
        t1 = self.graph_tabs.add("Curva de Fluxo")
        t2 = self.graph_tabs.add("Viscosidade")
        t3 = self.graph_tabs.add("Ajuste de Modelos")
        
        desc_fluxo = "Explicação: Relaciona a Tensão (τ) vs Taxa (γ̇). O formato da curva define se o fluido é Newtoniano, Pseudoplástico ou Viscoplástico."
        desc_visc = "Explicação: Mostra a Viscosidade (Real ou Aparente) vs Taxa. A inclinação negativa indica comportamento 'Shear Thinning' (pseudoplástico)."
        desc_modelos = f"Explicação: Comparação dos dados experimentais (pontos) com os modelos teóricos (linhas). O melhor ajuste foi o modelo {self.analysis_data.get('best_model')}."
        
        self._plot_figure(t1, self._create_flow_curve(), desc_fluxo)
        self._plot_figure(t2, self._create_viscosity_curve(), desc_visc)
        self._plot_figure(t3, self._create_model_curve(), desc_modelos)
        
    def _plot_figure(self, parent, fig, description=None):
        if description:
            lbl = ctk.CTkLabel(parent, text=description, font=ctk.CTkFont(slant="italic", size=11), wraplength=800)
            lbl.pack(side="bottom", fill="x", padx=10, pady=5)
            
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _create_flow_curve(self):
        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        
        # Plot Raw Data (Light background)
        if 'raw_gamma' in self.analysis_data:
            ax.plot(self.analysis_data['raw_gamma'], self.analysis_data['raw_tau'], 'o', color='lightgray', markersize=4, alpha=0.5, label='Dados Brutos')
            
        # Plot Means with Error Bars
        x = self.analysis_data['gamma_dot']
        y = self.analysis_data['tau_w']
        yerr = self.analysis_data.get('tau_w_std', None)
        
        ax.errorbar(x, y, yerr=yerr, fmt='o-', capsize=5, label='Média ± DesvPad', color='blue')
        
        ax.set_title("Curva de Fluxo (Estatística)")
        ax.set_xlabel("Taxa de Cisalhamento (1/s)")
        ax.set_ylabel("Tensão de Cisalhamento (Pa)")
        ax.set_xscale('log')
        ax.set_yscale('log')
        
        # Better Ticks
        ax.yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=15))
        ax.yaxis.set_minor_locator(ticker.LogLocator(base=10.0, subs=np.arange(0.1, 1.0, 0.1), numticks=15))
        
        ax.grid(True, which="both", alpha=0.3)
        ax.legend()
        return fig

    def _create_viscosity_curve(self):
        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        
        # Plot Raw Data (Light background)
        if 'raw_gamma' in self.analysis_data and 'raw_eta' in self.analysis_data:
            ax.plot(self.analysis_data['raw_gamma'], self.analysis_data['raw_eta'], 's', color='lightgray', markersize=4, alpha=0.5, label='Dados Brutos')
        
        # Plot Means with Error Bars
        x = self.analysis_data['gamma_dot']
        y = self.analysis_data['eta']
        yerr = self.analysis_data.get('eta_std', None)
        
        ax.errorbar(x, y, yerr=yerr, fmt='s-', capsize=5, color='orange', label='Viscosidade Real')
        
        # Dual Plot (Always active if n' != 1)
        n_prime = self.analysis_data.get('n_prime', 1.0)
        if n_prime != 1.0:
            # Calculate Apparent
            factor = (3*n_prime + 1) / (4*n_prime)
            x_app = x / factor
            y_app = self.analysis_data['tau_w'] / x_app
            ax.loglog(x_app, y_app, 'b^--', markersize=5, label='Viscosidade Aparente', alpha=0.7)
            ax.set_title(f"Viscosidade: Real (n'={n_prime:.2f}) vs Aparente")
        else:
            ax.set_title("Viscosidade Aparente (Fluido Newtoniano)")
            
        ax.set_xlabel("Taxa de Cisalhamento (1/s)")
        ax.set_ylabel("Viscosidade (Pa.s)")
        ax.set_xscale('log')
        ax.set_yscale('log')
        
        # Better Ticks
        ax.yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=15))
        ax.yaxis.set_minor_locator(ticker.LogLocator(base=10.0, subs=np.arange(0.1, 1.0, 0.1), numticks=15))
        
        ax.grid(True, which="both", ls="-", alpha=0.3)
        ax.legend()
        return fig

    def _create_model_curve(self):
        # Create subplot 1x2 (Flow Curve | Viscosity Curve)
        fig = Figure(figsize=(10, 4), dpi=100)
        
        # --- Plot 1: Flow Curve (Stress vs Rate) ---
        ax1 = fig.add_subplot(121)
        x = self.analysis_data['gamma_dot']
        y = self.analysis_data['tau_w']
        yerr = self.analysis_data.get('tau_w_std', None)
        
        # Plot Raw Data Shadow (Flow)
        if 'raw_gamma' in self.analysis_data and 'raw_tau' in self.analysis_data:
            ax1.plot(self.analysis_data['raw_gamma'], self.analysis_data['raw_tau'], 'o', color='lightgray', markersize=3, alpha=0.4)
            
        ax1.errorbar(x, y, yerr=yerr, fmt='ko-', capsize=3, label='Dados experimentais', alpha=0.7)
        
        # Prepare smooth x for models
        if len(x) > 0:
            x_min = max(1e-3, min(x))
            x_max = max(x)
            if x_max > x_min:
                x_smooth = np.logspace(np.log10(x_min), np.log10(x_max), 100)
            else:
                x_smooth = np.array([x_min])
        else:
            x_smooth = np.array([1, 10, 100])
        
        colors = ['r', 'g', 'b', 'm', 'c']
        color_idx = 0
        
        # --- Plot Models on Both Graphs ---
        # We need to calculate Viscosity Prediction for the models too: eta_pred = tau_pred / gamma
        
        ax2 = fig.add_subplot(122) # Viscosity Plot
        # Plot Exp Viscosity
        eta = self.analysis_data['eta']
        eta_err = self.analysis_data.get('eta_std', None)
        
        # Plot Raw Data Shadow (Viscosity)
        if 'raw_gamma' in self.analysis_data and 'raw_eta' in self.analysis_data:
            ax2.plot(self.analysis_data['raw_gamma'], self.analysis_data['raw_eta'], 's', color='lightgray', markersize=3, alpha=0.4)
            
        # Plot Means with Error Bars
        ax2.errorbar(x, eta, yerr=eta_err, fmt='ks-', capsize=3, label='Viscosidade Real', alpha=0.7)
        
        for name, fit in self.analysis_data['model_fits'].items():
            if fit.get('params') is not None:
                if name in models.MODELS:
                    func = models.MODELS[name][0]
                    try:
                        # Calculate Preds
                        y_pred = func(x_smooth, *fit['params'])
                        eta_pred = y_pred / x_smooth
                        
                        color = colors[color_idx % len(colors)]
                        
                        # Plot 1 (Flow)
                        ax1.loglog(x_smooth, y_pred, linestyle='--', label=f"{name}", color=color)
                        
                        # Plot 2 (Viscosity)
                        ax2.loglog(x_smooth, eta_pred, linestyle='--', label=f"{name}", color=color)
                        
                        color_idx += 1
                    except Exception as e:
                        print(f"Erro ao plotar modelo {name}: {e}")
                    
        # Formatting Plot 1
        ax1.set_title("Curva de Fluxo")
        ax1.set_xlabel("Taxa (1/s)")
        ax1.set_ylabel("Tensão (Pa)")
        ax1.set_xscale('log')
        ax1.set_yscale('log')
        ax1.legend(fontsize='small')
        
        # Better Ticks
        ax1.yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=15))
        ax1.yaxis.set_minor_locator(ticker.LogLocator(base=10.0, subs=np.arange(0.1, 1.0, 0.1), numticks=15))
        
        ax1.grid(True, which="both", alpha=0.3)
        
        # Formatting Plot 2
        ax2.set_title("Viscosidade")
        ax2.set_xlabel("Taxa (1/s)")
        ax2.set_ylabel("Viscosidade (Pa.s)")
        ax2.set_xscale('log')
        ax2.set_yscale('log')
        ax2.legend(fontsize='small')
        
        # Better Ticks
        ax2.yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=15))
        ax2.yaxis.set_minor_locator(ticker.LogLocator(base=10.0, subs=np.arange(0.1, 1.0, 0.1), numticks=15))
        
        ax2.grid(True, which="both", alpha=0.3)
        
        fig.tight_layout()
        return fig

    def _init_dados(self):
        # Apply style for Treeview in Dark Mode
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        fieldbackground="#2b2b2b", 
                        borderwidth=0,
                        font=("Segoe UI", 11))
        style.configure("Treeview.Heading", 
                        background="#333333", 
                        foreground="white", 
                        relief="flat",
                        font=("Segoe UI", 11, "bold"))
        style.map("Treeview", background=[('selected', '#3a7ebf')])

        # Container frame
        container = ctk.CTkFrame(self.tab_dados)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Treeview
        cols = ("Taxa (1/s)", "Tensão (Pa)", "DesvPad Tensão", "Viscosidade (Pa.s)", "DesvPad Visc")
        tree = ttk.Treeview(container, columns=cols, show="headings", height=15)
        
        for c in cols:
            tree.heading(c, text=c)
            width = 150 if "Desv" in c else 120
            tree.column(c, width=width, anchor="center")
            
        # Scrollbar
        vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        d = self.analysis_data
        if 'gamma_dot' in d and len(d['gamma_dot']) > 0:
            for i in range(len(d['gamma_dot'])):
                g = d['gamma_dot'][i]
                t = d['tau_w'][i]
                t_std = d.get('tau_w_std', [0]*len(d['tau_w']))[i]
                e = d['eta'][i]
                e_std = d.get('eta_std', [0]*len(d['eta']))[i]
                
                tree.insert("", "end", values=(
                    f"{g:.2f}", 
                    f"{t:.2f}", 
                    f"{t_std:.2f}",
                    f"{e:.4f}",
                    f"{e_std:.4f}"
                ))
        else:
            tree.insert("", "end", values=("Nenhum dado", "", "", "", ""))
            
        # UI optimization: adjust columns
        adjust_column_widths(tree)
