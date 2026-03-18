import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import time
import numpy as np
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

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
        
        self._init_tab_linha()
        self._init_tab_newtoniano()

    def _init_tab_linha(self):
        # Info about factory calibration
        self.info_label = ctk.CTkLabel(self.tab_linha, 
            text="O sensor Pasta possui calibração de fábrica (0-10 bar).\n"
                 "Usaremos ele como referência para calibrar o sensor Linha.",
            text_color="gray", justify="left")
        self.info_label.pack(pady=10, padx=20, anchor="w")
        
        self.step_label = ctk.CTkLabel(self.tab_linha, text="Passo 1: Ponto Baixo (0 bar)", font=ctk.CTkFont(size=18))
        self.step_label.pack(pady=10)
        
        self.instruction_label = ctk.CTkLabel(self.tab_linha, 
            text="Despressurize o sistema e clique em 'Ler Ponto Baixo'.", text_color="gray")
        self.instruction_label.pack(pady=5)
        
        self.info_frame = ctk.CTkFrame(self.tab_linha)
        self.info_frame.pack(pady=10)
        
        self.lbl_v1 = ctk.CTkLabel(self.info_frame, text="V_Linha: ---")
        self.lbl_v1.pack(side="left", padx=20)
        self.lbl_p_pasta = ctk.CTkLabel(self.info_frame, text="P_Pasta (ref): ---")
        self.lbl_p_pasta.pack(side="left", padx=20)
        
        self.btn_action = ctk.CTkButton(self.tab_linha, text="Ler Ponto Baixo", command=self.step_1_low)
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
        
        self.v_linha_low = 0
        self.p_pasta_low = 0
        self.v_linha_mid = 0
        self.p_pasta_mid = 0
        self.v_linha_high = 0
        self.p_pasta_high = 0
        
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

    def step_1_low(self):
        """Read low pressure point (ideally 0 bar)."""
        if not self.controller.is_connected:
            success, msg = self.controller.find_and_connect()
            if success:
                self.controller.start_reading()
            else:
                tk.messagebox.showerror("Erro", f"Arduino não conectado. Falha: {msg}")
                return
            
        if not self.controller.is_reading:
            self.controller.start_reading()
            time.sleep(1)
            
        self.btn_action.configure(state="disabled", text="Lendo... Aguarde")
        
        self.temp_samples = []
        self.original_cb = self.controller.on_pressure_reading
        
        def collector(p_linha, p_pasta, v1, v2):
            self.temp_samples.append((v1, p_pasta))  # v_linha, p_pasta (factory ref)
            
        self.controller.on_pressure_reading = collector
        
        # Schedule finalization after 3 seconds
        self.after(3000, self._finalize_step_1)
        
    def _finalize_step_1(self):
        self.controller.on_pressure_reading = self.original_cb
        
        if len(self.temp_samples) < 5:
            self.btn_action.configure(state="normal", text="Ler Ponto Baixo")
            tk.messagebox.showerror("Erro", "Dados insuficientes do Arduino.")
            return

        self.v_linha_low = np.mean([s[0] for s in self.temp_samples])
        self.p_pasta_low = np.mean([s[1] for s in self.temp_samples])
        
        self.lbl_v1.configure(text=f"V_Linha: {self.v_linha_low:.4f} V")
        self.lbl_p_pasta.configure(text=f"P_Pasta: {self.p_pasta_low:.2f} bar")
        
        # Move to Step 2
        self.step_label.configure(text="Passo 2: Ponto Médio (~2 a 4 bar)")
        self.instruction_label.configure(text="Aplique pressão (~2 a 4 bar) e clique em 'Ler Ponto Médio'.")
        self.btn_action.configure(state="normal", text="Ler Ponto Médio", command=self.step_2_mid)
        
    def step_2_mid(self):
        """Read mid pressure point."""
        if not self.controller.is_connected:
            success, msg = self.controller.find_and_connect()
            if success:
                self.controller.start_reading()
            else:
                tk.messagebox.showerror("Erro", f"Arduino não conectado. Falha: {msg}")
                return
                
        self.btn_action.configure(state="disabled", text="Lendo... Aguarde")
        self.temp_samples = []
        self.original_cb = self.controller.on_pressure_reading
        
        def collector(p_linha, p_pasta, v1, v2):
            self.temp_samples.append((v1, p_pasta))
            
        self.controller.on_pressure_reading = collector
        
        # Schedule finalization after 3 seconds
        self.after(3000, self._finalize_step_2)
        
    def _finalize_step_2(self):
        self.controller.on_pressure_reading = self.original_cb
        
        if len(self.temp_samples) < 5:
            self.btn_action.configure(state="normal", text="Ler Ponto Médio")
            tk.messagebox.showerror("Erro", "Dados insuficientes.")
            return

        self.v_linha_mid = np.mean([s[0] for s in self.temp_samples])
        self.p_pasta_mid = np.mean([s[1] for s in self.temp_samples])
        
        self.lbl_v1.configure(text=f"V_Linha: {self.v_linha_mid:.4f} V")
        self.lbl_p_pasta.configure(text=f"P_Pasta: {self.p_pasta_mid:.2f} bar")
        
        # Move to Step 3
        self.step_label.configure(text="Passo 3: Ponto Alto (>6 bar)")
        self.instruction_label.configure(text="Aplique pressão (>6 bar) e clique em 'Ler Ponto Alto'.")
        self.btn_action.configure(state="normal", text="Ler Ponto Alto", command=self.step_3_high)
        
    def step_3_high(self):
        """Read high pressure point (>6 bar recommended)."""
        if not self.controller.is_connected:
            success, msg = self.controller.find_and_connect()
            if success:
                self.controller.start_reading()
            else:
                tk.messagebox.showerror("Erro", f"Arduino não conectado. Falha: {msg}")
                return
                
        self.btn_action.configure(state="disabled", text="Lendo... Aguarde")
        self.temp_samples = []
        self.original_cb = self.controller.on_pressure_reading
        
        def collector(p_linha, p_pasta, v1, v2):
            self.temp_samples.append((v1, p_pasta))
            
        self.controller.on_pressure_reading = collector
        
        # Schedule finalization after 3 seconds
        self.after(3000, self._finalize_step_3)
        
    def _finalize_step_3(self):
        self.controller.on_pressure_reading = self.original_cb
        self.btn_action.configure(state="normal", text="Ler Ponto Alto")
        
        if len(self.temp_samples) < 5:
            tk.messagebox.showerror("Erro", "Dados insuficientes.")
            return

        self.v_linha_high = np.mean([s[0] for s in self.temp_samples])
        self.p_pasta_high = np.mean([s[1] for s in self.temp_samples])
        
        self.lbl_v1.configure(text=f"V_Linha: {self.v_linha_low:.4f} → {self.v_linha_mid:.4f} → {self.v_linha_high:.4f} V")
        self.lbl_p_pasta.configure(text=f"P_Pasta: {self.p_pasta_low:.2f} → {self.p_pasta_mid:.2f} → {self.p_pasta_high:.2f} bar")
        
        self.step_4_calculate()
        
    def step_4_calculate(self):
        """Calculate linha calibration using pasta as reference (Linear Regression on 3 points)."""
        from scipy.stats import linregress
        
        v_values = [self.v_linha_low, self.v_linha_mid, self.v_linha_high]
        p_values = [self.p_pasta_low, self.p_pasta_mid, self.p_pasta_high]
        
        delta_v = max(v_values) - min(v_values)
        delta_p = max(p_values) - min(p_values)
        
        if delta_v < 0.01:  # Nearly no voltage change
            tk.messagebox.showerror("Erro", "Variação de tensão insuficiente.\nAumente a diferença de pressão entre os pontos.")
            return
            
        if delta_p < 2.0:  # Less than 2 bar difference overall
            tk.messagebox.showerror("Erro", "Variação de pressão insuficiente.\nAplique maior diferença entre os pontos baixo e alto.")
            return
        
        # Linear fit: P_linha = slope * V_linha + intercept
        res = linregress(v_values, p_values)
        slope_linha = res.slope
        intercept_linha = res.intercept
        r2 = res.rvalue**2
        
        # Save to database (only linha values, pasta is fixed)
        self.db.add_calibracao(slope_linha, intercept_linha, 2.5, -1.25)  # Pasta fixed
        self.controller.load_calibration_linha(slope_linha, intercept_linha)
        
        msg_title = "Sucesso" if r2 >= 0.99 else "Aviso de Qualidade"
        quality_msg = "Calibração excelente." if r2 >= 0.99 else "Qualidade marginal. Recomenda-se refazer."
        if r2 < 0.95:
            quality_msg = "BAIXA QUALIDADE! Por favor, repita o procedimento."
            msg_title = "Aviso Crítico"
            
        tk.messagebox.showinfo(msg_title, 
            f"Calibração do Sensor Linha Salva!\n\n"
            f"P_linha = {slope_linha:.4f} × V + ({intercept_linha:.4f})\n"
            f"R² = {r2:.4f} ({quality_msg})\n\n"
            f"Referência: Sensor Pasta (fábrica)\n"
            f"Pontos lidos:\n"
            f"  P1: {v_values[0]:.3f}V → {p_values[0]:.2f}bar\n"
            f"  P2: {v_values[1]:.3f}V → {p_values[1]:.2f}bar\n"
            f"  P3: {v_values[2]:.3f}V → {p_values[2]:.2f}bar")
        
        # Reset UI
        self.step_label.configure(text="Passo 1: Ponto Baixo (0 bar)")
        self.instruction_label.configure(text="Despressurize o sistema e clique em 'Ler Ponto Baixo'.")
        self.btn_action.configure(text="Ler Ponto Baixo", command=self.step_1_low)
        self.lbl_v1.configure(text="V_Linha: ---")
        self.lbl_p_pasta.configure(text="P_Pasta (ref): ---")
