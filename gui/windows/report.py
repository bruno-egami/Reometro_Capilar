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
        t3 = self.graph_tabs.add("Modelos (Tensão)")
        t4 = self.graph_tabs.add("Modelos (Viscosidade)")

        desc_fluxo = "Explicação: Relaciona a Tensão (τ) vs Taxa (γ̇). O formato da curva define se o fluido é Newtoniano, Pseudoplástico ou Viscoplástico."
        desc_visc = "Explicação: Mostra a Viscosidade (Real ou Aparente) vs Taxa. A inclinação negativa indica comportamento 'Shear Thinning' (pseudoplástico)."
        desc_modelos = f"Explicação: Comparação dos dados experimentais com os modelos. O melhor ajuste foi {self.analysis_data.get('best_model')}."
        desc_mod_visc = "Explicação: Comparação das curvas de viscosidade dos modelos ajustados em relação aos dados experimentais."

        self._plot_figure(t1, self._create_flow_curve(), desc_fluxo)
        self._plot_figure(t2, self._create_viscosity_curve(), desc_visc)
        self._plot_figure(t3, self._create_model_curve(), desc_modelos)
        self._plot_figure(t4, self._create_model_visc_curve(), desc_mod_visc)

    def _plot_figure(self, parent, fig, description=None):
        if description:
            lbl = ctk.CTkLabel(parent, text=description, font=ctk.CTkFont(slant="italic", size=11), wraplength=800)
            lbl.pack(side="bottom", fill="x", padx=10, pady=5)

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _create_flow_curve(self):
        import reologia_plot as rp
        d = self.analysis_data
        gd_brutos = np.array(d.get('raw_gamma', []))
        tau_brutos = np.array(d.get('raw_tau', []))
        gd_med = np.array(d['gamma_dot'])
        tau_med = np.array(d['tau_w'])
        tau_err = np.array(d.get('tau_w_std', np.zeros_like(tau_med)))

        bm = d.get('best_model')
        fit = d.get('model_fits', {}).get(bm, {}) if bm else {}

        if len(gd_med) > 0:
            gd_fit = np.logspace(np.log10(max(1e-3, min(gd_med))), np.log10(max(gd_med)), 100)
        else:
            gd_fit = np.array([1, 10, 100])

        tau_fit = np.zeros_like(gd_fit)
        texto = ""
        r2 = 0.0

        if bm and fit.get('params') is not None:
            func = models.MODELS[bm][0]
            tau_fit = func(gd_fit, *fit['params'])
            r2 = fit.get('r2', 0.0)
            p_n = fit.get('param_names', [])
            p_v = fit['params']
            texto = "\n".join([f"{n} = {v:.4g}" for n, v in zip(p_n, p_v)])

        ref_data = d.get('dados_referencia', None)
        fig, ax = rp.plotar_curva_fluxo(gd_brutos, tau_brutos, gd_med, tau_med, tau_err,
                              gd_fit, tau_fit, bm or "Nenhum ajustado", r2, texto, dados_referencia=ref_data)
        return fig

    def _create_viscosity_curve(self):
        import reologia_plot as rp
        d = self.analysis_data
        gd_brutos = np.array(d.get('raw_gamma', []))
        eta_brutos = np.array(d.get('raw_eta', []))
        # Use apparent viscosity as the main series (blue circles)
        gd_med = np.array(d.get('gamma_dot_app', d['gamma_dot']))
        eta_med = np.array(d.get('eta_app', d['eta']))
        eta_err = np.array(d.get('eta_std', np.zeros_like(eta_med)))
        n_p = d.get('n_prime', 1.0)

        ref_data = d.get('dados_referencia', None)
        fig, ax = rp.plotar_viscosidade(gd_brutos, eta_brutos, gd_med, eta_med, eta_err, n_prime=n_p if n_p != 1.0 else None, dados_referencia=ref_data)
        return fig

    def _get_models_list(self, d, gd_fit):
        mods = []
        fits = [(k, v) for k, v in d.get('model_fits', {}).items() if v.get('params') is not None]
        fits.sort(key=lambda x: x[1].get('r2', -99), reverse=True)
        for k, v in fits:
            func = models.MODELS[k][0]
            try:
                t_fit = func(gd_fit, *v['params'])
                p_n = v.get('param_names', [])
                p_v = v['params']
                p_str = " | ".join([f"{n}={val:.3g}" for n, val in zip(p_n, p_v)])
                mods.append({'nome': k, 'tau_fit': t_fit, 'r2': v.get('r2', 0), 'params': p_str})
            except Exception as e:
                print(f"Erro no modelo {k}: {e}")
        return mods

    def _create_model_curve(self):
        import reologia_plot as rp
        d = self.analysis_data
        gd_brutos = np.array(d.get('raw_gamma', []))
        tau_brutos = np.array(d.get('raw_tau', []))
        
        # Models are fitted on Apparent Shear Rate, so we must plot them against it
        gd_med = np.array(d.get('gamma_dot_app', d['gamma_dot']))
        tau_med = np.array(d['tau_w'])
        tau_err = np.array(d.get('tau_w_std', np.zeros_like(tau_med)))

        if len(gd_med) > 0:
            gd_fit = np.logspace(np.log10(max(1e-3, min(gd_med))), np.log10(max(gd_med)), 100)
        else:
            gd_fit = np.array([1, 10, 100])

        mods = self._get_models_list(d, gd_fit)
        ref_data = d.get('dados_referencia', None)
        fig, ax = rp.plotar_ajuste_modelos(gd_brutos, tau_brutos, gd_med, tau_med, tau_err, gd_fit, mods, dados_referencia=ref_data)
        return fig

    def _create_model_visc_curve(self):
        import reologia_plot as rp
        d = self.analysis_data
        gd_brutos = np.array(d.get('raw_gamma', []))
        eta_brutos = np.array(d.get('raw_eta', [])) # This contains apparent eta for raw points
        
        # Models are fitted on Apparent data, plot them against Apparent data
        gd_med = np.array(d.get('gamma_dot_app', d['gamma_dot']))
        eta_med = np.array(d.get('eta_app', d['eta']))
        eta_err = np.array(d.get('eta_std', np.zeros_like(eta_med)))

        if len(gd_med) > 0:
            gd_fit = np.logspace(np.log10(max(1e-3, min(gd_med))), np.log10(max(gd_med)), 100)
        else:
            gd_fit = np.array([1, 10, 100])

        mods = self._get_models_list(d, gd_fit)
        ref_data = d.get('dados_referencia', None)
        fig, ax = rp.plotar_ajuste_viscosidade(gd_brutos, eta_brutos, gd_med, eta_med, eta_err, gd_fit, mods, dados_referencia=ref_data)
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
