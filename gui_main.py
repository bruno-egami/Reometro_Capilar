import customtkinter as ctk
from customtkinter import CTkInputDialog
import tkinter as tk
from tkinter import messagebox, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading
import time
from datetime import datetime
from database_manager import DatabaseManager
from reometer_controller import ReometerController, MockReometerController
import modelos_reologicos as models
from scipy.optimize import curve_fit
import numpy as np

# Set appearance mode and default color theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Increase global font/widget scaling for better readability
ctk.set_widget_scaling(1.3)  # 30% larger widgets
ctk.set_window_scaling(1.2)  # 20% larger window

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Reômetro Capilar Control System")
        self.geometry("1100x700")

        # Initialize Logic Components
        self.db = DatabaseManager()
        self.controller = ReometerController() 
        # Uncomment line below to force Mock for testing UI without Arduino
        # self.controller = MockReometerController()

        # Grid Layout (1x2)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Reômetro\nDual Sensor", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_coleta = ctk.CTkButton(self.sidebar_frame, text="Nova Coleta", command=self.show_coleta)
        self.btn_coleta.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_historico = ctk.CTkButton(self.sidebar_frame, text="Histórico", command=self.show_historico)
        self.btn_historico.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_calibracao = ctk.CTkButton(self.sidebar_frame, text="Calibração", command=self.show_calibracao)
        self.btn_calibracao.grid(row=3, column=0, padx=20, pady=10)

        self.btn_analise = ctk.CTkButton(self.sidebar_frame, text="Análise", command=self.show_analise)
        self.btn_analise.grid(row=4, column=0, padx=20, pady=10)
        
        self.btn_correcoes = ctk.CTkButton(self.sidebar_frame, text="Correções", command=self.show_correcoes)
        self.btn_correcoes.grid(row=5, column=0, padx=20, pady=10)
        
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Status: Desconectado", text_color="gray")
        self.status_label.grid(row=7, column=0, padx=20, pady=20)

        # --- Main Area ---
        self.frames = {}
        for F in (ColetaFrame, HistoricoFrame, CalibracaoFrame, AnaliseFrame, CorrecoesFrame):
            frame_name = F.__name__
            frame = F(parent=self, controller=self)
            self.frames[frame_name] = frame
            frame.grid(row=0, column=1, sticky="nsew")

        self.show_coleta()
    
    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()
        
    def show_coleta(self): self.show_frame("ColetaFrame")
    def show_historico(self): self.show_frame("HistoricoFrame")
    def show_calibracao(self): self.show_frame("CalibracaoFrame")
    def show_analise(self): self.show_frame("AnaliseFrame")
    def show_correcoes(self): self.show_frame("CorrecoesFrame")

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
        
        # Matplotlib Figure
        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor="#2b2b2b") # Dark background matching ctk
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#2b2b2b")
        self.ax.tick_params(axis='x', colors='white')
        self.ax.tick_params(axis='y', colors='white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white') 
        self.ax.spines['right'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.set_title("Pressão Real-time", color='white')
        self.ax.set_xlabel("Tempo (s)", color='white')
        self.ax.set_ylabel("Pressão (bar)", color='white')
        
        self.line_l, = self.ax.plot([], [], 'c-', label='Linha') # Cyan
        self.line_p, = self.ax.plot([], [], 'm-', label='Pasta') # Magenta
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
            import numpy as np
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


class HistoricoFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.db = controller.db
        
        self.label = ctk.CTkLabel(self, text="Histórico de Amostras", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20, padx=20, anchor="w")
        
        # Treeview Scrollbar
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Define columns
        cols = ("ID", "Nome", "Descrição", "Data", "Ensaios")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings")
        
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Button frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=10)
        
        self.btn_refresh = ctk.CTkButton(btn_frame, text="Atualizar", command=self.refresh_list)
        self.btn_refresh.pack(side="left", padx=5)
        
        self.btn_import_file = ctk.CTkButton(btn_frame, text="Importar JSON", 
                                              command=self.import_single_json, fg_color="green")
        self.btn_import_file.pack(side="left", padx=5)
        
        self.btn_import_folder = ctk.CTkButton(btn_frame, text="Importar Pasta", 
                                                command=self.import_folder_json, fg_color="orange")
        self.btn_import_folder.pack(side="left", padx=5)
        
        self.refresh_list()
    
    def import_single_json(self):
        """Import a single JSON file."""
        from tkinter import filedialog
        
        filepath = filedialog.askopenfilename(
            title="Selecionar JSON",
            initialdir="resultados_testes_reometro",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            success, msg, _ = self.db.import_json_legado(filepath)
            if success:
                messagebox.showinfo("Sucesso", msg)
                self.refresh_list()
            else:
                messagebox.showerror("Erro", msg)
    
    def import_folder_json(self):
        """Import all JSON files from a folder."""
        from tkinter import filedialog
        
        folder = filedialog.askdirectory(
            title="Selecionar Pasta com JSONs",
            initialdir="resultados_testes_reometro"
        )
        
        if folder:
            results = self.db.import_folder_json(folder)
            
            # Build summary
            success_count = sum(1 for _, s, _ in results if s)
            fail_count = len(results) - success_count
            
            # Build detailed message
            details = "\n".join([f"{'✓' if s else '✗'} {f}: {m}" for f, s, m in results[:10]])
            if len(results) > 10:
                details += f"\n... e mais {len(results) - 10} arquivos"
            
            messagebox.showinfo("Importação Concluída", 
                               f"Importados: {success_count}\nFalhas: {fail_count}\n\n{details}")
            self.refresh_list()

    def refresh_list(self):
        # Clear
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Fetch
        amostras = self.db.list_amostras()
        for a in amostras:
            # Count tests
            testes = self.db.get_ensaios_by_amostra(a['id'])
            num_testes = len(testes)
            
            self.tree.insert("", "end", values=(
                a['id'], a['nome'], a['descricao'], a['data_criacao'], num_testes
            ))
    
    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        self.refresh_list() # Auto refresh when shown

class CalibracaoFrame(ctk.CTkFrame):
    """Calibration wizard using Pasta sensor (factory calibrated) as reference for Linha."""
    
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller.controller
        self.db = controller.db
        
        self.label = ctk.CTkLabel(self, text="Calibração do Sensor Linha", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20, padx=20, anchor="w")
        
        # Info about factory calibration
        self.info_label = ctk.CTkLabel(self, 
            text="O sensor Pasta possui calibração de fábrica (0-10 bar).\n"
                 "Usaremos ele como referência para calibrar o sensor Linha.",
            text_color="gray", justify="left")
        self.info_label.pack(pady=10, padx=20, anchor="w")
        
        self.step_label = ctk.CTkLabel(self, text="Passo 1: Ponto Baixo (0 bar)", font=ctk.CTkFont(size=18))
        self.step_label.pack(pady=10)
        
        self.instruction_label = ctk.CTkLabel(self, 
            text="Despressurize o sistema e clique em 'Ler Ponto Baixo'.", text_color="gray")
        self.instruction_label.pack(pady=5)
        
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(pady=20)
        
        self.lbl_v1 = ctk.CTkLabel(self.info_frame, text="V_Linha: ---")
        self.lbl_v1.pack(side="left", padx=20)
        self.lbl_p_pasta = ctk.CTkLabel(self.info_frame, text="P_Pasta (ref): ---")
        self.lbl_p_pasta.pack(side="left", padx=20)
        
        self.btn_action = ctk.CTkButton(self, text="Ler Ponto Baixo", command=self.step_1_low)
        self.btn_action.pack(pady=20)
        
        # State
        self.v_linha_low = 0
        self.p_pasta_low = 0
        self.v_linha_high = 0
        self.p_pasta_high = 0

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

        import numpy as np
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

        import numpy as np
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

class AnaliseFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.db = controller.db
        
        self.label = ctk.CTkLabel(self, text="Análise Reológica Completa", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20, padx=20, anchor="w")
        
        # Selection Frame
        self.sel_frame = ctk.CTkFrame(self)
        self.sel_frame.pack(fill="x", padx=20)
        
        ctk.CTkLabel(self.sel_frame, text="Selecione Amostra:").pack(side="left", padx=10)
        self.combo_amostras = ctk.CTkComboBox(self.sel_frame, width=200)
        self.combo_amostras.pack(side="left", padx=10)
        self.combo_amostras.set("Atualizar Lista ->")
        
        self.btn_load = ctk.CTkButton(self.sel_frame, text="Analisar", command=self.run_analysis, fg_color="green")
        self.btn_load.pack(side="left", padx=10)
        
        # Options
        self.opt_frame = ctk.CTkFrame(self)
        self.opt_frame.pack(fill="x", padx=20, pady=10)
        
        self.chk_weissenberg = ctk.CTkCheckBox(self.opt_frame, text="Aplicar Correção Weissenberg-Rabinowitsch")
        self.chk_weissenberg.pack(side="left", padx=10)
        self.chk_weissenberg.select()  # Default: enabled
        
        # Export Buttons Frame
        self.export_frame = ctk.CTkFrame(self)
        self.export_frame.pack(fill="x", padx=20, pady=5)
        
        self.btn_export_png = ctk.CTkButton(self.export_frame, text="Exportar Gráficos (PNG)", 
                                             command=self.export_graphs, state="disabled")
        self.btn_export_png.pack(side="left", padx=10)
        
        self.btn_export_pdf = ctk.CTkButton(self.export_frame, text="Gerar Relatório (PDF)", 
                                             command=self.export_pdf, state="disabled")
        self.btn_export_pdf.pack(side="left", padx=10)
        
        # Results (Scrollable Textbox - allows text selection)
        self.txt_result = ctk.CTkTextbox(self, height=350, font=("Consolas", 14), wrap="word")
        self.txt_result.pack(fill="both", expand=True, padx=20, pady=10)
        self.txt_result.insert("1.0", "Resultados aparecerão aqui.\n\nSelecione uma amostra e clique em 'Analisar'.")
        self.txt_result.configure(state="disabled")  # Read-only but selectable
        
        # Store analysis data for export
        self.analysis_data = None
        
        self.refresh_combo()

    def refresh_combo(self):
        amostras = self.db.list_amostras()
        names = [a['nome'] for a in amostras]
        self.combo_amostras.configure(values=names)
        if names: self.combo_amostras.set(names[0])
        
    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        self.refresh_combo()
    
    def _set_result(self, text):
        """Update results textbox with text (selectable but read-only)."""
        self.txt_result.configure(state="normal")
        self.txt_result.delete("1.0", "end")
        self.txt_result.insert("1.0", text)
        self.txt_result.configure(state="disabled")

    def run_analysis(self):
        from scipy.stats import linregress
        from sklearn.metrics import r2_score
        
        nome = self.combo_amostras.get()
        if not nome: return
        
        amostra = self.db.get_amostra_by_name(nome)
        if not amostra: 
            self._set_result("Amostra não encontrada.")
            return
        
        df = self.db.get_ensaios_by_amostra(amostra['id'])
        if df.empty:
            self._set_result("Sem ensaios para esta amostra.")
            return
            
        try:
            D_mm = amostra['d_capilar_mm']
            L_mm = amostra['l_capilar_mm']
            Rho = amostra['densidade_g_cm3']
            
            R = (D_mm / 2.0) / 1000.0  # Radius in meters
            L = L_mm / 1000.0          # Length in meters
            
            aplicar_weissenberg = self.chk_weissenberg.get()
            
            gamma_dots_app = []
            taus = []
            delta_p_list = []  # P_linha - P_pasta (perdas do sistema)
            
            for index, row in df.iterrows():
                massa_g = row['massa_g']
                tempo_s = row['duracao_s']
                p_pasta_bar = row['pressao_pasta_bar']  # Sempre usar sensor da pasta
                p_linha_bar = row['pressao_linha_bar']  # Para cálculo de perdas
                
                if tempo_s <= 0 or massa_g <= 0 or p_pasta_bar <= 0: 
                    continue
                
                # Perda de pressão no sistema
                delta_p = p_linha_bar - p_pasta_bar
                delta_p_list.append(delta_p)
                
                # Volumetric flow rate Q
                Q_cm3s = massa_g / (Rho * tempo_s)  # cm³/s
                Q_m3s = Q_cm3s * 1e-6               # m³/s
                
                p_pa = p_pasta_bar * 1e5
                
                # Apparent Shear Rate: gamma_dot_app = (4 * Q) / (pi * R^3)
                gd_app = (4 * Q_m3s) / (np.pi * R**3)
                
                # Wall Shear Stress: tau_w = (P * R) / (2 * L)
                tau_w = (p_pa * R) / (2 * L)
                
                gamma_dots_app.append(gd_app)
                taus.append(tau_w)
                
            if len(gamma_dots_app) < 3:
                self._set_result("Pontos insuficientes para análise (mínimo 3).")
                return

            gd_app_arr = np.array(gamma_dots_app)
            tau_arr = np.array(taus)
            
            # --- Weissenberg-Rabinowitsch Correction ---
            n_prime = 1.0
            if aplicar_weissenberg:
                try:
                    log_gd = np.log(gd_app_arr)
                    log_tau = np.log(tau_arr)
                    slope, intercept, r_val, _, _ = linregress(log_gd, log_tau)
                    n_prime = slope
                    
                    # Correction Factor
                    correction_factor = (3 * n_prime + 1) / (4 * n_prime)
                    gd_true_arr = gd_app_arr * correction_factor
                except Exception:
                    gd_true_arr = gd_app_arr
            else:
                gd_true_arr = gd_app_arr
                
            # Viscosity
            eta_arr = tau_arr / gd_true_arr
            
            # --- Model Fitting ---
            results_txt = f"═══════════════════════════════════════════\n"
            results_txt += f"  ANÁLISE REOLÓGICA: {nome}\n"
            results_txt += f"═══════════════════════════════════════════\n\n"
            results_txt += f"Capilar: D={D_mm} mm, L={L_mm} mm\n"
            results_txt += f"Densidade: {Rho} g/cm³\n"
            results_txt += f"Ensaios analisados: {len(gd_true_arr)}\n"
            results_txt += f"Sensor Pressão: Pasta (sensor na câmara)\n"
            results_txt += f"Correção Weissenberg: {'Sim (n\'={:.3f})'.format(n_prime) if aplicar_weissenberg else 'Não'}\n\n"
            
            results_txt += "───────────────────────────────────────────\n"
            results_txt += "  AJUSTE DE MODELOS REOLÓGICOS\n"
            results_txt += "───────────────────────────────────────────\n\n"
            
            model_fits = {}
            best_model = None
            best_r2 = -np.inf
            
            for model_name, (model_func, param_names, guess_func, bounds) in models.MODELS.items():
                try:
                    p0 = guess_func(gd_true_arr, tau_arr)
                    popt, pcov = curve_fit(model_func, gd_true_arr, tau_arr, p0=p0, bounds=bounds, maxfev=10000)
                    
                    tau_pred = model_func(gd_true_arr, *popt)
                    r2 = r2_score(tau_arr, tau_pred)
                    
                    model_fits[model_name] = {'params': popt, 'r2': r2, 'param_names': param_names}
                    
                    if r2 > best_r2:
                        best_r2 = r2
                        best_model = model_name
                        
                except Exception as e:
                    model_fits[model_name] = {'params': None, 'r2': None, 'error': str(e)}
            
            # Display Results
            for model_name, fit_data in model_fits.items():
                is_best = (model_name == best_model)
                marker = "★" if is_best else " "
                
                if fit_data.get('params') is not None:
                    r2_val = fit_data['r2']
                    params = fit_data['params']
                    param_names = fit_data['param_names']
                    
                    results_txt += f"{marker} {model_name} (R²={r2_val:.4f})\n"
                    for i, pname in enumerate(param_names):
                        results_txt += f"    {pname}: {params[i]:.4g}\n"
                else:
                    results_txt += f"  {model_name}: Falha - {fit_data.get('error', 'Desconhecido')}\n"
                results_txt += "\n"
            
            results_txt += "───────────────────────────────────────────\n"
            results_txt += f"  MELHOR MODELO: {best_model} (R²={best_r2:.4f})\n"
            results_txt += "───────────────────────────────────────────\n\n"
            
            # Data Summary
            results_txt += "───────────────────────────────────────────\n"
            results_txt += "  DADOS CALCULADOS\n"
            results_txt += "───────────────────────────────────────────\n"
            results_txt += f"  Taxa Cisalhamento (s⁻¹): [{gd_true_arr.min():.1f} - {gd_true_arr.max():.1f}]\n"
            results_txt += f"  Tensão Parede (Pa):      [{tau_arr.min():.1f} - {tau_arr.max():.1f}]\n"
            results_txt += f"  Viscosidade (Pa.s):      [{eta_arr.min():.4f} - {eta_arr.max():.4f}]\n\n"
            
            # System Losses (ΔP)
            delta_p_arr = np.array(delta_p_list)
            results_txt += "───────────────────────────────────────────\n"
            results_txt += "  DIAGNÓSTICO DO SISTEMA\n"
            results_txt += "───────────────────────────────────────────\n"
            results_txt += f"  ΔP (P_linha - P_pasta):\n"
            results_txt += f"    Média: {delta_p_arr.mean():.3f} bar\n"
            results_txt += f"    Min:   {delta_p_arr.min():.3f} bar\n"
            results_txt += f"    Max:   {delta_p_arr.max():.3f} bar\n"
            
            if delta_p_arr.mean() > 0.5:
                results_txt += f"\n  ⚠️ Perdas elevadas no sistema (>{0.5} bar).\n"
                results_txt += f"  Verifique: vedação do êmbolo, vazamentos.\n"
            
            # Behavior Inference
            import reologia_fitting
            comportamento = reologia_fitting.inferir_comportamento_fluido(best_model, 
                {best_model: {'params': model_fits[best_model]['params'], 'R2': best_r2}} if best_model else {})
            results_txt += "\n───────────────────────────────────────────\n"
            results_txt += f"  COMPORTAMENTO: {comportamento}\n"
            results_txt += "───────────────────────────────────────────\n"
            
            self._set_result(results_txt)
            
            # Store data for export
            self.analysis_data = {
                'amostra': amostra,
                'gamma_dot': gd_true_arr,
                'tau_w': tau_arr,
                'eta': eta_arr,
                'model_fits': model_fits,
                'best_model': best_model,
                'best_r2': best_r2,
                'comportamento': comportamento,
                'n_prime': n_prime if aplicar_weissenberg else 1.0,
                'delta_p': delta_p_arr
            }
            
            # Enable export buttons
            self.btn_export_png.configure(state="normal")
            self.btn_export_pdf.configure(state="normal")
            
        except Exception as e:
            import traceback
            self._set_result(f"Erro na análise:\n{traceback.format_exc()}")
    
    def export_graphs(self):
        """Export analysis graphs as PNG files."""
        import matplotlib.pyplot as plt
        from tkinter import filedialog
        from datetime import datetime
        
        if not self.analysis_data:
            tk.messagebox.showerror("Erro", "Execute uma análise primeiro.")
            return
        
        # Ask for folder
        folder = filedialog.askdirectory(title="Selecione pasta para salvar gráficos")
        if not folder:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        amostra_nome = self.analysis_data['amostra']['nome']
        
        gamma = self.analysis_data['gamma_dot']
        tau = self.analysis_data['tau_w']
        eta = self.analysis_data['eta']
        best_model = self.analysis_data['best_model']
        
        imgs_generated = []
        
        # 1. Flow Curve (log-log)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.loglog(gamma, tau, 'o', markersize=8, label='Dados')
        
        # Add best model curve
        if best_model and self.analysis_data['model_fits'].get(best_model, {}).get('params') is not None:
            gamma_smooth = np.logspace(np.log10(gamma.min()), np.log10(gamma.max()), 100)
            model_func = models.MODELS[best_model][0]
            params = self.analysis_data['model_fits'][best_model]['params']
            tau_model = model_func(gamma_smooth, *params)
            ax.loglog(gamma_smooth, tau_model, '-', linewidth=2, label=f'{best_model}')
        
        ax.set_xlabel(r'Taxa de Cisalhamento $\dot{\gamma}$ (s$^{-1}$)', fontsize=12)
        ax.set_ylabel(r'Tensão de Cisalhamento $\tau_w$ (Pa)', fontsize=12)
        ax.set_title(f'Curva de Fluxo - {amostra_nome}', fontsize=14)
        ax.legend()
        ax.grid(True, which='both', alpha=0.3)
        
        path1 = f"{folder}/{timestamp}_{amostra_nome}_curva_fluxo.png"
        fig.savefig(path1, dpi=150, bbox_inches='tight')
        plt.close(fig)
        imgs_generated.append(path1)
        
        # 2. Viscosity Curve
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.loglog(gamma, eta, 's', markersize=8, color='green')
        ax.set_xlabel(r'Taxa de Cisalhamento $\dot{\gamma}$ (s$^{-1}$)', fontsize=12)
        ax.set_ylabel(r'Viscosidade $\eta$ (Pa.s)', fontsize=12)
        ax.set_title(f'Viscosidade vs Taxa de Cisalhamento - {amostra_nome}', fontsize=14)
        ax.grid(True, which='both', alpha=0.3)
        
        path2 = f"{folder}/{timestamp}_{amostra_nome}_viscosidade.png"
        fig.savefig(path2, dpi=150, bbox_inches='tight')
        plt.close(fig)
        imgs_generated.append(path2)
        
        # 3. All Models Comparison
        fig, ax = plt.subplots(figsize=(10, 7))
        ax.loglog(gamma, tau, 'ko', markersize=8, label='Dados')
        
        gamma_smooth = np.logspace(np.log10(gamma.min()), np.log10(gamma.max()), 100)
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        
        for i, (model_name, fit_data) in enumerate(self.analysis_data['model_fits'].items()):
            if fit_data.get('params') is not None:
                model_func = models.MODELS[model_name][0]
                tau_model = model_func(gamma_smooth, *fit_data['params'])
                r2 = fit_data['r2']
                ax.loglog(gamma_smooth, tau_model, '-', linewidth=2, color=colors[i % len(colors)],
                         label=f'{model_name} (R²={r2:.4f})')
        
        ax.set_xlabel(r'Taxa de Cisalhamento $\dot{\gamma}$ (s$^{-1}$)', fontsize=12)
        ax.set_ylabel(r'Tensão de Cisalhamento $\tau_w$ (Pa)', fontsize=12)
        ax.set_title(f'Comparação de Modelos - {amostra_nome}', fontsize=14)
        ax.legend(loc='best')
        ax.grid(True, which='both', alpha=0.3)
        
        path3 = f"{folder}/{timestamp}_{amostra_nome}_modelos.png"
        fig.savefig(path3, dpi=150, bbox_inches='tight')
        plt.close(fig)
        imgs_generated.append(path3)
        
        tk.messagebox.showinfo("Sucesso", f"{len(imgs_generated)} gráficos exportados para:\n{folder}")
    
    def export_pdf(self):
        """Export analysis as PDF report."""
        import reologia_report_pdf
        from tkinter import filedialog
        from datetime import datetime
        import pandas as pd
        
        if not self.analysis_data:
            tk.messagebox.showerror("Erro", "Execute uma análise primeiro.")
            return
        
        if not reologia_report_pdf.PDF_AVAILABLE:
            tk.messagebox.showerror("Erro", "Biblioteca FPDF não instalada.\nExecute: pip install fpdf")
            return
        
        # Ask for folder
        folder = filedialog.askdirectory(title="Selecione pasta para salvar relatório")
        if not folder:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        amostra = self.analysis_data['amostra']
        
        # First generate graphs (needed for PDF)
        self._generate_temp_graphs(folder, timestamp)
        
        # Prepare data
        df_res = pd.DataFrame({
            'Taxa Cisalhamento (s-1)': self.analysis_data['gamma_dot'],
            'Tensao Cisalhamento (Pa)': self.analysis_data['tau_w'],
            'Viscosidade (Pa.s)': self.analysis_data['eta']
        })
        
        # Prepare model summary
        summary_list = []
        for model_name, fit_data in self.analysis_data['model_fits'].items():
            if fit_data.get('params') is not None:
                param_names = fit_data['param_names']
                params_str = ", ".join([f"{n}={v:.4g}" for n, v in zip(param_names, fit_data['params'])])
                summary_list.append({'Modelo': model_name, 'R2': fit_data['r2'], 'Parametros': params_str})
        df_sum_modelo = pd.DataFrame(summary_list).sort_values(by='R2', ascending=False)
        
        lista_imgs = [f"{folder}/{timestamp}_curva_fluxo.png",
                      f"{folder}/{timestamp}_viscosidade.png",
                      f"{folder}/{timestamp}_modelos.png"]
        
        try:
            reologia_report_pdf.gerar_pdf(
                timestamp_str=timestamp,
                rho_g_cm3=amostra['densidade_g_cm3'],
                tempo_extrusao_info="Variavel",
                metodo_entrada="GUI",
                json_files=[],
                csv_path="",
                realizar_bagley=False,
                D_bagley=amostra['d_capilar_mm'],
                L_bagley_list=[amostra['l_capilar_mm']],
                realizar_mooney=False,
                L_mooney=amostra['l_capilar_mm'],
                D_mooney_list=[amostra['d_capilar_mm']],
                D_unico=amostra['d_capilar_mm'],
                L_unico=amostra['l_capilar_mm'],
                calib_path="",
                df_res=df_res,
                df_sum_modelo=df_sum_modelo,
                best_model_nome=self.analysis_data['best_model'],
                comportamento=self.analysis_data['comportamento'],
                lista_imgs=lista_imgs,
                output_folder=folder,
                fator_calibracao=1.0
            )
            tk.messagebox.showinfo("Sucesso", f"Relatório PDF gerado em:\n{folder}")
        except Exception as e:
            tk.messagebox.showerror("Erro", f"Falha ao gerar PDF:\n{e}")
    
    def _generate_temp_graphs(self, folder, timestamp):
        """Generate temporary graphs for PDF report."""
        import matplotlib.pyplot as plt
        
        gamma = self.analysis_data['gamma_dot']
        tau = self.analysis_data['tau_w']
        eta = self.analysis_data['eta']
        best_model = self.analysis_data['best_model']
        
        # 1. Flow Curve
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.loglog(gamma, tau, 'o', markersize=8, label='Dados')
        if best_model and self.analysis_data['model_fits'].get(best_model, {}).get('params') is not None:
            gamma_smooth = np.logspace(np.log10(gamma.min()), np.log10(gamma.max()), 100)
            model_func = models.MODELS[best_model][0]
            params = self.analysis_data['model_fits'][best_model]['params']
            tau_model = model_func(gamma_smooth, *params)
            ax.loglog(gamma_smooth, tau_model, '-', linewidth=2, label=f'{best_model}')
        ax.set_xlabel(r'$\dot{\gamma}$ (s$^{-1}$)')
        ax.set_ylabel(r'$\tau_w$ (Pa)')
        ax.legend()
        ax.grid(True, which='both', alpha=0.3)
        fig.savefig(f"{folder}/{timestamp}_curva_fluxo.png", dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # 2. Viscosity
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.loglog(gamma, eta, 's', markersize=8, color='green')
        ax.set_xlabel(r'$\dot{\gamma}$ (s$^{-1}$)')
        ax.set_ylabel(r'$\eta$ (Pa.s)')
        ax.grid(True, which='both', alpha=0.3)
        fig.savefig(f"{folder}/{timestamp}_viscosidade.png", dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # 3. All Models
        fig, ax = plt.subplots(figsize=(10, 7))
        ax.loglog(gamma, tau, 'ko', markersize=8, label='Dados')
        gamma_smooth = np.logspace(np.log10(gamma.min()), np.log10(gamma.max()), 100)
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        for i, (model_name, fit_data) in enumerate(self.analysis_data['model_fits'].items()):
            if fit_data.get('params') is not None:
                model_func = models.MODELS[model_name][0]
                tau_model = model_func(gamma_smooth, *fit_data['params'])
                ax.loglog(gamma_smooth, tau_model, '-', linewidth=2, color=colors[i % len(colors)],
                         label=f'{model_name} (R²={fit_data["r2"]:.4f})')
        ax.set_xlabel(r'$\dot{\gamma}$ (s$^{-1}$)')
        ax.set_ylabel(r'$\tau_w$ (Pa)')
        ax.legend(loc='best')
        ax.grid(True, which='both', alpha=0.3)
        fig.savefig(f"{folder}/{timestamp}_modelos.png", dpi=150, bbox_inches='tight')
        plt.close(fig)


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
            
            if len(set(d_values)) > 1:
                errors.append(f"Bagley: D deve ser igual em todas as amostras. Encontrado: {set(d_values)}")
            if len(set(l_values)) < 2:
                errors.append(f"Bagley: L deve ser diferente. Encontrado apenas: {set(l_values)}")
        
        # Mooney validation: same L, different D
        if do_mooney:
            d_values = [s['d_mm'] for s in samples]
            l_values = [s['l_mm'] for s in samples]
            
            if len(set(l_values)) > 1:
                errors.append(f"Mooney: L deve ser igual em todas as amostras. Encontrado: {set(l_values)}")
            if len(set(d_values)) < 2:
                errors.append(f"Mooney: D deve ser diferente. Encontrado apenas: {set(d_values)}")
        
        if errors:
            self.lbl_status.configure(text="❌ " + " | ".join(errors), text_color="red")
            self.btn_execute.configure(state="disabled")
            return False
        
        self.lbl_status.configure(text="✅ Seleção válida! Pronto para executar.", text_color="green")
        self.btn_execute.configure(state="normal")
        self.selected_samples = {s['nome']: s for s in samples}
        return True
    
    def run_corrections(self):
        """Execute Bagley and/or Mooney corrections."""
        import reologia_corrections
        import tempfile
        import os
        from datetime import datetime
        
        if not self.selected_samples:
            self.lbl_status.configure(text="❌ Valide a seleção primeiro.", text_color="red")
            return
        
        do_bagley = self.chk_bagley.get()
        do_mooney = self.chk_mooney.get()
        
        results_txt = "═══════════════════════════════════════════\n"
        results_txt += "  CORREÇÕES AVANÇADAS\n"
        results_txt += "═══════════════════════════════════════════\n\n"
        
        samples_list = list(self.selected_samples.values())
        
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
            from scipy.optimize import curve_fit
            from sklearn.metrics import r2_score
            
            results_txt += f"───────────────────────────────────────────\n"
            results_txt += f"  AJUSTE DE MODELOS (Dados Corrigidos)\n"
            results_txt += f"───────────────────────────────────────────\n\n"
            
            best_model = None
            best_r2 = -np.inf
            
            for model_name, (model_func, param_names, guess_func, bounds) in models.MODELS.items():
                try:
                    p0 = guess_func(final_gamma, final_tau)
                    popt, pcov = curve_fit(model_func, final_gamma, final_tau, p0=p0, bounds=bounds, maxfev=10000)
                    
                    tau_pred = model_func(final_gamma, *popt)
                    r2 = r2_score(final_tau, tau_pred)
                    
                    marker = ""
                    if r2 > best_r2:
                        best_r2 = r2
                        best_model = model_name
                    
                    results_txt += f"  {model_name} (R²={r2:.4f})\n"
                    for i, pname in enumerate(param_names):
                        results_txt += f"    {pname}: {popt[i]:.4g}\n"
                    results_txt += "\n"
                    
                except Exception as e:
                    results_txt += f"  {model_name}: Falha - {e}\n\n"
            
            if best_model:
                results_txt += f"───────────────────────────────────────────\n"
                results_txt += f"  ★ MELHOR MODELO: {best_model} (R²={best_r2:.4f})\n"
                results_txt += f"───────────────────────────────────────────\n"
        
        self._set_result(results_txt)

if __name__ == "__main__":
    app = App()
    app.mainloop()
