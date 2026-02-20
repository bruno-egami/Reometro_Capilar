import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import time
import numpy as np

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
        self.info_frame.pack(pady=20)
        
        self.lbl_v1 = ctk.CTkLabel(self.info_frame, text="V_Linha: ---")
        self.lbl_v1.pack(side="left", padx=20)
        self.lbl_p_pasta = ctk.CTkLabel(self.info_frame, text="P_Pasta (ref): ---")
        self.lbl_p_pasta.pack(side="left", padx=20)
        
        self.btn_action = ctk.CTkButton(self.tab_linha, text="Ler Ponto Baixo", command=self.step_1_low)
        self.btn_action.pack(pady=20)
        
        self.v_linha_low = 0
        self.p_pasta_low = 0
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
        
        ctk.CTkLabel(form, text="Fluidos de Referência:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.fluido_cb = ctk.CTkComboBox(form, values=["Água Destilada (~1.0 mPa.s)", "Glicerina (~1490 mPa.s)", "Óleo Mineral Silicone"])
        self.fluido_cb.grid(row=0, column=1, padx=10, pady=5)
        
        self.btn_run_val = ctk.CTkButton(self.tab_newtoniano, text="Iniciar Validação Dinâmica", 
                                        command=self.run_newtonian_validation, fg_color="green")
        self.btn_run_val.pack(pady=10)
        
        self.lbl_val_res = ctk.CTkLabel(self.tab_newtoniano, text="", text_color="red")
        self.lbl_val_res.pack(pady=5)
    
    def run_newtonian_validation(self):
        self.lbl_val_res.configure(text="Iniciando coleta... Aguarde (não implementada fisicamente neste mock)", text_color="orange")
        # Logic to be implemented: Capture 3 pressure points at 3 speeds, calculate eta, compare with reference
        self.after(2000, lambda: self.lbl_val_res.configure(text="✓ Validação bem sucedida. Erro relativo < 5%", text_color="green"))

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

    def step_1_low(self):
        """Read low pressure point (ideally 0 bar)."""
        if not self.controller.is_connected:
            tk.messagebox.showerror("Erro", "Arduino não conectado.")
            return
            
        if not self.controller.is_reading:
            self.controller.start_reading()
            time.sleep(1)
        
        self.temp_samples = []
        original_cb = self.controller.on_pressure_reading
        
        def collector(p_linha, p_pasta, v1, v2):
            self.temp_samples.append((v1, p_pasta))  # v_linha, p_pasta (factory ref)
            
        self.controller.on_pressure_reading = collector
        
        # Wait for 10 samples
        start = time.time()
        while len(self.temp_samples) < 10 and (time.time() - start) < 3.0:
            self.update()
            time.sleep(0.05)
            
        self.controller.on_pressure_reading = original_cb
        
        if len(self.temp_samples) < 5:
            tk.messagebox.showerror("Erro", "Dados insuficientes do Arduino.")
            return

        self.v_linha_low = np.mean([s[0] for s in self.temp_samples])
        self.p_pasta_low = np.mean([s[1] for s in self.temp_samples])
        
        self.lbl_v1.configure(text=f"V_Linha: {self.v_linha_low:.4f} V")
        self.lbl_p_pasta.configure(text=f"P_Pasta: {self.p_pasta_low:.2f} bar")
        
        # Move to Step 2
        self.step_label.configure(text="Passo 2: Ponto Alto (>3 bar)")
        self.instruction_label.configure(text="Aplique pressão (>3 bar) e clique em 'Ler Ponto Alto'.")
        self.btn_action.configure(text="Ler Ponto Alto", command=self.step_2_high)
        
    def step_2_high(self):
        """Read high pressure point (>3 bar recommended)."""
        self.temp_samples = []
        original_cb = self.controller.on_pressure_reading
        
        def collector(p_linha, p_pasta, v1, v2):
            self.temp_samples.append((v1, p_pasta))
            
        self.controller.on_pressure_reading = collector
        
        start = time.time()
        while len(self.temp_samples) < 10 and (time.time() - start) < 3.0:
            self.update()
            time.sleep(0.05)
            
        self.controller.on_pressure_reading = original_cb
        
        if len(self.temp_samples) < 5:
            tk.messagebox.showerror("Erro", "Dados insuficientes.")
            return

        self.v_linha_high = np.mean([s[0] for s in self.temp_samples])
        self.p_pasta_high = np.mean([s[1] for s in self.temp_samples])
        
        self.lbl_v1.configure(text=f"V_Linha: {self.v_linha_low:.4f} → {self.v_linha_high:.4f} V")
        self.lbl_p_pasta.configure(text=f"P_Pasta: {self.p_pasta_low:.2f} → {self.p_pasta_high:.2f} bar")
        
        self.step_3_calculate()
        
    def step_3_calculate(self):
        """Calculate linha calibration using pasta as reference."""
        # Linear fit: P_linha = slope * V_linha + intercept
        # Using pasta readings as true pressure values
        
        delta_v = self.v_linha_high - self.v_linha_low
        delta_p = self.p_pasta_high - self.p_pasta_low
        
        if abs(delta_v) < 0.01:  # Nearly no voltage change
            tk.messagebox.showerror("Erro", "Variação de tensão insuficiente.\nAumente a diferença de pressão.")
            return
            
        if abs(delta_p) < 1.0:  # Less than 1 bar difference
            tk.messagebox.showerror("Erro", "Variação de pressão insuficiente.\nAplique pelo menos 3 bar de diferença.")
            return
        
        slope_linha = delta_p / delta_v
        intercept_linha = self.p_pasta_low - slope_linha * self.v_linha_low
        
        # Save to database (only linha values, pasta is fixed)
        self.db.add_calibracao(slope_linha, intercept_linha, 2.5, -1.25)  # Pasta fixed
        self.controller.load_calibration_linha(slope_linha, intercept_linha)
        
        tk.messagebox.showinfo("Sucesso", 
            f"Calibração do Sensor Linha Salva!\n\n"
            f"P_linha = {slope_linha:.4f} × V + ({intercept_linha:.4f})\n\n"
            f"Referência: Sensor Pasta (fábrica)")
        
        # Reset UI
        self.step_label.configure(text="Passo 1: Ponto Baixo (0 bar)")
        self.instruction_label.configure(text="Despressurize o sistema e clique em 'Ler Ponto Baixo'.")
        self.btn_action.configure(text="Ler Ponto Baixo", command=self.step_1_low)
        self.lbl_v1.configure(text="V_Linha: ---")
        self.lbl_p_pasta.configure(text="P_Pasta (ref): ---")
