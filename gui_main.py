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
from gui_data_cleaning import DataCleaningWindow

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

    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        # Restore callback when frame is shown
        if self.controller.is_connected:
            self.controller.on_pressure_reading = self.update_plot_callback


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
        
        # Configure Treeview Style for larger font
        style = ttk.Style()
        style.configure("Treeview", font=("Arial", 12), rowheight=30)
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"))
        
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

        self.btn_delete = ctk.CTkButton(btn_frame, text="Excluir Amostra", 
                                         command=self.delete_sample, fg_color="red")
        self.btn_delete.pack(side="left", padx=5)
        
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
            testes = self.db.get_ensaios_by_amostra(a['id'])
            self.tree.insert("", "end", iid=str(a['id']), values=(a['id'], a['nome'], a['descricao'], a['data_criacao'], len(testes)))

    def delete_sample(self):
        """Deletes the selected sample from the history."""
        from tkinter import messagebox
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione uma amostra para excluir.")
            return
            
        amostra_id = int(selected[0])
        amostra_nome = self.tree.item(selected[0], "values")[1]
        
        if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir a amostra '{amostra_nome}'?\n\nIsso apagará permanentemente todos os ensaios e análises vinculadas!"):
            if self.db.delete_amostra(amostra_id):
                messagebox.showinfo("Sucesso", f"Amostra '{amostra_nome}' excluída.")
                self.refresh_list()
            else:
                messagebox.showerror("Erro", "Não foi possível excluir a amostra.")
    
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
        
        self.v_linha_low = 0
        self.p_pasta_low = 0
        self.v_linha_high = 0
        self.p_pasta_high = 0

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
        # Update labels with live values
        # Only update if NOT currently holding a captured value (simple check)
        # Actually, user wants to see live value BEFORE capturing. 
        # So checking if labels have "---" or not might be tricky.
        # Better to update separate "Live" labels or append to existing?
        # User request: "precisa ser apresentado ao usuário a leitura"
        # I will update the info labels.
        
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

