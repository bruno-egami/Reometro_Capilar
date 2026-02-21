import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import numpy as np
import json
from scipy.stats import linregress
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import datetime
import os

# Internal modules
from gui.utils import adjust_column_widths
from gui.windows.data_cleaning import DataCleaningWindow
from gui.windows.report import RelatorioWindow
from gui.windows.comparative import ComparativeAnalysisWindow
import modelos_reologicos as models
import reologia_fitting
import reologia_report_pdf

class AnaliseFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.db = controller.db
        
        self.label = ctk.CTkLabel(self, text="Análise Reológica Completa", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20, padx=20, anchor="w")
        
        # Selection Frame (Treeview)
        self.sel_frame = ctk.CTkFrame(self)
        self.sel_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(self.sel_frame, text="Selecione Amostra para Análise:").pack(anchor="w", padx=10, pady=5)
        
        # Treeview Scrollbar
        self.tree_frame = ctk.CTkFrame(self.sel_frame, height=150)
        self.tree_frame.pack(fill="x", padx=10, pady=5)
        
        cols = ("ID", "Nome", "Descrição", "D(mm)", "L(mm)", "Data", "Ensaios", "Status")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", height=8, selectmode="extended")
        
        self.tree.heading("ID", text="ID")
        self.tree.column("ID", width=40, anchor="center")
        self.tree.heading("Nome", text="Nome")
        self.tree.column("Nome", width=150)
        self.tree.heading("Descrição", text="Descrição")
        self.tree.column("Descrição", width=150)
        self.tree.heading("D(mm)", text="D (mm)")
        self.tree.column("D(mm)", width=60, anchor="center")
        self.tree.heading("L(mm)", text="L (mm)")
        self.tree.column("L(mm)", width=60, anchor="center")
        self.tree.heading("Data", text="Data")
        self.tree.column("Data", width=120, anchor="center")
        self.tree.heading("Ensaios", text="Ensaios")
        self.tree.column("Ensaios", width=70, anchor="center")
        self.tree.heading("Status", text="Status")
        self.tree.column("Status", width=80, anchor="center")
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Action Buttons
        self.actions_frame = ctk.CTkFrame(self.sel_frame)
        self.actions_frame.pack(fill="x", padx=10, pady=5)
        
        self.btn_load = ctk.CTkButton(self.actions_frame, text="Análise (Individual)", command=self.run_single_analysis, fg_color="blue")
        self.btn_load.pack(side="right", padx=10, pady=10)
        
        self.btn_batch = ctk.CTkButton(self.actions_frame, text="Análise em Lote", command=self.run_batch_analysis, fg_color="purple")
        self.btn_batch.pack(side="right", padx=10, pady=10)
        
        self.btn_compare = ctk.CTkButton(self.actions_frame, text="Visualizar Comparativo", command=self.run_comparative_analysis, fg_color="#2b5a2b")
        self.btn_compare.pack(side="right", padx=10, pady=10)
        
        self.btn_cleaning = ctk.CTkButton(self.actions_frame, text="Limpeza / Outliers", command=self.open_cleaning_window, fg_color="orange")
        self.btn_cleaning.pack(side="left", padx=10, pady=10)

        self.btn_delete_analise = ctk.CTkButton(self.actions_frame, text="Excluir Análise", command=self.delete_selected_analysis, fg_color="#8b0000")
        self.btn_delete_analise.pack(side="left", padx=10, pady=10)
        
        # Dummy Checkbox for Weissenberg (assumed True always based on code flow, or we create a hidden var)
        self.chk_weissenberg = ctk.BooleanVar(value=True)

        # Selection Bind
        self.tree.bind("<<TreeviewSelect>>", self.on_select_sample)
        
        # Options
        # Export Buttons Frame
        self.export_frame = ctk.CTkFrame(self)
        self.export_frame.pack(fill="x", padx=20, pady=5)
        
        self.btn_view_report = ctk.CTkButton(self.export_frame, text="Visualizar Relatório", 
                                             command=self.open_report_window, state="disabled", fg_color="orange")
        self.btn_view_report.pack(side="left", padx=10)
        
        self.btn_export_png = ctk.CTkButton(self.export_frame, text="Exportar Gráficos (PNG)", 
                                             command=self.export_graphs, state="disabled")
        self.btn_export_png.pack(side="left", padx=10)
        
        self.btn_export_pdf = ctk.CTkButton(self.export_frame, text="Gerar Relatório (PDF)", 
                                             command=self.export_pdf, state="disabled")
        self.btn_export_pdf.pack(side="left", padx=10)

        
        # Results (Scrollable Textbox - allows text selection)
        self.txt_result = ctk.CTkTextbox(self, height=350, font=("Consolas", 14), wrap="word")
        self.txt_result.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt_result.insert("1.0", "Selecione uma amostra na lista acima.")
        self.txt_result.configure(state="disabled") 
        
        # Store analysis data for export
        self.analysis_data = None
        self.selected_amostra_id = None
        
        self.refresh_list()

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        amostras = self.db.list_amostras()
        for a in amostras:
            # Check if analysis exists
            last_analysis = self.db.get_last_analise(a['id'])
            status = "Analisado" if last_analysis else "Pendente"
            
            # Count tests
            testes = self.db.get_ensaios_by_amostra(a['id'])
            num_testes = len(testes)
            
            self.tree.insert("", "end", iid=str(a['id']), values=(
                a['id'],
                a['nome'],
                a['descricao'],
                f"{a['d_capilar_mm']:.2f}", 
                f"{a['l_capilar_mm']:.2f}",
                a['data_criacao'],
                num_testes,
                status
            ))
            
        # UI optimization: adjust columns
        adjust_column_widths(self.tree)
        
    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        self.refresh_list()

    def on_select_sample(self, event):
        selected = self.tree.selection()
        if not selected: return
        
        amostra_id = int(selected[0])
        self.selected_amostra_id = amostra_id
        
        # Try to load existing analysis
        last_analysis = self.db.get_last_analise(amostra_id)
        if last_analysis:
            self.load_analysis_from_db(last_analysis)
        else:
            self._set_result("Amostra selecionada. Clique em 'Nova Análise' para processar.")
            self.analysis_data = None
            self.btn_export_png.configure(state="disabled")
            self.btn_export_pdf.configure(state="disabled")
            self.btn_view_report.configure(state="disabled")

    def load_analysis_from_db(self, analysis_row):
        """Reconstruct analysis data from database record."""
        import json
        
        try:
            params = json.loads(analysis_row['parametros_json'])
            # Auto-run calculation using visual indication
            self.run_analysis(auto=True)
            
            # Prepend info about source
            current_text = self.txt_result.get("1.0", "end")
            self._set_result(f"--- RESULTADO CARREGADO DO BANCO DE DADOS ({analysis_row['data_analise']}) ---\n\n" + current_text)
            
        except Exception as e:
            self._set_result(f"Erro ao carregar análise salva: {e}")
    
    def _set_result(self, text):
        """Update results textbox with text (selectable but read-only)."""
        self.txt_result.configure(state="normal")
        self.txt_result.delete("1.0", "end")
        self.txt_result.insert("1.0", text)
        self.txt_result.configure(state="disabled")

    def run_single_analysis(self):
        """Wrapper for button click to ensure specific selection behavior."""
        selected = self.tree.selection()
        if not selected:
            tk.messagebox.showwarning("Aviso", "Selecione pelo menos uma amostra na tabela.")
            return
        
        # For single analysis, we just run the first one if multiple selected
        self.selected_amostra_id = int(selected[0])
        self.run_analysis(auto=False)

    def run_batch_analysis(self):
        """Processes multiple selected samples in sequence."""
        selected = self.tree.selection()
        if not selected:
            tk.messagebox.showwarning("Aviso", "Selecione as amostras para análise em lote (use Ctrl+Click ou Shift+Click).")
            return
            
        count = len(selected)
        if not tk.messagebox.askyesno("Análise em Lote", f"Deseja processar {count} amostras em lote?\nOs resultados serão salvos automaticamente no banco de dados."):
            return
            
        summary = f"═══════════════════════════════════════════\n"
        summary += f"  RESUMO DA ANÁLISE EM LOTE ({count} itens)\n"
        summary += f"═══════════════════════════════════════════\n\n"
        
        success_count = 0
        
        for iid in selected:
            amostra_id = int(iid)
            result = self._perform_statistical_analysis(amostra_id, self.chk_weissenberg.get(), auto=False, save=True)
            
            if result['success']:
                success_count += 1
                summary += f"✓ {result['nome']}:\n"
                summary += f"  Melhor Modelo: {result['best_model']} (R²={result['best_r2']:.4f})\n"
                summary += f"  Comportamento: {result['comportamento']}\n\n"
            else:
                summary += f"✗ ID {amostra_id}: Erro - {result['error']}\n\n"
        
        summary += f"───────────────────────────────────────────\n"
        summary += f"PROCESSAMENTO CONCLUÍDO: {success_count}/{count} sucesso.\n"
        summary += f"───────────────────────────────────────────\n"
        
        self._set_result(summary)
        self.refresh_list()
        tk.messagebox.showinfo("Sucesso", f"Análise em lote concluída!\n{success_count} amostras processadas.")

    def run_comparative_analysis(self):
        """Prepares and opens the comparative analysis window."""
        selected = self.tree.selection()
        if not selected:
            tk.messagebox.showwarning("Aviso", "Selecione pelo menos uma amostra para comparação.")
            return
            
        dataset_list = []
        for iid in selected:
            amostra_id = int(iid)
            # Try to load existing or process on-the-fly
            result = self._perform_statistical_analysis(amostra_id, aplicar_weissenberg=True, auto=True, save=False)
            if result['success']:
                dataset_list.append({
                    'id': amostra_id,
                    'nome': result['nome'],
                    'data': result['data']
                })

        if not dataset_list:
            tk.messagebox.showerror("Erro", "Não foi possível carregar dados para as amostras selecionadas.")
            return
            
        ComparativeAnalysisWindow(self, dataset_list)

    def run_analysis(self, auto=False):
        """Main method for single sample analysis with full UI update."""
        if not self.selected_amostra_id:
            return

        # Force Weissenberg correction
        result = self._perform_statistical_analysis(self.selected_amostra_id, aplicar_weissenberg=True, auto=auto, save=not auto)
        
        if result['success']:
            self._set_result(result['text'])
            self.analysis_data = result['data']
            self.btn_export_png.configure(state="normal")
            self.btn_export_pdf.configure(state="normal")
            self.btn_view_report.configure(state="normal")
            
            # Atualiza o status na tabela para "Analisado" dinamicamente para preservar selecao
            if not auto:
                item_iid = str(self.selected_amostra_id)
                if self.tree.exists(item_iid):
                    vals = list(self.tree.item(item_iid, "values"))
                    if len(vals) >= 8:
                        vals[7] = "Analisado"
                        self.tree.item(item_iid, values=vals)
        else:
            if not auto: tk.messagebox.showerror("Erro na Análise", result['error'])
            self._set_result(f"Erro: {result['error']}")

    def open_cleaning_window(self):
        """Opens the data points management and outlier removal window."""
        selected = self.tree.selection()
        if not selected:
            tk.messagebox.showwarning("Aviso", "Selecione uma amostra para limpeza de dados.")
            return
            
        amostra_id = int(selected[0])
        DataCleaningWindow(self, self.db, amostra_id, on_save_callback=lambda: self.run_analysis(auto=True))

    def delete_selected_analysis(self):
        """Deletes the specific analysis for the selected sample."""
        selected = self.tree.selection()
        if not selected:
            tk.messagebox.showwarning("Aviso", "Selecione uma amostra para remover a análise.")
            return
        
        amostra_id = int(selected[0])
        amostra_nome = self.tree.item(selected[0], "values")[1]
        
        # Check if analysis exists
        last_analysis = self.db.get_last_analise(amostra_id)
        if not last_analysis:
            tk.messagebox.showinfo("Informação", "Não há análise salva para esta amostra.")
            return

        if tk.messagebox.askyesno("Confirmar Exclusão", f"Deseja realmente excluir a análise da amostra '{amostra_nome}'?\n\nA amostra e os ensaios brutos serão preservados."):
            if self.db.delete_all_analises(amostra_id):
                tk.messagebox.showinfo("Sucesso", "Análise excluída com sucesso.")
                
                # Atualiza o status na tabela para "Pendente" dinamicamente
                item_iid = str(amostra_id)
                if self.tree.exists(item_iid):
                    vals = list(self.tree.item(item_iid, "values"))
                    if len(vals) >= 8:
                        vals[7] = "Pendente"
                        self.tree.item(item_iid, values=vals)
                
                self._set_result("Análise removida. A amostra continua disponível para novo processamento.")
                self.analysis_data = None
                self.btn_export_png.configure(state="disabled")
                self.btn_export_pdf.configure(state="disabled")
                self.btn_view_report.configure(state="disabled")
            else:
                tk.messagebox.showerror("Erro", "Falha ao excluir análise.")

    def _perform_statistical_analysis(self, amostra_id, aplicar_weissenberg, auto=False, save=True):
        """
        Isolated reological logic.
        Returns a dictionary with results, status and data.
        """
        
        try:
            # Fetch fresh from DB
            amostras = self.db.list_amostras()
            amostra = next((a for a in amostras if a['id'] == amostra_id), None)
            
            if not amostra: 
                return {'success': False, 'error': "Amostra não encontrada.", 'id': amostra_id}

            nome = amostra['nome']
            # Fetch ONLY active points
            df = self.db.get_ensaios_by_amostra(amostra['id'], apenas_ativos=True)
            
            if df.empty:
                return {'success': False, 'error': "Sem ensaios para esta amostra.", 'id': amostra_id, 'nome': nome}

            D_mm = amostra['d_capilar_mm']
            L_mm = amostra['l_capilar_mm']
            Rho = amostra['densidade_g_cm3']
            
            R = (D_mm / 2.0) / 1000.0
            L = L_mm / 1000.0
            
            gamma_dots_app = []
            taus = []
            delta_p_list = []
            massas = []
            tempos = []
            pressoes = []
            
            for index, row in df.iterrows():
                massa_g = row['massa_g']
                tempo_s = row['duracao_s']
                p_pasta_bar = row['pressao_pasta_bar']
                p_linha_bar = row['pressao_linha_bar']
                
                if tempo_s <= 0 or massa_g <= 0 or p_pasta_bar <= 0: continue
                
                delta_p = p_linha_bar - p_pasta_bar
                delta_p_list.append(delta_p)
                massas.append(massa_g)
                tempos.append(tempo_s)
                pressoes.append(p_pasta_bar)
                
                Q_cm3s = massa_g / (Rho * tempo_s)
                Q_m3s = Q_cm3s * 1e-6
                p_pa = p_pasta_bar * 1e5
                
                gd_app = (4 * Q_m3s) / (np.pi * R**3)
                tau_w = (p_pa * R) / (2 * L)
                
                gamma_dots_app.append(gd_app)
                taus.append(tau_w)
                
            if len(gamma_dots_app) < 3:
                return {'success': False, 'error': "Mínimo 3 pontos necessários.", 'id': amostra_id, 'nome': nome}

            gd_app_arr = np.array(gamma_dots_app)
            tau_arr = np.array(taus)
            
            # --- M5: Propagação de Incerteza Metrológica ---
            # Incertezas padrão dos instrumentos
            u_R = 0.025e-3   # 0.025 mm (paquímetro digital) em metros
            u_L = 0.05e-3    # 0.05 mm em metros
            u_P_rel = 0.02   # 2% fundo de escala do sensor (classe C)
            u_m_kg = 0.01e-3 # 0.01 g em kg
            u_t = 0.2        # 0.2 s (trigger manual)
            
            # u(tau_w) / tau_w = sqrt( (u_P/P)^2 + (u_R/R)^2 + (u_L/L)^2 )
            u_tau_arr = tau_arr * np.sqrt(
                u_P_rel**2 + (u_R / R)**2 + (u_L / L)**2
            )
            # u(gd) / gd = sqrt( (u_m/m)^2 + (u_t/t)^2 + (3*u_R/R)^2 )
            massas_kg = np.array(massas) / 1000.0
            tempos_arr = np.array(tempos)
            u_gd_arr = gd_app_arr * np.sqrt(
                (u_m_kg / massas_kg)**2 + (u_t / tempos_arr)**2 + (3 * u_R / R)**2
            )
            
            # Corrections (Weissenberg) performed on RAW data first
            n_prime = 1.0
            gd_true_arr = gd_app_arr.copy()
            
            if aplicar_weissenberg and len(gd_app_arr) >= 3:
                try:
                    log_gd = np.log(gd_app_arr)
                    log_tau = np.log(tau_arr)
                    
                    # --- M3/M4: Weissenberg-Rabinowitsch Local ---
                    # Usa gradiente (derivada central) no lugar do ajuste global
                    # Para bordas, o numpy faz derivada unilateral aproximada
                    local_n_primes = np.gradient(log_tau, log_gd)
                    
                    # Guarda limitadora (M4): 0.05 <= n' <= 3.0
                    local_n_primes = np.clip(local_n_primes, 0.05, 3.0)
                    
                    # Correção ponto a ponto
                    gd_true_arr = gd_app_arr * ((3 * local_n_primes + 1) / (4 * local_n_primes))
                    
                    # Para logs de relatórios ou fit global secundário (falso-n_prime),
                    # podemos expor a média do log derivado como 'n_prime' global
                    n_prime = np.mean(local_n_primes)
                    
                except Exception as e:
                    print(f"Erro no Weissenberg-Rabinowitsch local: {e}")
                    gd_true_arr = gd_app_arr.copy()
                
            eta_arr = tau_arr / gd_true_arr
            
            # --- STATISTICAL GROUPING ---
            try:
                # Create DataFrame for statistical grouping
                df_calc = pd.DataFrame({
                    'gamma_dot': gd_true_arr, # True Shear Rate
                    'tau_w': tau_arr,
                    'eta': eta_arr, # True Viscosity
                    'gamma_dot_app': gd_app_arr, # Apparent Shear Rate
                    'eta_app': tau_arr / gd_app_arr, # Apparent Viscosity
                    'massa_g': np.array(massas),
                    'tempo_s': np.array(tempos),
                    'pressao': np.array(pressoes)
                })
                # Group by log of shear rate (rounded to 1 decimal)
                df_calc['log_gd'] = np.round(np.log10(df_calc['gamma_dot']), 1)
                
                grouped = df_calc.groupby('log_gd')
                
                # Extract vectors for fitting and plotting (Means)
                gd_mean = grouped['gamma_dot'].mean().values
                tau_mean = grouped['tau_w'].mean().values
                tau_std = grouped['tau_w'].std().fillna(0).values
                eta_mean = grouped['eta'].mean().values
                eta_std = grouped['eta'].std().fillna(0).values
                
                # Additional Means for Report
                gd_app_mean = grouped['gamma_dot_app'].mean().values
                eta_app_mean = grouped['eta_app'].mean().values
                pressao_mean = grouped['pressao'].mean().values # Ensure this is calculated
                tempo_mean = grouped['tempo_s'].mean().values
                massa_mean = grouped['massa_g'].mean().values
                
                # --- Advanced Statistics (CVs) ---
                # Avoid division by zero
                with np.errstate(divide='ignore', invalid='ignore'):
                    cv_tau = np.where(tau_mean > 0, (tau_std / tau_mean) * 100.0, 0.0)
                    cv_eta = np.where(eta_mean > 0, (eta_std / eta_mean) * 100.0, 0.0)
                    
                    # Gamma CV (using True Shear Rate std)
                    gd_std = grouped['gamma_dot'].std().fillna(0).values
                    cv_gamma = np.where(gd_mean > 0, (gd_std / gd_mean) * 100.0, 0.0)

                # Weighted Global Metrics (Weighted by Shear Stress)
                total_stress = np.sum(tau_mean)
                if total_stress > 0:
                    cv_tau_global = np.sum(cv_tau * tau_mean) / total_stress
                    cv_eta_global = np.sum(cv_eta * tau_mean) / total_stress
                    cv_gamma_global = np.sum(cv_gamma * tau_mean) / total_stress
                else:
                    cv_tau_global = np.mean(cv_tau)
                    cv_eta_global = np.mean(cv_eta)
                    cv_gamma_global = np.mean(cv_gamma)
                    
                cv_tau_max = np.max(cv_tau) if len(cv_tau) > 0 else 0.0
                
                # Qualitative Assessment Text
                parecer_texto = "1. REPRODUTIBILIDADE DA TENSÃO (tau_w):\n"
                if cv_tau_global < 1.0:
                    parecer_texto += f"  * RESULTADO: Excelente ({cv_tau_global:.2f}%). Alta reprodutibilidade.\n"
                elif cv_tau_global < 5.0:
                    parecer_texto += f"  * RESULTADO: Bom ({cv_tau_global:.2f}%). Variação aceitável.\n"
                else:
                    parecer_texto += f"  * RESULTADO: Atenção ({cv_tau_global:.2f}%). Dispersão considerável.\n"
                    
                parecer_texto += "\n2. ESTABILIDADE DA VISCOSIDADE (eta):\n"
                if cv_eta_global < 5.0:
                    parecer_texto += f"  * RESULTADO: Alta Estabilidade ({cv_eta_global:.2f}%).\n"
                elif cv_eta_global < 10.0:
                    parecer_texto += f"  * RESULTADO: Estabilidade Aceitável ({cv_eta_global:.2f}%).\n"
                else:
                    parecer_texto += f"  * RESULTADO: Baixa Estabilidade ({cv_eta_global:.2f}%).\n"

                # Prepare Raw Values String List for Report
                sorted_keys = sorted(grouped.groups.keys())
                raw_values_clean = []
                for k in sorted_keys:
                    vals = grouped.get_group(k)['tau_w'].values
                    vals_str = ", ".join([f"{v:.1f}" for v in vals])
                    raw_values_clean.append(vals_str)
                
                # Build stats_details dictionary
                stats_details = {
                    'df_cv': pd.DataFrame({
                        'tau_w_mean': tau_mean,
                        'tau_w_std': tau_std,
                        'cv_tau': cv_tau,
                        'gamma_dot_w_mean': gd_mean,
                        'cv_gamma': cv_gamma,
                        'cv_eta': cv_eta,
                        'tempo_mean': tempo_mean,
                        'massa_mean': massa_mean,
                        'raw_values': raw_values_clean,
                        'num_points': [len(grouped.get_group(k)) for k in sorted_keys]
                    }),
                    'metrics': {
                        'cv_tau_global': cv_tau_global,
                        'cv_gamma_global': cv_gamma_global,
                        'cv_eta_global': cv_eta_global,
                        'cv_tau_max': cv_tau_max,
                        'num_pontos': len(tau_mean)
                    },
                    'parecer': parecer_texto
                }

                # Use MEANS for model fitting
                fit_gd = gd_mean
                fit_tau = tau_mean
                
            except Exception as e:
                # Fallback to raw data if grouping fails
                print(f"Error in grouping: {e}")
                fit_gd = gd_true_arr
                fit_tau = tau_arr
                gd_mean, tau_mean, eta_mean = gd_true_arr, tau_arr, eta_arr
                tau_std, eta_std = np.zeros_like(tau_arr), np.zeros_like(eta_arr)
                stats_details = None

            # Model Fitting (Weighted by standard deviation - WLS)
            model_fits = {}
            best_model = None
            best_r2 = -np.inf
            best_aic = np.inf
            
            n_pts = len(fit_gd)
            from scipy.stats import t
            
            # Prepare Sigma for WLS
            # Avoid zeroes in sigma, replace with a small value or mean of std
            valid_std = tau_std[tau_std > 0]
            sigma_wls = None
            if len(valid_std) > 0:
                min_std = np.min(valid_std)
                # Replace zeros with a fraction of the minimum valid std to give them high but not infinite weight
                sigma_wls = np.where(tau_std == 0, min_std * 0.1, tau_std)
            
            for m_name, (m_func, p_names, g_func, bnds) in models.MODELS.items():
                try:
                    p0 = g_func(fit_gd, fit_tau)
                    # Fit to means (WLS if sigma is available)
                    if sigma_wls is not None:
                        popt, pcov = curve_fit(m_func, fit_gd, fit_tau, p0=p0, bounds=bnds, sigma=sigma_wls, absolute_sigma=False, maxfev=10000)
                    else:
                        popt, pcov = curve_fit(m_func, fit_gd, fit_tau, p0=p0, bounds=bnds, maxfev=10000)
                    
                    tau_pred = m_func(fit_gd, *popt)
                    r2 = r2_score(fit_tau, tau_pred)
                    
                    # M6: Calculo de AIC/BIC
                    rss = np.sum((fit_tau - tau_pred)**2)
                    k = len(popt)
                    rss_safe = rss if rss > 1e-10 else 1e-10
                    aic_val = 2*k + n_pts * np.log(rss_safe/n_pts)
                    bic_val = k * np.log(n_pts) + n_pts * np.log(rss_safe/n_pts)
                    
                    # M7: Intervalo de Confianca 95% usando pcov
                    ic_dict = {}
                    if not np.isinf(pcov).all():
                        dof = max(1, n_pts - k)
                        t_val = t.ppf(0.975, dof)
                        std_errs = np.sqrt(np.diag(pcov))
                        for idx, p_n in enumerate(p_names):
                            ic_dict[p_n] = t_val * std_errs[idx]
                    
                    model_fits[m_name] = {'params': popt, 'r2': r2, 'aic': aic_val, 'bic': bic_val, 'ic': ic_dict, 'param_names': p_names}
                    
                    # OLS modificado para AIC (Menor e melhor)
                    if aic_val < best_aic:
                        best_aic = aic_val
                        best_model = m_name
                        best_r2 = r2
                        
                except Exception as e:
                    model_fits[m_name] = {'params': None, 'r2': None, 'error': str(e)}

            # Generate Text Result
            results_txt = f"═══════════════════════════════════════════\n"
            results_txt += f"  RESULTADO DA ANÁLISE: {nome}\n"
            results_txt += f"═══════════════════════════════════════════\n\n"
            
            # M12: Aviso de confiabilidade do modelo para poucos grupos de cisalhamento
            if len(fit_gd) < 4:
                results_txt += "⚠️ AVISO M12: O número de grupos de taxa de cisalhamento estabilizados é menor que 4.\n"
                results_txt += "O ajuste dos modelos reológicos pode estar superdeterminado ou impreciso.\n"
                results_txt += "Recomenda-se realizar mais ensaios em gradientes de base.\n\n"
                
            results_txt += f"1. TRATAMENTO DE SINAL (Regime Estacionário)\n"
            results_txt += f"  - Pontos Estáveis Coletados: {len(gd_true_arr)}\n"
            results_txt += f"Capilar: D={D_mm} mm, L={L_mm} mm\n"
            results_txt += f"Densidade: {Rho} g/cm³\n"
            results_txt += f"Pontos Agrupados: {len(fit_gd)} níveis de taxa\n"
            results_txt += f"Correção Weissenberg: {'Sim (n\'={:.3f})'.format(n_prime) if aplicar_weissenberg else 'Não'}\n\n"
            
            results_txt += "───────────────────────────────────────────\n"
            results_txt += "  AJUSTE DOS MODELOS (MÉDIAS)\n"
            results_txt += "───────────────────────────────────────────\n\n"
            
            for m_name, fit_data in model_fits.items():
                if fit_data.get('params') is not None:
                    marker = "★" if m_name == best_model else " "
                    results_txt += f"{marker} {m_name} (R²={fit_data['r2']:.4f}, AIC={fit_data.get('aic', 0):.1f})\n"
                    for i, pn in enumerate(fit_data['param_names']):
                        margin = fit_data.get('ic', {}).get(pn, 0.0)
                        marg_str = f" ± {margin:.2g}" if margin > 0 else ""
                        results_txt += f"    {pn}: {fit_data['params'][i]:.4g}{marg_str}\n"
                results_txt += "\n"
            
            comportamento = reologia_fitting.inferir_comportamento_fluido(best_model, 
                {best_model: {'params': model_fits[best_model]['params'], 'R2': best_r2}} if best_model else {})
            
            results_txt += f"───────────────────────────────────────────\n"
            results_txt += f"  COMPORTAMENTO: {comportamento}\n"
            results_txt += f"───────────────────────────────────────────\n"

            # Prepare data object (Storing means as primary data, raw as secondary)
            analysis_data = {
                'amostra': amostra, 
                'gamma_dot': gd_mean, 'tau_w': tau_mean, 'eta': eta_mean, # Means
                'gamma_dot_std': np.zeros_like(gd_mean), # Assume negligible x-error for now or calc it
                'tau_w_std': tau_std, 'eta_std': eta_std, # Standard Deviations
                'raw_gamma': gd_true_arr, 'raw_tau': tau_arr, 'raw_eta': eta_arr, # Raw Data
                'raw_mass': np.array(massas), 'raw_time': np.array(tempos), 'raw_pressure': np.array(pressoes),
                'u_tau': u_tau_arr, 'u_gd': u_gd_arr, # M5: Incertezas metrológicas
                'model_fits': model_fits, 'best_model': best_model, 'best_r2': best_r2,
                'comportamento': comportamento, 'n_prime': n_prime if aplicar_weissenberg else 1.0,
                'delta_p': np.array(delta_p_list),
                'pressao_mean': pressao_mean if stats_details else np.array(delta_p_list), # Fallback if no stats
                'stats_details': stats_details
            }

            if save:
                params_storage = {
                    'best_model': best_model, 'n_prime': n_prime, 'is_weissenberg': aplicar_weissenberg,
                    'statistical_treatment': {
                        'method': 'grouped_by_shear_rate_log',
                        'num_groups': len(fit_gd),
                        'original_points': len(gd_true_arr)
                    },
                    'fits': {m: {'params': f['params'].tolist() if f['params'] is not None else None, 
                                 'r2': f['r2']} for m, f in model_fits.items()}
                }
                self.db.add_analise(amostra_id, best_model, best_r2, n_prime if aplicar_weissenberg else 1.0, 
                                   comportamento, json.dumps(params_storage))

            return {
                'success': True, 'text': results_txt, 'data': analysis_data, 
                'nome': nome, 'best_model': best_model, 'best_r2': best_r2, 
                'comportamento': comportamento
            }

        except Exception as e:
            return {'success': False, 'error': str(e), 'id': amostra_id}

    def open_report_window(self):
        if not self.analysis_data:
            tk.messagebox.showwarning("Aviso", "Execute a análise primeiro.")
            return
        
        # Capture current data for the callback
        current_data = self.analysis_data
        RelatorioWindow(self, current_data, export_callback=lambda: self.export_pdf(current_data))
    
    def export_graphs(self):
        """Export analysis graphs as PNG files."""
        import reologia_plot as rp
        import matplotlib.pyplot as plt
        
        if not self.analysis_data:
            tk.messagebox.showerror("Erro", "Execute uma análise primeiro.")
            return
        
        # Ask for folder
        folder = filedialog.askdirectory(title="Selecione pasta para salvar gráficos")
        if not folder:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        d = self.analysis_data
        amostra_nome = d['amostra']['nome']
        
        imgs_generated = []
        
        # Helper to extract variables
        gd_brutos = np.array(d.get('raw_gamma', []))
        tau_brutos = np.array(d.get('raw_tau', []))
        eta_brutos = np.array(d.get('raw_eta', []))
        
        gd_med = np.array(d['gamma_dot'])
        tau_med = np.array(d['tau_w'])
        eta_med = np.array(d['eta'])
        
        tau_err = np.array(d.get('tau_w_std', np.zeros_like(tau_med)))
        eta_err = np.array(d.get('eta_std', np.zeros_like(eta_med)))
        
        bm = d.get('best_model')
        fit = d.get('model_fits', {}).get(bm, {}) if bm else {}
        
        if len(gd_med) > 0:
            gd_fit = np.logspace(np.log10(max(1e-3, min(gd_med))), np.log10(max(gd_med)), 100)
        else:
            gd_fit = np.array([1, 10, 100])
        
        # 1. Flow Curve
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
            
        fig1, _ = rp.plotar_curva_fluxo(gd_brutos, tau_brutos, gd_med, tau_med, tau_err,
                              gd_fit, tau_fit, bm or "Nenhum", r2, texto, titulo=f'Curva de Fluxo - {amostra_nome}')
        path1 = f"{folder}/{timestamp}_{amostra_nome}_curva_fluxo.png"
        fig1.savefig(path1, dpi=300, bbox_inches='tight')
        plt.close(fig1)
        imgs_generated.append(path1)
        
        # 2. Viscosity Curve
        n_p = d.get('n_prime', 1.0)
        fig2, _ = rp.plotar_viscosidade(gd_brutos, eta_brutos, gd_med, eta_med, eta_err, n_prime=n_p if n_p != 1.0 else None, titulo=f'Viscosidade - {amostra_nome}')
        path2 = f"{folder}/{timestamp}_{amostra_nome}_viscosidade.png"
        fig2.savefig(path2, dpi=300, bbox_inches='tight')
        plt.close(fig2)
        imgs_generated.append(path2)
        
        # 3. All Models
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
            except: pass
            
        fig3, _ = rp.plotar_ajuste_modelos(gd_brutos, tau_brutos, gd_med, tau_med, tau_err, gd_fit, mods, titulo=f'Comparação de Modelos - {amostra_nome}')
        path3 = f"{folder}/{timestamp}_{amostra_nome}_modelos.png"
        fig3.savefig(path3, dpi=300, bbox_inches='tight')
        plt.close(fig3)
        imgs_generated.append(path3)
        
        tk.messagebox.showinfo("Sucesso", f"{len(imgs_generated)} gráficos exportados para:\n{folder}")
    
    def export_pdf(self, analysis_data=None):
        """Export analysis as PDF report."""
        
        # Use provided data or current data
        data_to_use = analysis_data if analysis_data else self.analysis_data
        
        if not data_to_use:
            tk.messagebox.showerror("Erro", "Execute uma análise primeiro.")
            return
        
        if not reologia_report_pdf.PDF_AVAILABLE:
            tk.messagebox.showerror("Erro", "Biblioteca FPDF não instalada.\nExecute: pip install fpdf")
            return
        
        # Get sample name for suggested filename
        amostra = data_to_use['amostra']
        nome_amostra = amostra['nome'].replace(' ', '_').replace('%', 'pct')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_name = f"Relatorio_{nome_amostra}_{timestamp}.pdf"
        
        # Ask for file location
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf", 
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=suggested_name,
            title="Salvar Relatório PDF"
        )
        
        if not filepath: return
        
        folder = os.path.dirname(filepath)
        
        try:
            # Generate graphs in TEMP folder to avoid cluttering user directory
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            try:
                self._generate_temp_graphs(temp_dir, timestamp, data_to_use)
                
                # Prepare data (Statistical Means + StdDevs)
                # Use data_to_use (which might be passed arg) instead of self.analysis_data directly
                df_res = pd.DataFrame({
                    'Taxa Cisalhamento (s-1)': data_to_use['gamma_dot'],
                    'Tensao Cisalhamento (Pa)': data_to_use['tau_w'],
                    'Desvio Padrao Tensao (Pa)': data_to_use.get('tau_w_std', np.zeros_like(data_to_use['tau_w'])),
                    'Viscosidade (Pa.s)': data_to_use['eta'],
                    'Desvio Padrao Viscosidade (Pa.s)': data_to_use.get('eta_std', np.zeros_like(data_to_use['eta']))
                })
                
                # Prepare Raw Data (All Active Points) - Restored from Block 1
                df_raw_data = pd.DataFrame({
                    'gamma_dot_w': data_to_use.get('raw_gamma', []),
                    'tau_w': data_to_use.get('raw_tau', []),
                    'eta_true': data_to_use.get('raw_eta', []),
                    'delta_p': data_to_use.get('delta_p', []),
                    'tempo_s': data_to_use.get('raw_time', []),
                    'massa_g': data_to_use.get('raw_mass', []),
                    'pressao': data_to_use.get('raw_pressure', [])
                })
                
                # Prepare model summary
                summary_list = []
                for model_name, fit_data in data_to_use['model_fits'].items():
                    if fit_data.get('params') is not None:
                        param_names = fit_data['param_names']
                        params_str = ", ".join([f"{n}={v:.4g}" for n, v in zip(param_names, fit_data['params'])])
                        summary_list.append({'Modelo': model_name, 'R2': fit_data['r2'], 'Parametros': params_str})
                df_sum_modelo = pd.DataFrame(summary_list).sort_values(by='R2', ascending=False)
                
                lista_imgs = [os.path.join(temp_dir, f"{timestamp}_curva_fluxo.png"),
                              os.path.join(temp_dir, f"{timestamp}_viscosidade.png"),
                              os.path.join(temp_dir, f"{timestamp}_modelos_fluxo.png"),
                              os.path.join(temp_dir, f"{timestamp}_modelos_visc.png")]
                
                # Prepare Outlier Dataframe for Report - From Block 2
                df_outliers_report = None
                try:
                    # Use selected_amostra_id from controller if matches data
                    # Or better: data_to_use['amostra']['id']
                    amostra_id = data_to_use['amostra']['id']
                    
                    query_out = """
                        SELECT gamma_dot_w, tau_w, eta_true, tempo_s, 
                               NULL as limite_inf, NULL as limite_sup, -- Placeholder if limits not stored per point
                               ' IQR / Manual' as motivo
                        FROM pontos_ensaio 
                        WHERE amostra_id = ? AND (ativo = 0 OR outlier = 1)
                    """
                    rows_out = self.db.fetch_all(query_out, (amostra_id,))
                    if rows_out:
                        df_outliers_report = pd.DataFrame(rows_out, columns=['gamma_dot_w', 'tau_w', 'eta_true', 'tempo_s', 'Limite Inf', 'Limite Sup', 'motivo'])
                except Exception as ex_out:
                    print(f"Erro ao buscar outliers: {ex_out}")

                reologia_report_pdf.gerar_pdf(
                    timestamp_str=timestamp,
                    rho_g_cm3=data_to_use['amostra']['densidade_g_cm3'],
                    tempo_extrusao_info="Variavel",
                    metodo_entrada="Média Estatística",
                    json_files=[],
                    csv_path="",
                    realizar_bagley=False,
                    D_bagley=data_to_use['amostra']['d_capilar_mm'],
                    L_bagley_list=[data_to_use['amostra']['l_capilar_mm']],
                    realizar_mooney=False,
                    L_mooney=data_to_use['amostra']['l_capilar_mm'],
                    D_mooney_list=[data_to_use['amostra']['d_capilar_mm']],
                    D_unico=data_to_use['amostra']['d_capilar_mm'],
                    L_unico=data_to_use['amostra']['l_capilar_mm'],
                    calib_path="",
                    df_res=df_res,
                    df_sum_modelo=df_sum_modelo,
                    best_model_nome=data_to_use['best_model'],
                    comportamento=data_to_use['comportamento'],
                    lista_imgs=lista_imgs,
                    output_folder=folder,
                    fator_calibracao=1.0,
                    output_filename=filepath,
                    df_raw_data=df_raw_data,
                    stats_details=data_to_use.get('stats_details'),
                    df_outliers=df_outliers_report,
                    amostra_info=data_to_use['amostra']
                )
                tk.messagebox.showinfo("Sucesso", f"Relatório PDF gerado em:\n{filepath}")
                
            finally:
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(tb)
            tk.messagebox.showerror("Erro ao Gerar PDF", f"Falha na geração do relatório:\n{e}\n\nDetalhes no console.")
    
    def _generate_temp_graphs(self, folder, timestamp, analysis_data=None):
        """Generate temporary graphs for PDF report."""
        import reologia_plot as rp
        import matplotlib.pyplot as plt
        import modelos_reologicos as models
        import numpy as np
        import os
        
        data = analysis_data if analysis_data else self.analysis_data
        
        gamma = np.array(data['gamma_dot'])
        tau = np.array(data['tau_w'])
        eta = np.array(data['eta'])
        
        tau_err = np.array(data.get('tau_w_std', np.zeros_like(tau)))
        eta_err = np.array(data.get('eta_std', np.zeros_like(eta)))
        
        gd_raw = np.array(data.get('raw_gamma', []))
        tau_raw = np.array(data.get('raw_tau', []))
        eta_raw = np.array(data.get('raw_eta', []))
        
        bm = data.get('best_model')
        fit = data.get('model_fits', {}).get(bm, {}) if bm else {}
        n_prime = data.get('n_prime', 1.0)
        
        # Cria dominio suave para plot de modelos
        if len(gamma) > 0:
            gd_fit = np.logspace(np.log10(max(1e-3, gamma.min())), np.log10(gamma.max()), 100)
        else:
            gd_fit = np.array([1, 10, 100])
        
        # 1. Curva de Fluxo
        tau_fit = np.zeros_like(gd_fit)
        texto = ''
        r2 = 0.0
        if bm and fit.get('params') is not None:
            tau_fit = models.MODELS[bm][0](gd_fit, *fit['params'])
            r2 = fit.get('r2', 0.0)
            texto = '\n'.join([f'{n}={v:.4g}' for n, v in zip(fit['param_names'], fit['params'])])
            
        fig1, _ = rp.plotar_curva_fluxo(gd_raw, tau_raw, gamma, tau, tau_err, gd_fit, tau_fit, bm or 'Nenhum', r2, texto)
        fig1.savefig(os.path.join(folder, f'{timestamp}_curva_fluxo.png'), dpi=150, bbox_inches='tight')
        plt.close(fig1)
        
        # 2. Viscosidade
        fig2, _ = rp.plotar_viscosidade(gd_raw, eta_raw, gamma, eta, eta_err, n_prime=n_prime if n_prime != 1.0 else None)
        fig2.savefig(os.path.join(folder, f'{timestamp}_viscosidade.png'), dpi=150, bbox_inches='tight')
        plt.close(fig2)
        
        # 3 e 4. Modelos Comparativos
        fits_sorted = sorted([(k, v) for k, v in data.get('model_fits', {}).items() if v.get('params') is not None],
                             key=lambda x: x[1].get('r2', -99), reverse=True)
        mods = []
        for k, v in fits_sorted:
            try:
                t_fit = models.MODELS[k][0](gd_fit, *v['params'])
                p_str = ' | '.join([f'{nm}={val:.3g}' for nm, val in zip(v['param_names'], v['params'])])
                mods.append({'nome': k, 'tau_fit': t_fit, 'r2': v.get('r2', 0), 'params': p_str})
            except Exception:
                pass
                
        fig3, _ = rp.plotar_ajuste_modelos(gd_raw, tau_raw, gamma, tau, tau_err, gd_fit, mods)
        fig3.savefig(os.path.join(folder, f'{timestamp}_modelos_fluxo.png'), dpi=150, bbox_inches='tight')
        plt.close(fig3)
        
        fig4, _ = rp.plotar_ajuste_viscosidade(gd_raw, eta_raw, gamma, eta, eta_err, gd_fit, mods)
        fig4.savefig(os.path.join(folder, f'{timestamp}_modelos_visc.png'), dpi=150, bbox_inches='tight')
        plt.close(fig4)
