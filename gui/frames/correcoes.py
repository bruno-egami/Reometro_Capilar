import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np

class CorrecoesFrame(ctk.CTkFrame):
    """Frame para correções avançadas de Bagley e Mooney."""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.db = controller.db
        self.selected_samples = {}  # {nome: {id, d_mm, l_mm, ...}}
        
        # Title
        self.label = ctk.CTkLabel(self, text="Correções Avançadas (Bagley/Mooney)", 
                                   font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20, padx=20, anchor="w")
        
        # Options Frame
        self.opt_frame = ctk.CTkFrame(self)
        self.opt_frame.pack(fill="x", padx=20, pady=10)
        
        self.chk_bagley = ctk.CTkCheckBox(self.opt_frame, text="Aplicar Correção de Bagley (mesmo D, diferentes L)")
        self.chk_bagley.pack(side="left", padx=10)
        self.chk_bagley.select()
        
        self.chk_mooney = ctk.CTkCheckBox(self.opt_frame, text="Aplicar Correção de Mooney (mesmo L, diferentes D)")
        self.chk_mooney.pack(side="left", padx=10)
        
        # Sample Selection Frame
        self.sel_frame = ctk.CTkFrame(self)
        self.sel_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(self.sel_frame, text="Selecione as amostras (mínimo 2 para cada correção):", 
                     font=ctk.CTkFont(size=14)).pack(anchor="w", padx=10, pady=5)
        
        # Treeview for sample selection
        self.tree_container = ctk.CTkFrame(self.sel_frame)
        self.tree_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        cols = ("Sel", "Nome", "D (mm)", "L (mm)", "Densidade", "Ensaios")
        self.tree = ttk.Treeview(self.tree_container, columns=cols, show="headings", selectmode="extended")
        
        self.tree.heading("Sel", text="✓")
        self.tree.column("Sel", width=30)
        self.tree.heading("Nome", text="Nome")
        self.tree.column("Nome", width=200)
        self.tree.heading("D (mm)", text="D (mm)")
        self.tree.column("D (mm)", width=80)
        self.tree.heading("L (mm)", text="L (mm)")
        self.tree.column("L (mm)", width=80)
        self.tree.heading("Densidade", text="ρ (g/cm³)")
        self.tree.column("Densidade", width=80)
        self.tree.heading("Ensaios", text="Ensaios")
        self.tree.column("Ensaios", width=60)
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        vsb = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Bind selection event
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # Status Label
        self.lbl_status = ctk.CTkLabel(self.sel_frame, text="Selecione pelo menos 2 amostras.", 
                                        text_color="gray", font=("Consolas", 12))
        self.lbl_status.pack(anchor="w", padx=10, pady=5)
        
        # Action Buttons
        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.pack(fill="x", padx=20, pady=10)
        
        self.btn_validate = ctk.CTkButton(self.btn_frame, text="Validar Seleção", command=self.validate_selection)
        self.btn_validate.pack(side="left", padx=10)
        
        self.btn_execute = ctk.CTkButton(self.btn_frame, text="Executar Correções", command=self.run_corrections, 
                                          fg_color="green", state="disabled")
        self.btn_execute.pack(side="left", padx=10)
        
        # Results (Scrollable Textbox - allows text selection)
        self.txt_result = ctk.CTkTextbox(self, height=200, font=("Consolas", 14), wrap="word")
        self.txt_result.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt_result.insert("1.0", "Resultados aparecerão aqui.")
        self.txt_result.configure(state="disabled")
        
        self.refresh_samples()
    
    def refresh_samples(self):
        """Refresh the sample list from database."""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        amostras = self.db.list_amostras()
        for a in amostras:
            testes = self.db.get_ensaios_by_amostra(a['id'])
            num_testes = len(testes)
            
            self.tree.insert("", "end", iid=str(a['id']), values=(
                "", a['nome'], f"{a['d_capilar_mm']:.2f}", f"{a['l_capilar_mm']:.2f}",
                f"{a['densidade_g_cm3']:.3f}", num_testes
            ))
    
    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        self.refresh_samples()
    
    def _set_result(self, text):
        """Update results textbox with text (selectable but read-only)."""
        self.txt_result.configure(state="normal")
        self.txt_result.delete("1.0", "end")
        self.txt_result.insert("1.0", text)
        self.txt_result.configure(state="disabled")
    
    def on_tree_select(self, event):
        """Handle tree selection change."""
        selected = self.tree.selection()
        self.lbl_status.configure(text=f"{len(selected)} amostra(s) selecionada(s).")
    
    def validate_selection(self):
        """Validate the selected samples for Bagley/Mooney requirements."""
        selected_ids = self.tree.selection()
        
        if len(selected_ids) < 2:
            self.lbl_status.configure(text="❌ Selecione pelo menos 2 amostras.", text_color="red")
            self.btn_execute.configure(state="disabled")
            return False
        
        # M11: Aviso quando < 3 capilares (R²=1.0 com apenas 2 pontos)
        if len(selected_ids) < 3:
            messagebox.showwarning('Aviso — Validade Estatística',
                'Apenas 2 capilares selecionados.\n\n'
                'Com 2 pontos a regressão linear é exata (R²=1.0)\n'
                'sem graus de liberdade residuais.\n\n'
                'Recomenda-se mínimo 3 capilares para\n'
                'validade estatística de Bagley/Mooney.')
        
        # Get sample details
        samples = []
        for sid in selected_ids:
            item = self.tree.item(sid)
            values = item['values']
            samples.append({
                'id': int(sid),
                'nome': values[1],
                'd_mm': float(values[2]),
                'l_mm': float(values[3]),
                'rho': float(values[4])
            })
        
        do_bagley = self.chk_bagley.get()
        do_mooney = self.chk_mooney.get()
        
        errors = []
        
        # Bagley validation: same D, different L
        if do_bagley:
            d_values = [s['d_mm'] for s in samples]
            l_values = [s['l_mm'] for s in samples]
            
            # Allow some tolerance or checking exact? GUI shows 2 decimals.
            # Convert to fixed string to compare safely?
            d_set = set([f"{v:.2f}" for v in d_values])
            l_set = set([f"{v:.2f}" for v in l_values])
            
            if len(d_set) > 1:
                errors.append(f"Bagley: D deve ser igual em todas as amostras. Encontrado: {d_set}")
            if len(l_set) < 2:
                errors.append(f"Bagley: L deve ser diferente. Encontrado apenas: {l_set}")
        
        # Mooney validation: same L, different D
        if do_mooney:
            d_values = [s['d_mm'] for s in samples]
            l_values = [s['l_mm'] for s in samples]
            
            d_set = set([f"{v:.2f}" for v in d_values])
            l_set = set([f"{v:.2f}" for v in l_values])
            
            if len(l_set) > 1:
                errors.append(f"Mooney: L deve ser igual em todas as amostras. Encontrado: {l_set}")
            if len(d_set) < 2:
                errors.append(f"Mooney: D deve ser diferente. Encontrado apenas: {d_set}")
        
        if errors:
            self.lbl_status.configure(text="❌ " + " | ".join(errors), text_color="red")
            self.btn_execute.configure(state="disabled")
            return False
        
        self.lbl_status.configure(text="✅ Seleção válida! Pronto para executar.", text_color="green")
        self.btn_execute.configure(state="normal")
        self.selected_samples = {s['nome']: s for s in samples}
        return True
    
    def run_corrections(self):
        """Execute Bagley and/or Mooney corrections in a separate thread."""
        if not hasattr(self, 'selected_samples') or not self.selected_samples:
            self.lbl_status.configure(text="❌ Valide a seleção primeiro.", text_color="red")
            return
            
        do_bagley = self.chk_bagley.get()
        do_mooney = self.chk_mooney.get()
        samples_list = list(self.selected_samples.values())
        
        self.btn_execute.configure(state="disabled", text="Executando...")
        self.lbl_status.configure(text="⏳ Aguarde, calculando correções...", text_color="orange")
        self._set_result("Iniciando cálculos. Por favor aguarde...\n")
        
        import threading
        threading.Thread(target=self._do_run_corrections, args=(do_bagley, do_mooney, samples_list), daemon=True).start()
        
    def _do_run_corrections(self, do_bagley, do_mooney, samples_list):
        import reologia_corrections
        import tempfile
        import os
        from datetime import datetime
        import numpy as np
        
        results_txt = "═══════════════════════════════════════════\n"
        results_txt += "  CORREÇÕES AVANÇADAS\n"
        results_txt += "═══════════════════════════════════════════\n\n"
        
        # Get common parameters
        rho_g_cm3 = samples_list[0]['rho']
        rho_si = rho_g_cm3 * 1000  # kg/m³
        
        # Prepare capillary data structure
        capilares_data = []
        t_ext_s_array_map = {}
        
        for sample in samples_list:
            df = self.db.get_ensaios_by_amostra(sample['id'])
            if df.empty:
                continue
            
            d_mm = sample['d_mm']
            l_mm = sample['l_mm']
            
            # Extract data
            pressoes_Pa = df['pressao_pasta_bar'].values * 1e5
            massas_kg = df['massa_g'].values / 1000.0
            duracoes_s = df['duracao_s'].values
            
            cap_id = f"{d_mm:.3f}_{l_mm:.2f}"
            t_ext_s_array_map[cap_id] = duracoes_s
            
            capilares_data.append({
                'D_mm': d_mm,
                'L_mm': l_mm,
                'L_m': l_mm / 1000.0,
                'pressoes_Pa': pressoes_Pa,
                'massas_kg': massas_kg
            })
        
        output_folder = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        tau_w_corrigido = np.array([])
        gamma_targets = np.array([])
        tau_w_mooney = np.array([])
        gamma_true_mooney = np.array([])
        
        # Execute Bagley
        if do_bagley:
            common_D = samples_list[0]['d_mm']
            results_txt += f"───────────────────────────────────────────\n"
            results_txt += f"  CORREÇÃO DE BAGLEY (D={common_D} mm)\n"
            results_txt += f"───────────────────────────────────────────\n"
            
            tau_w_corrigido, gamma_targets = reologia_corrections.perform_bagley_correction(
                capilares_data, common_D, rho_si, t_ext_s_array_map, output_folder, timestamp
            )
            
            if len(tau_w_corrigido) > 0:
                results_txt += f"  Pontos corrigidos: {len(tau_w_corrigido)}\n"
                results_txt += f"  τ_w range: [{tau_w_corrigido.min():.1f} - {tau_w_corrigido.max():.1f}] Pa\n"
                results_txt += f"  γ̇ range:  [{gamma_targets.min():.1f} - {gamma_targets.max():.1f}] s⁻¹\n\n"
            else:
                results_txt += f"  ⚠️ Correção falhou. Verifique os dados.\n\n"
        
        # Execute Mooney
        if do_mooney:
            common_L = samples_list[0]['l_mm']
            results_txt += f"───────────────────────────────────────────\n"
            results_txt += f"  CORREÇÃO DE MOONEY (L={common_L} mm)\n"
            results_txt += f"───────────────────────────────────────────\n"
            
            # Use Bagley results as reference if available
            tau_ref = tau_w_corrigido if len(tau_w_corrigido) > 0 else None
            
            tau_w_mooney, gamma_true_mooney = reologia_corrections.perform_mooney_correction(
                capilares_data, common_L, rho_si, t_ext_s_array_map, output_folder, timestamp, tau_ref
            )
            
            if len(gamma_true_mooney) > 0:
                results_txt += f"  Pontos corrigidos: {len(gamma_true_mooney)}\n"
                results_txt += f"  τ_w range: [{tau_w_mooney.min():.1f} - {tau_w_mooney.max():.1f}] Pa\n"
                results_txt += f"  γ̇_true range: [{gamma_true_mooney.min():.1f} - {gamma_true_mooney.max():.1f}] s⁻¹\n\n"
            else:
                results_txt += f"  ⚠️ Correção falhou. Verifique os dados.\n\n"
        
        # If we have corrected data, fit models
        final_tau = tau_w_mooney if len(tau_w_mooney) > 0 else tau_w_corrigido
        final_gamma = gamma_true_mooney if len(gamma_true_mooney) > 0 else gamma_targets
        
        if len(final_tau) >= 3 and len(final_gamma) >= 3:
            import reologia_fitting
            
            results_txt += f"───────────────────────────────────────────\n"
            results_txt += f"  AJUSTE DE MODELOS (Dados Corrigidos)\n"
            results_txt += f"───────────────────────────────────────────\n\n"
            
            # Use unified fitting function
            model_results, best_model_nome, df_sum_modelo = reologia_fitting.ajustar_modelos(final_gamma, final_tau)
            
            if model_results:
                for idx, row in df_sum_modelo.iterrows():
                    mod_name = row['Modelo']
                    r2_val = row['R2']
                    aic_val = row['AIC']
                    params_txt = row['Parametros']
                    
                    results_txt += f"  {mod_name} (R²={r2_val:.4f}, AIC={aic_val:.2f})\n"
                    # Parâmetros já formatados na string "K=1.23, n=0.45"
                    for p_str in params_txt.split(", "):
                        results_txt += f"    {p_str}\n"
                    results_txt += "\n"
                
                if best_model_nome:
                    best_r2_val = model_results[best_model_nome]['R2']
                    results_txt += f"───────────────────────────────────────────\n"
                    results_txt += f"  ★ MELHOR MODELO (AIC): {best_model_nome} (R²={best_r2_val:.4f})\n"
                    results_txt += f"───────────────────────────────────────────\n"
        
        self.after(0, lambda: self._on_corrections_done(results_txt))
        
    def _on_corrections_done(self, results_txt):
        self._set_result(results_txt)
        self.lbl_status.configure(text="✅ Cálculos concluídos.", text_color="green")
        self.btn_execute.configure(state="normal", text="Executar Selecionadas")
