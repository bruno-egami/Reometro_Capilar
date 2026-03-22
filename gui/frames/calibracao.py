import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import time
import numpy as np
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from datetime import datetime

class CalibracaoFrame(ctk.CTkFrame):
    """Calibration wizard using Pasta sensor (factory calibrated) as reference for Linha."""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller.controller
        self.db = controller.db
        
        self.label = ctk.CTkLabel(self, text="Calibração e Validação do Reômetro", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=10, padx=20, anchor="w")
        
        # Tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tab_linha = self.tabview.add("Calibração P_Linha")
        self.tab_newtoniano = self.tabview.add("Validação Newtoniana (M9)")
        self.tab_historico = self.tabview.add("Histórico")
        
        self._init_tab_linha()
        self._init_tab_newtoniano()
        self._init_tab_historico()

    def _init_tab_linha(self):
        # Info about factory calibration
        self.info_label = ctk.CTkLabel(self.tab_linha, 
            text="O sensor Pasta possui calibração de fábrica (0-10 bar).\n"
                 "Usaremos ele como referência para calibrar o sensor Linha.",
            text_color="gray", justify="left")
        self.info_label.pack(pady=10, padx=20, anchor="w")
        
        self.step_label = ctk.CTkLabel(self.tab_linha, text="Calibração Contínua (Ramp-up)", font=ctk.CTkFont(size=18))
        self.step_label.pack(pady=10)
        
        instructions = (
            "1. Despressurize o sistema a 0 bar.\n"
            "2. Clique em 'Iniciar Gravação'.\n"
            "3. Aumente a pressão lenta e progressivamente (ex: até 8 bar).\n"
            "4. Clique em 'Parar e Calcular' ANTES de soltar a pressão."
        )
        self.instruction_label = ctk.CTkLabel(self.tab_linha, text=instructions, text_color="gray", justify="left")
        self.instruction_label.pack(pady=5)
        
        self.info_frame = ctk.CTkFrame(self.tab_linha)
        self.info_frame.pack(pady=10)
        
        self.lbl_v1 = ctk.CTkLabel(self.info_frame, text="V_Linha: ---")
        self.lbl_v1.pack(side="left", padx=20)
        self.lbl_p_pasta = ctk.CTkLabel(self.info_frame, text="P_Pasta (ref): ---")
        self.lbl_p_pasta.pack(side="left", padx=20)
        
        self.btn_action = ctk.CTkButton(self.tab_linha, text="Iniciar Gravação da Calibração", command=self.toggle_calibration, fg_color="#1f6aa5")
        self.btn_action.pack(pady=10)
        
        # --- Real-time Graph ---
        self.graph_frame = ctk.CTkFrame(self.tab_linha)
        self.graph_frame.pack(fill="both", expand=True, pady=10)
        
        self.fig = Figure(figsize=(5, 2.5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Pressão Instantânea (bar)", fontsize=10)
        self.ax.set_xlabel("Tempo (s)", fontsize=8)
        self.line_l, = self.ax.plot([], [], label='Linha') 
        self.line_p, = self.ax.plot([], [], label='Pasta') 
        self.ax.legend(fontsize=8)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Data storage for plot (limit to last 200 points for performance)
        self.plot_times = deque(maxlen=200)
        self.plot_p_linha = deque(maxlen=200)
        self.plot_p_pasta = deque(maxlen=200)
        self.plot_start_time = None
        
        # State variables for continuous calibration
        self.is_recording_calibration = False
        self.calib_v_linha = []
        self.calib_p_pasta = []
        
    def _init_tab_newtoniano(self):
        lbl = ctk.CTkLabel(self.tab_newtoniano, text="Rotina de Verificação de Precisão", font=ctk.CTkFont(size=18, weight="bold"))
        lbl.pack(pady=10)
        
        txt = ("Valide o hardware testando um fluido Newtoniano conhecido (ex: Água Destilada, Óleo Mineral).\n"
               "1. A equação deve se ajustar linearmente indicando o índice n ≈ 1.0\n"
               "2. A densidade aferida garante a precisão do sensor de pressão (Ajuste de Célula de Carga).")
        
        ctk.CTkLabel(self.tab_newtoniano, text=txt, text_color="gray", justify="left").pack(pady=5)
        
        form = ctk.CTkFrame(self.tab_newtoniano)
        form.pack(pady=10, padx=20, fill="x")
        
        # Grid para inputs
        ctk.CTkLabel(form, text="Fluidos de Referência:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.fluido_cb = ctk.CTkComboBox(form, values=["Água Destilada (~0.89 mPa.s)", "Óleo Mineral Silicone (~500 mPa.s)", "Glicerina (~934 mPa.s)"])
        self.fluido_cb.grid(row=0, column=1, padx=10, pady=5)
        self.fluido_cb.set("Óleo Mineral Silicone (~500 mPa.s)")
        
        ctk.CTkLabel(form, text="D Capilar (mm):").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.val_d_entry = ctk.CTkEntry(form, width=80)
        self.val_d_entry.insert(0, "1.0")
        self.val_d_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        ctk.CTkLabel(form, text="L Capilar (mm):").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.val_l_entry = ctk.CTkEntry(form, width=80)
        self.val_l_entry.insert(0, "30.0")
        self.val_l_entry.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        
        self.btn_run_val = ctk.CTkButton(self.tab_newtoniano, text="Lida Massa (Q) & Valida Pressão", 
                                        command=self.run_newtonian_validation, fg_color="green")
        self.btn_run_val.pack(pady=10)
        
        self.lbl_val_res = ctk.CTkLabel(self.tab_newtoniano, text="", text_color="red")
        self.lbl_val_res.pack(pady=5)
    
    def run_newtonian_validation(self):
        """Lê pressão atual e compara com o fluido Newtoniano de referência."""
        if not self.controller.is_connected:
            success, msg = self.controller.find_and_connect()
            if success:
                self.controller.start_reading()
            else:
                tk.messagebox.showerror("Erro", f"Conecte o Arduino primeiro. Falha: {msg}")
                return

        dialog = ctk.CTkInputDialog(text="Extrusão em andamento?\nDigite a Vazão Mássica média estimada (g/s):", title="Vazão")
        vazao_str = dialog.get_input()
        if not vazao_str: return
        
        try:
            vazao_m = float(vazao_str.replace(',', '.')) / 1000.0 # kg/s
            d_m = float(self.val_d_entry.get().replace(',', '.')) / 1000.0
            l_m = float(self.val_l_entry.get().replace(',', '.')) / 1000.0
        except ValueError:
            tk.messagebox.showerror("Erro", "Entradas inválidas.")
            return
            
        self.btn_run_val.configure(state="disabled", text="Avaliando...")
        self.lbl_val_res.configure(text="Capturando pressão...", text_color="orange")
        
        self.temp_samples = []
        self.original_cb = self.controller.on_pressure_reading
        
        def val_collector(p_linha, p_pasta, v1, v2):
            self.temp_samples.append(p_linha)
            
        self.controller.on_pressure_reading = val_collector
        self.after(3000, lambda: self._finalize_validation(vazao_m, d_m, l_m))
        
    def _finalize_validation(self, vazao_kg_s, d_m, l_m):
        self.controller.on_pressure_reading = self.original_cb
        self.btn_run_val.configure(state="normal", text="Lida Massa (Q) & Valida Pressão")
        
        if len(self.temp_samples) < 5:
            self.lbl_val_res.configure(text="Erro: Sem dados do Arduino", text_color="red")
            return
            
        p_avg_bar = np.mean(self.temp_samples)
        p_avg_pa = p_avg_bar * 100000
        
        ref_choice = self.fluido_cb.get()
        mu_ref = 0.500 # Default fallback
        rho_ref = 1000
        if "Água" in ref_choice:
            mu_ref = 0.00089 # Pa.s
            rho_ref = 1000
        elif "Óleo" in ref_choice:
            mu_ref = 0.500 # Pa.s
            rho_ref = 960
        elif "Glicerina" in ref_choice:
            mu_ref = 0.934 # Pa.s
            rho_ref = 1260
            
        # Q volumétrica = massa_s / densidade
        vazao_vol = vazao_kg_s / rho_ref
        
        # Calculo Newtoniano
        r = d_m / 2.0
        gamma_dot = (4.0 * vazao_vol) / (np.pi * r**3)
        tau_w = (p_avg_pa * r) / (2.0 * l_m)
        mu_calc = tau_w / gamma_dot if gamma_dot > 0 else 0
        
        erro_relativo = abs(mu_calc - mu_ref) / mu_ref * 100.0
        
        status_color = "green" if erro_relativo <= 10.0 else "orange" if erro_relativo <= 25.0 else "red"
        status_icon = "✅" if erro_relativo <= 10.0 else "⚠️" if erro_relativo <= 25.0 else "❌"
        
        res_text = (f"{status_icon} Erro: {erro_relativo:.1f}%\n"
                    f"η_calc={mu_calc*1000:.1f} mPa.s | η_ref={mu_ref*1000:.1f} mPa.s\n"
                    f"P_medida = {p_avg_bar:.2f} bar")
        
        self.lbl_val_res.configure(text=res_text, text_color=status_color)

    def _init_tab_historico(self):
        frm_top = ctk.CTkFrame(self.tab_historico, fg_color="transparent")
        frm_top.pack(fill="x", padx=10, pady=10)
        
        lbl_title = ctk.CTkLabel(frm_top, text="Histórico de Calibrações", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_title.pack(side="left")
        
        btn_refresh = ctk.CTkButton(frm_top, text="Atualizar", width=100, command=self.refresh_historico)
        btn_refresh.pack(side="right")
        
        self.scroll_hist = ctk.CTkScrollableFrame(self.tab_historico)
        self.scroll_hist.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.refresh_historico()
        
    def refresh_historico(self):
        # Clear current
        for widget in self.scroll_hist.winfo_children():
            widget.destroy()
            
        calibs = self.db.get_all_calibracoes()
        if not calibs:
            lbl = ctk.CTkLabel(self.scroll_hist, text="Nenhuma calibração registrada ainda.", text_color="gray")
            lbl.pack(pady=20)
            return
            
        for i, cal in enumerate(calibs):
            bg_color = ("gray85", "gray25") if i % 2 == 0 else ("gray90", "gray20")
            is_active = (i == 0) # Assuming the most recent is active
            
            if is_active:
                bg_color = ("#d4edda", "#1d4d29") # light green highlight for active
            
            card = ctk.CTkFrame(self.scroll_hist, fg_color=bg_color, corner_radius=5)
            card.pack(fill="x", pady=2, padx=2)
            
            data_str = cal.get('data', '')
            try:
                dt = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S")
                data_str = dt.strftime("%d/%m/%Y %H:%M:%S")
            except (ValueError, KeyError):
                pass
                
            header_text = f"Calibração #{cal['id']} - Realizada em: {data_str}"
            if is_active:
                header_text += " [ATIVA]"
                
            lbl_header = ctk.CTkLabel(card, text=header_text, font=ctk.CTkFont(weight="bold"))
            lbl_header.pack(anchor="w", padx=10, pady=(5, 0))
            
            # Equation Line
            eq_linha = f"P_Linha = {cal['slope_linha']:.4f} × V + ({cal['intercept_linha']:.4f})"
            lbl_eq = ctk.CTkLabel(card, text=eq_linha, font=ctk.CTkFont(family="monospace", size=12))
            lbl_eq.pack(anchor="w", padx=20, pady=(0, 2))
            
            # Quality Metrics Line
            r2 = cal.get('r2')
            pontos = cal.get('pontos')
            p_min = cal.get('p_min')
            p_max = cal.get('p_max')
            
            metrics = []
            if r2 is not None: metrics.append(f"R²: {r2:.4f}")
            if pontos is not None: metrics.append(f"Pontos lidos: {pontos}")
            if p_min is not None and p_max is not None: metrics.append(f"Faixa: {p_min:.1f} a {p_max:.1f} bar")
            
            if metrics:
                metrics_text = " | ".join(metrics)
                lbl_met = ctk.CTkLabel(card, text=metrics_text, font=ctk.CTkFont(size=11), text_color="gray")
                lbl_met.pack(anchor="w", padx=20, pady=(0, 5))

    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        # Start monitoring if connected
        self.start_monitoring()

    def start_monitoring(self):
        if self.controller.is_connected:
            self.controller.on_pressure_reading = self.monitor_callback
            if not self.controller.is_reading:
                 self.controller.start_reading()

    def monitor_callback(self, p_linha, p_pasta, v1, v2):
        # Update labels (thread safe)
        self.after(0, self._update_labels_live, p_linha, p_pasta, v1)

    def _update_labels_live(self, p_linha, p_pasta, v1):
        self.lbl_v1.configure(text=f"V_Linha: {v1:.4f} V")
        self.lbl_p_pasta.configure(text=f"P_Pasta (ref): {p_pasta:.2f} bar")
        
        # Update Real-time Graph
        if self.plot_start_time is None:
            self.plot_start_time = time.time()
            
        t = time.time() - self.plot_start_time
        self.plot_times.append(t)
        self.plot_p_linha.append(p_linha)
        self.plot_p_pasta.append(p_pasta)
        
        if len(self.plot_times) % 2 == 0:
            self.line_l.set_data(self.plot_times, self.plot_p_linha)
            self.line_p.set_data(self.plot_times, self.plot_p_pasta)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()

        # If recording calibration, append to lists
        if hasattr(self, 'is_recording_calibration') and self.is_recording_calibration:
            self.calib_v_linha.append(v1)
            self.calib_p_pasta.append(p_pasta)

    def toggle_calibration(self):
        if hasattr(self, 'is_recording_calibration') and self.is_recording_calibration:
            # STOP recording and calculate
            self.is_recording_calibration = False
            self.btn_action.configure(text="Iniciar Gravação da Calibração", fg_color="#1f6aa5")
            self.calculate_continuous()
        else:
            # START recording
            if not self.controller.is_connected:
                success, msg = self.controller.find_and_connect()
                if success:
                    self.controller.start_reading()
                else:
                    tk.messagebox.showerror("Erro", f"Arduino não conectado. Falha: {msg}")
                    return
            
            # Start fresh lists
            self.calib_v_linha = []
            self.calib_p_pasta = []
            self.is_recording_calibration = True
            
            self.btn_action.configure(text="Parar e Calcular", fg_color="red")
            
    def calculate_continuous(self):
        if len(self.calib_v_linha) < 10:
            tk.messagebox.showerror("Erro", "Poucos pontos coletados. Faça uma varredura mais longa.")
            return
            
        from scipy.stats import linregress
        
        v_values = np.array(self.calib_v_linha)
        p_values = np.array(self.calib_p_pasta)
        
        delta_v = np.max(v_values) - np.min(v_values)
        delta_p = np.max(p_values) - np.min(p_values)
        
        if delta_v < 0.05:  
            tk.messagebox.showerror("Erro", "Variação de tensão muito baixa.\nAumente a pressão durante a gravação.")
            return
            
        if delta_p < 2.0:  
            tk.messagebox.showerror("Erro", "Variação de pressão insuficiente (mínimo de ~2 bar sugerido).\nAplique mais pressão.")
            return
        
        # Linear fit: P_linha = slope * V_linha + intercept
        res = linregress(v_values, p_values)
        slope_linha = res.slope
        intercept_linha = res.intercept
        r2 = res.rvalue**2
        num_points = len(v_values)
        p_min = np.min(p_values)
        p_max = np.max(p_values)
        
        # Save to database (only linha values, pasta is fixed)
        self.db.add_calibracao(
            slope_l=slope_linha, intercept_l=intercept_linha, 
            slope_p=2.5, intercept_p=-1.25, 
            r2=r2, pontos=num_points, p_min=p_min, p_max=p_max
        )
        self.controller.load_calibration_linha(slope_linha, intercept_linha)
        
        msg_title = "Sucesso" if r2 >= 0.99 else "Aviso de Qualidade"
        quality_msg = "Calibração excelente." if r2 >= 0.99 else "Qualidade marginal. Considere refazer mantendo a pressão subindo de forma mais suave."
        if r2 < 0.95:
            quality_msg = "BAIXA QUALIDADE! Por favor, repita o procedimento verificando ruídos ou subidas muito bruscas."
            msg_title = "Aviso Crítico"
            
        tk.messagebox.showinfo(msg_title, 
            f"Calibração Contínua do Sensor Linha Concluída!\n\n"
            f"P_linha = {slope_linha:.4f} × V + ({intercept_linha:.4f})\n"
            f"R² = {r2:.4f} ({quality_msg})\n\n"
            f"Referência: Sensor Pasta (fábrica)\n"
            f"Pontos coletados: {num_points}\n"
            f"Variação de Pressão: {p_min:.1f} bar → {p_max:.1f} bar")
            
        # Refresh history
        self.refresh_historico()