class RelatorioWindow(ctk.CTkToplevel):
    def __init__(self, parent, analysis_data, export_callback=None):
        super().__init__(parent)
        self.analysis_data = analysis_data
        self.export_callback = export_callback
        
        # Make window modal-like or just top
        self.title(f"Relatório de Análise - {analysis_data['amostra']['nome']}")
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
        
        # Focus
        self.lift()
        self.focus_force()

    def _init_resumo(self):
        # Textbox for summary
        self.txt_resumo = ctk.CTkTextbox(self.tab_resumo, font=("Consolas", 14), wrap="word")
        self.txt_resumo.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Build Summary Text
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
        for model, fit in d['model_fits'].items():
            if fit.get('params') is not None:
                text += f"{model}: R²={fit['r2']:.4f}\n"
                for n, v in zip(fit['param_names'], fit['params']):
                    text += f"  {n}: {v:.4g}\n"
                text += "\n"
        
        self.txt_resumo.insert("1.0", text)
        self.txt_resumo.configure(state="disabled")

    def _init_graficos(self):
        # Tabview for sub-graphs
        self.graph_tabs = ctk.CTkTabview(self.tab_graficos)
        self.graph_tabs.pack(fill="both", expand=True)
        
        t1 = self.graph_tabs.add("Curva de Fluxo")
        t2 = self.graph_tabs.add("Viscosidade")
        t3 = self.graph_tabs.add("Ajuste de Modelos")
        
        # We need to defer plotting slightly to avoid layout issues? Or just plot.
        self._plot_figure(t1, self._create_flow_curve())
        self._plot_figure(t2, self._create_viscosity_curve())
        self._plot_figure(t3, self._create_model_curve())
        


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
                text += f"{model_name}: R²={fit['r2']:.4f}\n"
                for n, v in zip(fit['param_names'], fit['params']):
                    text += f"  {n}: {v:.4g}\n"
                text += "\n"
        
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
            
        self.txt_resumo.insert("1.0", text)
        self.txt_resumo.configure(state="disabled")

    def _init_graficos(self):
        self.graph_tabs = ctk.CTkTabview(self.tab_graficos)
        self.graph_tabs.pack(fill="both", expand=True)
        
        t1 = self.graph_tabs.add("Curva de Fluxo")
        t2 = self.graph_tabs.add("Viscosidade")
        t3 = self.graph_tabs.add("Ajuste de Modelos")
        
        desc_fluxo = "Explicação: Relaciona a Tensão (τ) vs Taxa (γ̇). O formato da curva define se o fluido é Newtoniano, Pseudoplástico ou Viscoplástico."
        desc_visc = "Explicação: Mostra a Viscosidade Aparente vs Taxa. A inclinação negativa indica comportamento 'Shear Thinning' (pseudoplástico)."
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
        ax.plot(self.analysis_data['gamma_dot'], self.analysis_data['tau_w'], 'o-', label='Experimental')
        ax.set_title("Curva de Fluxo")
        ax.set_xlabel("Taxa de Cisalhamento (1/s)")
        ax.set_ylabel("Tensão de Cisalhamento (Pa)")
        ax.grid(True)
        return fig

    def _create_viscosity_curve(self):
        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(self.analysis_data['gamma_dot'], self.analysis_data['eta'], 's-', color='orange', label='Viscosidade')
        ax.set_title("Viscosidade Aparente")
        ax.set_xlabel("Taxa de Cisalhamento (1/s)")
        ax.set_ylabel("Viscosidade (Pa.s)")
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.grid(True, which="both", ls="-")
        return fig

    def _create_model_curve(self):
        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        
        x = self.analysis_data['gamma_dot']
        y = self.analysis_data['tau_w']
        ax.plot(x, y, 'ko', label='Experimental', alpha=0.6)
        
        # Use logspace for smoother model curves
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
        
        for name, fit in self.analysis_data['model_fits'].items():
            if fit.get('params') is not None:
                # Use the function from the models module dictionary
                if name in models.MODELS:
                    func = models.MODELS[name][0]
                    try:
                        y_pred = func(x_smooth, *fit['params'])
                        ax.loglog(x_smooth, y_pred, linestyle='--', label=f"{name}", color=colors[color_idx % len(colors)])
                        color_idx += 1
                    except Exception as e:
                        print(f"Erro ao plotar modelo {name}: {e}")
                    
        ax.set_title("Ajuste de Modelos")
        ax.set_xlabel("Taxa (1/s)")
        ax.set_ylabel("Tensão (Pa)")
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.legend()
        ax.grid(True, which="both", alpha=0.3)
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
        cols = ("Taxa (1/s)", "Tensão (Pa)", "Viscosidade (Pa.s)")
        tree = ttk.Treeview(container, columns=cols, show="headings", height=15)
        
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=200, anchor="center")
            
        # Scrollbar
        vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        d = self.analysis_data
        if 'gamma_dot' in d and len(d['gamma_dot']) > 0:
            for g, t, e in zip(d['gamma_dot'], d['tau_w'], d['eta']):
                tree.insert("", "end", values=(f"{g:.2f}", f"{t:.2f}", f"{e:.4f}"))
        else:
            tree.insert("", "end", values=("Nenhum dado", "", ""))

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
        
        self.btn_batch = ctk.CTkButton(self.actions_frame, text="Análise em Lote (Selecionados)", command=self.run_batch_analysis, fg_color="purple")
        self.btn_batch.pack(side="right", padx=10, pady=10)
        
        self.btn_cleaning = ctk.CTkButton(self.actions_frame, text="Limpeza / Outliers", command=self.open_cleaning_window, fg_color="orange")
        self.btn_cleaning.pack(side="left", padx=10, pady=10)

        self.btn_delete = ctk.CTkButton(self.actions_frame, text="Excluir Amostra", command=self.delete_selected_sample, fg_color="red")
        self.btn_delete.pack(side="left", padx=10, pady=10)
        
        # Selection Bind
        self.tree.bind("<<TreeviewSelect>>", self.on_select_sample)
        
        # Options
        self.opt_frame = ctk.CTkFrame(self)
        self.opt_frame.pack(fill="x", padx=20, pady=5)
        
        self.chk_weissenberg = ctk.CTkCheckBox(self.opt_frame, text="Aplicar Correção Weissenberg-Rabinowitsch")
        self.chk_weissenberg.pack(side="left", padx=10)
        self.chk_weissenberg.select()  # Default: enabled
        
        # Export Buttons Frame
        self.export_frame = ctk.CTkFrame(self)
        self.export_frame.pack(fill="x", padx=20, pady=5)
        
        self.btn_view_report = ctk.CTkButton(self.export_frame, text="Visualizar Relatório", 
                                             command=self.open_report_window, state="disabled", fg_color="orange")
        self.btn_view_report.pack(side="left", padx=10)
        
        self.btn_export_png = ctk.CTkButton(self.export_frame, text="Exportar Gráficos (PNG)", 
                                             command=self.export_graphs, state="disabled")
        # self.btn_export_png.pack(side="left", padx=10) # Optional now? Keep distinct.
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

    def run_analysis(self, auto=False):
        """Main method for single sample analysis with full UI update."""
        if not self.selected_amostra_id:
            return

        result = self._perform_statistical_analysis(self.selected_amostra_id, self.chk_weissenberg.get(), auto=auto, save=not auto)
        
        if result['success']:
            self._set_result(result['text'])
            self.analysis_data = result['data']
            self.btn_export_png.configure(state="normal")
            self.btn_export_pdf.configure(state="normal")
            self.btn_view_report.configure(state="normal")
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

    def delete_selected_sample(self):
        """Deletes the selected sample after confirmation."""
        selected = self.tree.selection()
        if not selected:
            tk.messagebox.showwarning("Aviso", "Selecione uma amostra para fechar.")
            return
        
        # We delete just the first one if multiple selected (safer)
        amostra_id = int(selected[0])
        amostra_nome = self.tree.item(selected[0], "values")[1] # Column 1 is Name
        
        if tk.messagebox.askyesno("Confirmar Exclusão", f"Deseja realmente excluir a amostra '{amostra_nome}'?\n\nEsta ação é irreversível e apagará todos os dados vinculados."):
            if self.db.delete_amostra(amostra_id):
                tk.messagebox.showinfo("Sucesso", "Amostra excluída com sucesso.")
                self.refresh_list()
                self._set_result("") # Clear result box
                self.analysis_data = None
            else:
                tk.messagebox.showerror("Erro", "Falha ao excluir amostra.")

    def _perform_statistical_analysis(self, amostra_id, aplicar_weissenberg, auto=False, save=True):
        """
        Isolated reological logic.
        Returns a dictionary with results, status and data.
        """
        from scipy.stats import linregress
        from sklearn.metrics import r2_score
        import json
        
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
            
            for index, row in df.iterrows():
                massa_g = row['massa_g']
                tempo_s = row['duracao_s']
                p_pasta_bar = row['pressao_pasta_bar']
                p_linha_bar = row['pressao_linha_bar']
                
                if tempo_s <= 0 or massa_g <= 0 or p_pasta_bar <= 0: continue
                
                delta_p = p_linha_bar - p_pasta_bar
                delta_p_list.append(delta_p)
                
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
            
            # Corrections
            n_prime = 1.0
            if aplicar_weissenberg:
                try:
                    log_gd = np.log(gd_app_arr)
                    log_tau = np.log(tau_arr)
                    slope, _, _, _, _ = linregress(log_gd, log_tau)
                    n_prime = slope
                    gd_true_arr = gd_app_arr * ((3 * n_prime + 1) / (4 * n_prime))
                except Exception: gd_true_arr = gd_app_arr
            else: gd_true_arr = gd_app_arr
                
            eta_arr = tau_arr / gd_true_arr
            
            # Model Fitting
            model_fits = {}
            best_model = None
            best_r2 = -np.inf
            
            for m_name, (m_func, p_names, g_func, bnds) in models.MODELS.items():
                try:
                    p0 = g_func(gd_true_arr, tau_arr)
                    popt, _ = curve_fit(m_func, gd_true_arr, tau_arr, p0=p0, bounds=bnds, maxfev=10000)
                    tau_pred = m_func(gd_true_arr, *popt)
                    r2 = r2_score(tau_arr, tau_pred)
                    model_fits[m_name] = {'params': popt, 'r2': r2, 'param_names': p_names}
                    if r2 > best_r2:
                        best_r2 = r2
                        best_model = m_name
                except Exception as e:
                    model_fits[m_name] = {'params': None, 'r2': None, 'error': str(e)}

            # Generate Text Result
            results_txt = f"═══════════════════════════════════════════\n"
            results_txt += f"  ANÁLISE REOLÓGICA: {nome}\n"
            results_txt += f"═══════════════════════════════════════════\n\n"
            results_txt += f"Capilar: D={D_mm} mm, L={L_mm} mm\n"
            results_txt += f"Densidade: {Rho} g/cm³\n"
            results_txt += f"Correção Weissenberg: {'Sim (n\'={:.3f})'.format(n_prime) if aplicar_weissenberg else 'Não'}\n\n"
            
            results_txt += "───────────────────────────────────────────\n"
            results_txt += "  AJUSTE DE MODELOS REOLÓGICOS\n"
            results_txt += "───────────────────────────────────────────\n\n"
            
            for m_name, fit_data in model_fits.items():
                if fit_data.get('params') is not None:
                    marker = "★" if m_name == best_model else " "
                    results_txt += f"{marker} {m_name} (R²={fit_data['r2']:.4f})\n"
                    for i, pn in enumerate(fit_data['param_names']):
                        results_txt += f"    {pn}: {fit_data['params'][i]:.4g}\n"
                results_txt += "\n"
            
            import reologia_fitting
            comportamento = reologia_fitting.inferir_comportamento_fluido(best_model, 
                {best_model: {'params': model_fits[best_model]['params'], 'R2': best_r2}} if best_model else {})
            
            results_txt += f"───────────────────────────────────────────\n"
            results_txt += f"  COMPORTAMENTO: {comportamento}\n"
            results_txt += f"───────────────────────────────────────────\n"

            # Prepare data object
            analysis_data = {
                'amostra': amostra, 'gamma_dot': gd_true_arr, 'tau_w': tau_arr, 'eta': eta_arr,
                'model_fits': model_fits, 'best_model': best_model, 'best_r2': best_r2,
                'comportamento': comportamento, 'n_prime': n_prime if aplicar_weissenberg else 1.0,
                'delta_p': np.array(delta_p_list)
            }

            if save:
                params_storage = {
                    'best_model': best_model, 'n_prime': n_prime, 'is_weissenberg': aplicar_weissenberg,
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
    
    def export_pdf(self, analysis_data=None):
        """Export analysis as PDF report."""
        import reologia_report_pdf
        from tkinter import filedialog
        from datetime import datetime
        import pandas as pd
        
        # Use provided data or current data
        data_to_use = analysis_data if analysis_data else self.analysis_data
        
        if not data_to_use:
            tk.messagebox.showerror("Erro", "Execute uma análise primeiro.")
            return
        
        if not reologia_report_pdf.PDF_AVAILABLE:
            tk.messagebox.showerror("Erro", "Biblioteca FPDF não instalada.\nExecute: pip install fpdf")
            return
        
        import os as os_sys
        
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
        
        folder = os_sys.path.dirname(filepath)
        
        try:
            # Generate graphs in TEMP folder to avoid cluttering user directory
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            try:
                self._generate_temp_graphs(temp_dir, timestamp, data_to_use)
                
                # Prepare data
                df_res = pd.DataFrame({
                    'Taxa Cisalhamento (s-1)': data_to_use['gamma_dot'],
                    'Tensao Cisalhamento (Pa)': data_to_use['tau_w'],
                    'Viscosidade (Pa.s)': data_to_use['eta']
                })
                
                # Prepare model summary
                summary_list = []
                for model_name, fit_data in data_to_use['model_fits'].items():
                    if fit_data.get('params') is not None:
                        param_names = fit_data['param_names']
                        params_str = ", ".join([f"{n}={v:.4g}" for n, v in zip(param_names, fit_data['params'])])
                        summary_list.append({'Modelo': model_name, 'R2': fit_data['r2'], 'Parametros': params_str})
                df_sum_modelo = pd.DataFrame(summary_list).sort_values(by='R2', ascending=False)
                
                lista_imgs = [os_sys.path.join(temp_dir, f"{timestamp}_curva_fluxo.png"),
                              os_sys.path.join(temp_dir, f"{timestamp}_viscosidade.png"),
                              os_sys.path.join(temp_dir, f"{timestamp}_modelos.png")]
                
                reologia_report_pdf.gerar_pdf(
                    timestamp_str=timestamp,
                    rho_g_cm3=data_to_use['amostra']['densidade_g_cm3'],
                    tempo_extrusao_info="Variavel",
                    metodo_entrada="GUI",
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
                    output_filename=filepath
                )
                tk.messagebox.showinfo("Sucesso", f"Relatório PDF gerado em:\n{filepath}")
                
            finally:
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(tb)
            tk.messagebox.showerror("Erro ao Gerar PDF", f"Falha na geração do relatório:\n{e}\n\nDetalhes no console.")
        filepath = filedialog.asksaveasfilename(
            title="Salvar Relatório PDF",
            defaultextension=".pdf",
            initialfile=suggested_name,
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        # Get folder from filepath
        folder = os_sys.path.dirname(filepath)
        if not folder:
            folder = "."
        
        # Ensure folder exists
        if not os_sys.path.exists(folder):
            try:
                os_sys.makedirs(folder, exist_ok=True)
            except Exception as e:
                tk.messagebox.showerror("Erro", f"Não foi possível criar a pasta:\n{folder}\n\nErro: {e}")
                return
        
        try:
            # Generate graphs in TEMP folder to avoid cluttering user directory
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            try:
                self._generate_temp_graphs(temp_dir, timestamp)
                
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
                
                lista_imgs = [os_sys.path.join(temp_dir, f"{timestamp}_curva_fluxo.png"),
                              os_sys.path.join(temp_dir, f"{timestamp}_viscosidade.png"),
                              os_sys.path.join(temp_dir, f"{timestamp}_modelos.png")]
                
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
                    fator_calibracao=1.0,
                    output_filename=filepath
                )
                tk.messagebox.showinfo("Sucesso", f"Relatório PDF gerado em:\n{filepath}")
                
            finally:
                # Cleanup temp dir
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            tk.messagebox.showerror("Erro", f"Falha ao gerar PDF:\n{e}\n\nDetalhes:\n{tb}")
    
    def _generate_temp_graphs(self, folder, timestamp, analysis_data=None):
        """Generate temporary graphs for PDF report."""
        import matplotlib.pyplot as plt
        from os import path as os_path
        
        data = analysis_data if analysis_data else self.analysis_data
        
        gamma = data['gamma_dot']
        tau = data['tau_w']
        eta = data['eta']
        best_model = data['best_model']
        
        # 1. Flow Curve
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.loglog(gamma, tau, 'o', markersize=8, label='Dados')
        if best_model and data['model_fits'].get(best_model, {}).get('params') is not None:
            gamma_smooth = np.logspace(np.log10(gamma.min()), np.log10(gamma.max()), 100)
            model_func = models.MODELS[best_model][0]
            params = data['model_fits'][best_model]['params']
            tau_model = model_func(gamma_smooth, *params)
            ax.loglog(gamma_smooth, tau_model, '-', linewidth=2, label=f'{best_model}')
        ax.set_xlabel(r'$\dot{\gamma}$ (s$^{-1}$)')
        ax.set_ylabel(r'$\tau_w$ (Pa)')
        ax.legend()
        ax.grid(True, which='both', alpha=0.3)
        fig.savefig(os_path.join(folder, f"{timestamp}_curva_fluxo.png"), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # 2. Viscosity
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.loglog(gamma, eta, 's', markersize=8, color='green')
        ax.set_xlabel(r'$\dot{\gamma}$ (s$^{-1}$)')
        ax.set_ylabel(r'$\eta$ (Pa.s)')
        ax.grid(True, which='both', alpha=0.3)
        fig.savefig(os_path.join(folder, f"{timestamp}_viscosidade.png"), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        # 3. All Models
        fig, ax = plt.subplots(figsize=(10, 7))
        ax.loglog(gamma, tau, 'ko', markersize=8, label='Dados')
        gamma_smooth = np.logspace(np.log10(gamma.min()), np.log10(gamma.max()), 100)
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        for i, (model_name, fit_data) in enumerate(data['model_fits'].items()):
            if fit_data.get('params') is not None:
                model_func = models.MODELS[model_name][0]
                tau_model = model_func(gamma_smooth, *fit_data['params'])
                ax.loglog(gamma_smooth, tau_model, '-', linewidth=2, color=colors[i % len(colors)],
                         label=f'{model_name} (R²={fit_data["r2"]:.4f})')
        ax.set_xlabel(r'$\dot{\gamma}$ (s$^{-1}$)')
        ax.set_ylabel(r'$\tau_w$ (Pa)')
        ax.legend(loc='best')
        ax.grid(True, which='both', alpha=0.3)
        fig.savefig(os_path.join(folder, f"{timestamp}_modelos.png"), dpi=150, bbox_inches='tight')
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
