import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from customtkinter import CTkInputDialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import time
import numpy as np

class ColetaFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller.controller # Access actual logic controller
        self.db = controller.db
        
        # Title
        self.label = ctk.CTkLabel(self, text="Painel de Coleta", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20, padx=20, anchor="w")
        
        # --- Top Section: Inputs ---
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.pack(fill="x", padx=20)
        
        # Helper to create inputs
        def create_entry(parent, label_text, col):
            lbl = ctk.CTkLabel(parent, text=label_text)
            lbl.grid(row=0, column=col*2, padx=5, pady=5, sticky="e")
            entry = ctk.CTkEntry(parent, width=120)
            entry.grid(row=0, column=col*2+1, padx=5, pady=5)
            return entry

        self.entry_amostra = create_entry(self.input_frame, "ID Amostra:", 0)
        self.entry_d = create_entry(self.input_frame, "D (mm):", 1)
        self.entry_l = create_entry(self.input_frame, "L (mm):", 2)
        self.entry_rho = create_entry(self.input_frame, "Densidade (g/cm³):", 3)
        
        self.btn_connect = ctk.CTkButton(self.input_frame, text="Conectar", command=self.connect_arduino, fg_color="green")
        self.btn_connect.grid(row=0, column=8, padx=20, pady=5)

        # --- Middle Section: Graph ---
        self.graph_frame = ctk.CTkFrame(self)
        self.graph_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Matplotlib Figure with inherited style
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        self.ax.set_title("Pressão Real-time")
        self.ax.set_xlabel("Tempo (s)")
        self.ax.set_ylabel("Pressão (bar)")
        
        self.line_l, = self.ax.plot([], [], label='Linha') 
        self.line_p, = self.ax.plot([], [], label='Pasta') 
        self.ax.legend()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # --- Bottom Section: Controls & Monitor ---
        self.control_frame = ctk.CTkFrame(self, height=100)
        self.control_frame.pack(fill="x", padx=20, pady=20)
        
        self.lbl_p_linha = ctk.CTkLabel(self.control_frame, text="P. Linha: 0.00 bar", font=("Consolas", 20))
        self.lbl_p_linha.pack(side="left", padx=20)
        
        self.lbl_p_pasta = ctk.CTkLabel(self.control_frame, text="P. Pasta: 0.00 bar", font=("Consolas", 20))
        self.lbl_p_pasta.pack(side="left", padx=20)
        
        self.btn_start = ctk.CTkButton(self.control_frame, text="INICIAR COLETA", command=self.toggle_collection, state="disabled")
        self.btn_start.pack(side="right", padx=20, pady=10)

        # Data storage for plotting
        self.times = []
        self.p1_data = []
        self.p2_data = []
        self.start_time = None
        self.collecting = False
        self.connection_lost = False

        # Setup callbacks
        self.controller.on_pressure_reading = self.update_plot_callback
        self.controller.on_error = self.handle_arduino_error
    
    def handle_arduino_error(self, error_msg):
        """Handle Arduino disconnection or communication errors."""
        self.connection_lost = True
        self.after(0, self._show_disconnect_error, error_msg)
    
    def _show_disconnect_error(self, error_msg):
        """Show error dialog on main thread."""
        if self.collecting:
            # Save partial data if available
            self.collecting = False
            self.btn_start.configure(text="INICIAR COLETA", fg_color="#1f6aa5", state="disabled")
            
            partial_msg = ""
            if len(self.times) > 0:
                partial_msg = f"\n\nDados parciais coletados ({len(self.times)} pontos).\nDeseja salvar?"
                
                if tk.messagebox.askyesno("Dados Parciais", 
                    f"Arduino desconectado durante coleta!\n{partial_msg}"):
                    # Ask for mass and save partial data
                    dialog = CTkInputDialog(text="Digite a massa extrudada (g):", title="Salvar Dados Parciais")
                    massa_str = dialog.get_input()
                    if massa_str:
                        try:
                            massa = float(massa_str.replace(',', '.'))
                            if massa > 0:
                                self.save_point(massa)
                        except ValueError:
                            pass
            else:
                tk.messagebox.showerror("Erro de Conexão", 
                    f"Arduino desconectado!\n\nErro: {error_msg}")
        else:
            tk.messagebox.showerror("Erro de Conexão", 
                f"Conexão com Arduino perdida.\n\nErro: {error_msg}")
        
        # Reset connection UI
        self.btn_connect.configure(text="Reconectar", state="normal", fg_color="orange")
        self.btn_start.configure(state="disabled")

    def connect_arduino(self):
        success, msg = self.controller.find_and_connect()
        if success:
            self.connection_lost = False
            self.btn_connect.configure(text="Conectado", state="disabled", fg_color="green")
            self.btn_start.configure(state="normal")
            # Start background reading
            self.controller.start_reading()
            # C11: Aviso de calibração pendente
            if not self.controller.linha_calibrada:
                if not hasattr(self, '_calib_banner'):
                    self._calib_banner = ctk.CTkLabel(
                        self, text="⚠  Sensor Linha sem calibração! Vá à aba Calibração antes de coletar.",
                        font=ctk.CTkFont(size=13, weight="bold"),
                        text_color="#1e1e2e", fg_color="#f9e2af",
                        corner_radius=6, height=32)
                    self._calib_banner.pack(fill="x", padx=20, pady=(0, 5), before=self.graph_frame)
        else:
            tk.messagebox.showerror("Erro", f"Falha ao conectar: {msg}")

    def toggle_collection(self):
        if not self.collecting:
            # Validate Inputs with comprehensive checks
            errors = []
            
            # Validate sample name
            amostra_nome = self.entry_amostra.get().strip()
            if not amostra_nome:
                errors.append("• ID da Amostra é obrigatório")
            
            # Validate numeric fields with ranges
            def validate_numeric(entry, name, min_val, max_val):
                val_str = entry.get().strip().replace(',', '.')
                if not val_str:
                    return None, f"• {name} é obrigatório"
                try:
                    val = float(val_str)
                    if val <= 0:
                        return None, f"• {name} deve ser positivo (atual: {val})"
                    if val < min_val:
                        return None, f"• {name} muito pequeno (mín: {min_val}, atual: {val})"
                    if val > max_val:
                        return None, f"• {name} muito grande (máx: {max_val}, atual: {val})"
                    return val, None
                except ValueError:
                    return None, f"• {name} inválido (não é número)"
            
            d_val, d_err = validate_numeric(self.entry_d, "Diâmetro (D)", 0.1, 10.0)
            if d_err: errors.append(d_err)
            
            l_val, l_err = validate_numeric(self.entry_l, "Comprimento (L)", 1.0, 200.0)
            if l_err: errors.append(l_err)
            
            rho_val, rho_err = validate_numeric(self.entry_rho, "Densidade (ρ)", 0.5, 5.0)
            if rho_err: errors.append(rho_err)
            
            if errors:
                tk.messagebox.showerror("Erro de Validação", 
                    "Corrija os seguintes erros:\n\n" + "\n".join(errors))
                return

            # Start Collection
            self.collecting = True
            self.btn_start.configure(text="PARAR & SALVAR", fg_color="red")
            self.times = []
            self.p1_data = []
            self.p2_data = []
            self.v1_data = []
            self.v2_data = []
            
            # A-02: Reset EMA filter before new collection
            # Stop reading briefly to avoid serial bus contention
            self.controller.stop_reading()
            self.controller.reset_ema()
            self.controller.start_reading()
            
            self.start_time = time.time()
            
            # Clear graph
            self.line_l.set_data([], [])
            self.line_p.set_data([], [])
            self.canvas.draw()
            
        else:
            # Stop Collection
            self.collecting = False
            self.btn_start.configure(text="INICIAR COLETA", fg_color="#1f6aa5")
            
            # 1. Ask for Mass
            dialog = CTkInputDialog(text="Digite a massa extrudada (g):", title="Massa")
            massa_str = dialog.get_input()
            
            if massa_str:
                try:
                    massa = float(massa_str.replace(',', '.'))
                    if massa <= 0:
                        tk.messagebox.showerror("Erro", "Massa deve ser positiva.")
                        return
                    if massa > 50:
                        tk.messagebox.showwarning("Aviso", f"Massa elevada ({massa}g). Verifique o valor.")
                    self.save_point(massa)
                except ValueError:
                    tk.messagebox.showerror("Erro", "Massa inválida. Digite um número.")

    def update_plot_callback(self, p1, p2, v1, v2):
        # Called from thread, update via after
        self.after(0, self._update_gui, p1, p2, v1, v2)

    def _update_gui(self, p1, p2, v1, v2):
        self.lbl_p_linha.configure(text=f"P. Linha: {p1:.2f} bar")
        self.lbl_p_pasta.configure(text=f"P. Pasta: {p2:.2f} bar")
        
        if self.collecting:
            t = time.time() - self.start_time
            self.times.append(t)
            self.p1_data.append(p1)
            self.p2_data.append(p2)
            self.v1_data.append(v1)
            self.v2_data.append(v2)
            
            # Efficient update (redraw every 5th point to save CPU if fast)
            if len(self.times) % 2 == 0:
                self.line_l.set_data(self.times, self.p1_data)
                self.line_p.set_data(self.times, self.p2_data)
                self.ax.relim()
                self.ax.autoscale_view()
                self.canvas.draw_idle()

    def save_point(self, massa):
        try:
            # 1. Get/Create Sample
            nome = self.entry_amostra.get().strip()
            desc = "Coleta via GUI"
            d_mm = float(self.entry_d.get().replace(',', '.'))
            l_mm = float(self.entry_l.get().replace(',', '.'))
            rho = float(self.entry_rho.get().replace(',', '.'))
            
            # Check if sample exists, if not create
            amostra = self.db.get_amostra_by_name(nome)
            if amostra:
                amostra_id = amostra['id']
            else:
                amostra_id = self.db.add_amostra(nome, desc, d_mm, l_mm, rho)
            
            if not amostra_id:
                tk.messagebox.showerror("Erro", "Falha ao criar/obter amostra.")
                return

            # 2. Calculate Averages
            
            # --- M2: Detecção Automática de Regime Estacionário ---
            # Encontrar a janela com menor desvio padrão (mais estável)
            window_size = min(30, len(self.p2_data)) # Janela de até 30 pontos (3 segundos)
            if window_size >= 10:
                best_start_idx = 0
                min_std = float('inf')
                
                # Desliza a janela pela segunda metade dos dados (geralmente onde estabiliza)
                start_search = max(0, len(self.p2_data) // 2 - window_size)
                
                for i in range(start_search, len(self.p2_data) - window_size + 1):
                    window = self.p2_data[i: i + window_size]
                    current_std = np.std(window)
                    if current_std < min_std:
                        min_std = current_std
                        best_start_idx = i
                        
                end_idx = best_start_idx + window_size
                p1_avg = np.mean(self.p1_data[best_start_idx:end_idx])
                p2_avg = np.mean(self.p2_data[best_start_idx:end_idx])
                v1_avg = np.mean(self.v1_data[best_start_idx:end_idx])
                v2_avg = np.mean(self.v2_data[best_start_idx:end_idx])
                
                # Calcular CV para feedback ao usuário
                p2_mean_window = np.mean(self.p2_data[best_start_idx:end_idx])
                cv_percent = (min_std / p2_mean_window * 100) if p2_mean_window > 0 else 0
                
                print(f"Regime estacionário detectado: pontos {best_start_idx} a {end_idx}. CV: {cv_percent:.2f}%")
                
                # M2: Destaque visual da janela no gráfico
                if self.times and len(self.times) > end_idx:
                    t_start = self.times[best_start_idx]
                    t_end = self.times[end_idx - 1]
                    self.ax.axvspan(t_start, t_end, alpha=0.18, color='#a6e3a1', zorder=0,
                                   label=f'Regime Estável (CV={cv_percent:.1f}%)')
                    self.ax.legend(fontsize=8)
                    self.canvas.draw_idle()
            else:
                # Fallback para média simples se poucos pontos
                p1_avg = np.mean(self.p1_data) if self.p1_data else 0
                p2_avg = np.mean(self.p2_data) if self.p2_data else 0
                v1_avg = np.mean(self.v1_data) if self.v1_data else 0
                v2_avg = np.mean(self.v2_data) if self.v2_data else 0
                
            duracao = self.times[-1] if self.times else 0
            
            # Determine point number (count existing + 1)
            existing_tests = self.db.get_ensaios_by_amostra(amostra_id)
            ponto_n = len(existing_tests) + 1
            
            # 3. Save Test
            self.db.add_ensaio(amostra_id, ponto_n, p1_avg, p2_avg, massa, duracao, v1_avg, v2_avg)
            
            tk.messagebox.showinfo("Sucesso", f"Ponto {ponto_n} salvo para amostra '{nome}'!")
            
        except Exception as e:
            tk.messagebox.showerror("Erro", f"Erro ao salvar: {e}")

    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        # Restore callback when frame is shown
        if self.controller.is_connected:
            self.controller.on_pressure_reading = self.update_plot_callback
