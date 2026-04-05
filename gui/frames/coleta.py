import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from customtkinter import CTkInputDialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FormatStrFormatter, MaxNLocator
import time
import numpy as np

# Pressure trigger thresholds (bar)
PRESSURE_THRESHOLD_START = 0.15  # P_Pasta acima deste valor inicia gravação
PRESSURE_THRESHOLD_STOP  = 0.10  # P_Pasta abaixo deste valor para gravação
MIN_RECORDING_TIME       = 2.0   # Tempo mínimo (s) antes de permitir auto-parada
MIN_STEADY_STATE_TIME    = 5.0   # Tempo mínimo (s) em regime antes de auto-parada

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
        self.entry_pyield = create_entry(self.input_frame, "P. Escoam. (bar):", 4)
        self.entry_pyield.insert(0, "0.15")  # Default safe threshold

        # --- Middle Section: Graph ---
        self.graph_frame = ctk.CTkFrame(self)
        self.graph_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Matplotlib Figure with inherited style
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        self.ax.set_title("Pressão Real-time")
        self.ax.set_xlabel("Tempo (s)")
        self.ax.set_ylabel("Pressão (bar)")
        self.ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        self.ax.yaxis.set_major_locator(MaxNLocator(nbins='auto', steps=[1, 2, 5, 10]))
        
        self.line_l, = self.ax.plot([], [], label='Linha') 
        self.line_p, = self.ax.plot([], [], label='Pasta') 
        self.ax.legend()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # --- Bottom Section: Controls & Monitor ---
        self.control_frame = ctk.CTkFrame(self, height=100)
        self.control_frame.pack(fill="x", padx=20, pady=20)
        
        self.control_frame.grid_columnconfigure(0, weight=1)
        self.control_frame.grid_columnconfigure(1, weight=1)
        self.control_frame.grid_columnconfigure(2, weight=1)
        
        self.lbl_p_linha = ctk.CTkLabel(self.control_frame, text="P. Linha: 0.00 bar", font=("Consolas", 20))
        self.lbl_p_linha.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        self.lbl_p_pasta = ctk.CTkLabel(self.control_frame, text="P. Pasta: 0.00 bar", font=("Consolas", 20))
        self.lbl_p_pasta.grid(row=0, column=1, padx=20, pady=10, sticky="w")
        
        # New: Status label for discrete messages (no popup)
        self.lbl_status = ctk.CTkLabel(self.control_frame, text="", font=ctk.CTkFont(size=14, slant="italic"), text_color="#a6e3a1")
        self.lbl_status.grid(row=1, column=0, columnspan=2, padx=20, pady=(0,5), sticky="w")
        
        button_container = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        button_container.grid(row=0, column=2, rowspan=2, padx=20, pady=10, sticky="e")
        
        self.btn_end_session = ctk.CTkButton(button_container, text="FINALIZAR ENSAIO", command=self._end_session, 
                                             fg_color="#f38ba8", hover_color="#eba0ac", text_color="#11111b")
        self.btn_end_session.pack(side="left", padx=(0, 10))
        self.btn_end_session.pack_forget() # Hidden initially
        
        self.btn_start = ctk.CTkButton(button_container, text="INICIAR SESSÃO", command=self.toggle_collection)
        self.btn_start.pack(side="right")

        # Data storage for plotting
        self.times = []
        self.p1_data = []
        self.p2_data = []
        self.v1_data = []
        self.v2_data = []
        self.start_time = None
        self.collecting = False
        self.connection_lost = False
        
        # Pressure trigger state: 'idle' | 'waiting' | 'recording'
        self.trigger_state = 'idle'

        # Regime detection state
        self.regime_detected = False
        self.idx_regime_start = None
        self.steady_state_start = None
        self.pasta_peaked = False
        self._K_calibration = None  # Mass cross-validation constant

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
        self.btn_start.configure(state="normal", text="INICIAR COLETA", fg_color="#1f6aa5")

    def toggle_collection(self):
        if not self.controller.is_connected:
            # Auto-connect attempt
            success, msg = self.controller.find_and_connect()
            if success:
                self.controller.start_reading()
            else:
                tk.messagebox.showerror("Erro", f"Arduino não conectado. Falha ao reconectar: {msg}")
                return

        if self.trigger_state == 'idle':
            # --- Transition: idle → waiting ---
            # Validate Inputs with comprehensive checks
            errors = []
            
            # Validate sample name
            amostra_nome = self.entry_amostra.get().strip()
            if not amostra_nome:
                errors.append("• ID da Amostra é obrigatório")
            
            # Validate numeric fields with ranges
            def validate_numeric(entry, name, min_val, max_val, allow_zero=False):
                val_str = entry.get().strip().replace(',', '.')
                if not val_str:
                    return None, f"• {name} é obrigatório"
                try:
                    val = float(val_str)
                    if val < 0 or (val == 0 and not allow_zero):
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
            
            pyield_val, pyield_err = validate_numeric(self.entry_pyield, "P. Escoamento", 0.0, 10.0, allow_zero=True)
            if pyield_err: errors.append(pyield_err)
            
            if errors:
                tk.messagebox.showerror("Erro de Validação", 
                    "Corrija os seguintes erros:\n\n" + "\n".join(errors))
                return

            # Store the validated custom pyield for this session's mass partition
            self.session_pyield = pyield_val

            # Start Session: Enter waiting state
            self.trigger_state = 'waiting'
            self.collecting = True
            self._K_calibration = None  # Reset cross-calibration memory for new session
            self.lbl_status.configure(text="Sessão iniciada. Pontos serão gravados sequencialmente.")
            
            # Show End Session button
            self.btn_end_session.pack(side="left", padx=(0, 10))
            
            self._prepare_for_next_point()
            
        else:
            # --- Manual override: stop from waiting or recording state ---
            self._manual_stop()
            
    def _prepare_for_next_point(self):
        """Prepares UI and variables for the next point in the session."""
        self.btn_start.configure(
            text=f"AGUARDANDO (> {PRESSURE_THRESHOLD_START:.2f} bar)",
            fg_color="#e6a817"  # yellow/amber
        )
        self.start_time = None
        self.times = []
        self.p1_data = []
        self.p2_data = []
        self.v1_data = []
        self.v2_data = []
        
        # Ocultar o gráfico antes do início (conforme pedido)
        self.line_l.set_data([], [])
        self.line_p.set_data([], [])
        self.canvas.draw_idle()
        
        # Reset regime detection
        self.regime_detected = False
        self.idx_regime_start = None
        self.steady_state_start = None
        self.pasta_peaked = False
        
        self.controller.stop_reading()
        self.controller.reset_ema()
        self.controller.start_reading()
        
        self.line_l.set_data([], [])
        self.line_p.set_data([], [])
        for patch in self.ax.patches[:]:
            patch.remove()
        # Remove extra lines (regime markers) beyond base Linha/Pasta
        while len(self.ax.lines) > 2:
            self.ax.lines[-1].remove()
        self.ax.legend(['Linha', 'Pasta'])
        self.ax.set_xlim(0, 10)  # Reset X axis to initial rolling buffer width
        self.canvas.draw()
    
    def _end_session(self):
        """Ends the entire multi-point session and returns to idle."""
        was_recording = self.trigger_state == 'recording'
        self.trigger_state = 'asking_mass'
        self.collecting = False
        
        # Hide End Session button
        self.btn_end_session.pack_forget()
        
        self.btn_start.configure(text="INICIAR SESSÃO", fg_color="#1f6aa5")
        
        if was_recording and len(self.times) > 0:
            self._ask_mass_and_save()
            
        self.trigger_state = 'idle'
        self.lbl_status.configure(text="Sessão finalizada. Arquivo fechado.")

    def _manual_stop(self):
        """Manual override: stop recording and save current point, then wait for next point."""
        if self.trigger_state == 'recording' and len(self.times) > 0:
            self.trigger_state = 'asking_mass'
            self._ask_mass_and_save()
        elif self.trigger_state == 'recording':
            self.lbl_status.configure(text="Ponto cancelado (sem dados suficientes).")
            
        if self.trigger_state != 'idle':
            self.trigger_state = 'waiting'
            self._prepare_for_next_point()
    
    def _auto_stop(self):
        """Automatic stop triggered by pressure dropping below threshold."""
        # MUST change state BEFORE showing dialog to prevent re-entrant calls
        if self.trigger_state != 'idle':
            self.trigger_state = 'asking_mass'
            
            valid_point = False
            if len(self.p2_data) > 0:
                avg_p = sum(self.p2_data) / len(self.p2_data)
                # Se a pressão média for muito baixa, foi apenas um esbarrão mecânico ou ruído que disparou o sensor
                if avg_p > (PRESSURE_THRESHOLD_START / 2.0):
                    valid_point = True
            
            if valid_point:
                self._ask_mass_and_save()
            else:
                self.lbl_status.configure(text="Ponto ignorado (ruído ou esbarrão detectado).")
                
            self.trigger_state = 'waiting'
            self._prepare_for_next_point()
    
    def _ask_mass_and_save(self):
        """Show mass dialog and save the collected point."""
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
        # Capture exact physical time from the background thread to prevent GUI lag from stretching the graph
        ts = time.time()
        # Called from thread, update via after
        self.after(0, self._update_gui, p1, p2, v1, v2, ts)

    def _update_gui(self, p1, p2, v1, v2, ts=None):
        if ts is None:
            ts = time.time()
            
        # Always update pressure labels
        self.lbl_p_linha.configure(text=f"P. Linha: {p1:.2f} bar")
        self.lbl_p_pasta.configure(text=f"P. Pasta: {p2:.2f} bar")
        
        if self.trigger_state in ['idle', 'waiting']:
            # Manter apenas histórico mínimo para o pre-trigger (economiza CPU e trava a interface)
            self.p2_data.append(p2)
            self.p1_data.append(p1)
            if len(self.p2_data) > 10:
                self.p2_data.pop(0)
                self.p1_data.pop(0)

            if self.trigger_state == 'waiting':
                # Trigger Clássico: P_Pasta venciando a tensão de escoamento real
                recent_p2 = self.p2_data[-3:] if len(self.p2_data) >= 3 else [p2]
                pasta_trigger = (sum(recent_p2) / len(recent_p2)) > PRESSURE_THRESHOLD_START
                
                # Trigger Antecipado: Queda brusca associada à abertura da Válvula Pneumática
                linha_trigger = False
                if len(self.p1_data) >= 5:
                    p1_old = self.p1_data[0] # Leitura ~1s atrás
                    p1_recent = sum(self.p1_data[-3:]) / len(self.p1_data[-3:])
                    # Se a linha estava pressurizada (>0.2 bar) e caiu de repente pela metade (válvula abriu expandindo pro capilar vazio)
                    if p1_old > 0.2 and p1_recent < (p1_old * 0.5):
                        linha_trigger = True

                if pasta_trigger or linha_trigger:
                    self.trigger_state = 'recording'
                    self.regime_detected = False
                    self.idx_regime_start = None
                    
                    # Zera o tempo e arrays definitivos
                    self.start_time = ts
                    self.times = [0.0]
                    self.p1_data = [p1]
                    self.p2_data = [p2]
                    self.v1_data = [v1]
                    self.v2_data = [v2]
                        
                    # Libera o limite X para a gravação
                    self.ax.set_xlim(auto=True)
                    self.line_l.set_data(self.times, self.p1_data)
                    self.line_p.set_data(self.times, self.p2_data)
                    self.btn_start.configure(text="GRAVANDO... (Clique para parar)", fg_color="red")
        
        elif self.trigger_state == 'recording':
            # Recording data
            if self.start_time is None:
                self.start_time = ts
                
            t = ts - self.start_time
            self.times.append(t)
            self.p1_data.append(p1)
            self.p2_data.append(p2)
            self.v1_data.append(v1)
            self.v2_data.append(v2)
            
            # Update graph (every 5th point for UI performance / anti-stutter)
            if len(self.times) % 5 == 0:
                self.line_l.set_data(self.times, self.p1_data)
                self.line_p.set_data(self.times, self.p2_data)
                self.ax.relim()
                self.ax.autoscale_view()
                self.canvas.draw_idle()
            
            # --- Regime detection using Moving Window CV ---
            # Para lidar com casos onde P_Linha e P_Pasta sobem juntos (rampa gradual)
            WINDOW_SIZE = 30  # Janela de ~3 segundos (a 10Hz)
            
            if len(self.p2_data) >= WINDOW_SIZE:
                recent_window = self.p2_data[-WINDOW_SIZE:]
                mean_w = np.mean(recent_window)
                cv_w = (np.std(recent_window) / mean_w * 100) if mean_w > 0.05 else 100.0
                
                # 1. Detectar o início se estiver bem estável nesta janela
                if not self.regime_detected and mean_w > 0.05 and cv_w <= 2.5:
                    self.regime_detected = True
                    self.idx_regime_start = len(self.p2_data) - WINDOW_SIZE
                    self.steady_state_start = self.times[self.idx_regime_start]
                    print(f"Regime detectado via Janela (CV={cv_w:.2f}%) no tempo {self.steady_state_start:.1f}s")
                
                # 2. Monitorar e corrigir durante o regime
                if self.regime_detected and self.idx_regime_start is not None:
                    regime_data = self.p2_data[self.idx_regime_start:]
                    t_in_regime = t - self.steady_state_start
                    
                    overall_mean = np.mean(regime_data)
                    overall_cv = (np.std(regime_data) / overall_mean * 100) if overall_mean > 0 else 0
                    
                    # Self-healing: se a janela atual é muito mais estável que o regime global,
                    # significa que temos resíduo de rampa no início. Avança o início imediatamente.
                    if overall_cv > 3.0 and cv_w < 2.0 and len(regime_data) > WINDOW_SIZE:
                        self.idx_regime_start = len(self.p2_data) - WINDOW_SIZE
                        self.steady_state_start = self.times[self.idx_regime_start]
                        # Recalcular com dados aparados
                        regime_data = self.p2_data[self.idx_regime_start:]
                        t_in_regime = t - self.steady_state_start
                        overall_mean = np.mean(regime_data)
                        overall_cv = (np.std(regime_data) / overall_mean * 100) if overall_mean > 0 else 0
                        print(f"Auto-correção: avançando início do regime (CV global {overall_cv:.1f}%)")
                    
                    # Feedback em tempo real (usando CV já corrigido)
                    if overall_cv < 3.0 and t_in_regime >= MIN_STEADY_STATE_TIME:
                        self.lbl_status.configure(
                            text=f"✅ Regime estável ({t_in_regime:.0f}s, CV={overall_cv:.1f}%) — OK para parar",
                            text_color="#a6e3a1")
                    elif overall_cv < 3.0:
                        self.lbl_status.configure(
                            text=f"⏳ Estável, aguardando tempo mínimo ({t_in_regime:.0f}/{MIN_STEADY_STATE_TIME:.0f}s)",
                            text_color="#f9e2af")
                    elif overall_cv < 6.0:
                        self.lbl_status.configure(
                            text=f"⏳ Estabilizando... ({t_in_regime:.0f}s, CV={overall_cv:.1f}%)",
                            text_color="#f9e2af")
                    else:
                        self.lbl_status.configure(
                            text=f"⏳ Aguardando regime (CV={overall_cv:.1f}%)",
                            text_color="#fab387")
                                
                    # Drop-out: se a pressão cair drasticamente (ex: válvula fechou)
                    if p2 < (self.p2_data[self.idx_regime_start] * 0.7) and p2 < PRESSURE_THRESHOLD_STOP:
                       self.regime_detected = False
            else:
                self.lbl_status.configure(
                    text=f"🔄 Rampa... P_Pasta={p2:.2f} / P_Linha={p1:.2f} bar",
                    text_color="#89b4fa")
            
            # Register if sample ever reached the working pressure threshold
            if p2 > PRESSURE_THRESHOLD_START:
                self.pasta_peaked = True
            
            # --- Auto-stop with minimum steady-state time (Melhoria 4) ---
            # Exige que a pressão tenha ultrapassado o threshold ao menos uma vez para não abortar rampas lentas precocemente
            if self.pasta_peaked and p2 < PRESSURE_THRESHOLD_STOP and t > MIN_RECORDING_TIME:
                if self.regime_detected and self.steady_state_start is not None:
                    t_regime = t - self.steady_state_start
                    if t_regime >= MIN_STEADY_STATE_TIME:
                        self._auto_stop()
                    # If not enough regime time, ignore (likely noise)
                else:
                    self._auto_stop()  # Fallback: original behavior

    def save_point(self, massa):
        try:
            # 1. Get/Create Sample
            nome = self.entry_amostra.get().strip()
            desc = "Coleta via GUI"
            d_mm = float(self.entry_d.get().replace(',', '.'))
            l_mm = float(self.entry_l.get().replace(',', '.'))
            rho = float(self.entry_rho.get().replace(',', '.'))
            
            # Get the session's empirical yield pressure
            p_yield_bar = getattr(self, 'session_pyield', None)
            
            # Check if sample exists, if not create
            amostra = self.db.get_amostra_by_name(nome)
            if amostra:
                amostra_id = amostra['id']
                # Always update p_escoamento with the latest operator observation
                if p_yield_bar is not None:
                    self.db.update_amostra_pyield(amostra_id, p_yield_bar)
            else:
                amostra_id = self.db.add_amostra(nome, desc, d_mm, l_mm, rho, p_escoamento_bar=p_yield_bar)
            
            if not amostra_id:
                tk.messagebox.showerror("Erro", "Falha ao criar/obter amostra.")
                return

            # 2. Calcular Médias Integrais BRUTAS (todo o ensaio)
            p1_avg = np.mean(self.p1_data) if self.p1_data else 0
            p2_avg = np.mean(self.p2_data) if self.p2_data else 0
            v1_avg = np.mean(self.v1_data) if self.v1_data else 0
            v2_avg = np.mean(self.v2_data) if self.v2_data else 0
            duracao = self.times[-1] if self.times else 0
            
            # 3. Calcular dados de REGIME ESTACIONÁRIO (corrigidos - Melhoria 1)
            idx_ss = self.idx_regime_start
            p_pasta_regime = None
            p_linha_regime = None
            massa_regime = None
            duracao_regime = None
            ratio = None
            cv_regime = None
            
            if idx_ss is not None and idx_ss < len(self.p2_data) and len(self.p2_data) > idx_ss + 5:
                # Partição de massa pela Integral de Pressão Efetiva (Bingham Proxy)
                # Como não há fluxo antes de vencer a tensão de escoamento, 
                # a integral desconta o "piso" mínimo estipulado pelo usuário na interface.
                # Isso impede que o tempo de pressurização morto aproprie indevidamente parte da massa.
                p_yield = getattr(self, 'session_pyield', PRESSURE_THRESHOLD_START)
                ef_p2_data = [max(0, p - p_yield) for p in self.p2_data]
                
                integral_total = sum(ef_p2_data)
                integral_regime = sum(ef_p2_data[idx_ss:])
                ratio = integral_regime / integral_total if integral_total > 0 else 1.0
                
                massa_regime = massa * ratio
                duracao_regime = self.times[-1] - self.times[idx_ss] if self.times else 0
                p_pasta_regime = np.mean(self.p2_data[idx_ss:])
                p_linha_regime = np.mean(self.p1_data[idx_ss:])
                
                # CV em regime (indicador de qualidade)
                cv_regime = (np.std(self.p2_data[idx_ss:]) / p_pasta_regime * 100) if p_pasta_regime > 0 else 0
                
                print(f"Regime detectado no ponto {idx_ss}/{len(self.p2_data)}. "
                      f"Ratio={ratio:.2f}, Massa regime={massa_regime:.2f}g, "
                      f"P_regime={p_pasta_regime:.3f} bar, CV={cv_regime:.1f}%")
            else:
                p_yield = 0
                ef_p2_data = self.p2_data
                print(f"Regime NÃO detectado. Usando dados brutos integrais.")
            
            # --- Feedback Visual: Regime Estacionário no gráfico ---
            window_size = min(30, len(self.p2_data))
            if window_size >= 10:
                best_start_idx = 0
                min_std = float('inf')
                start_search = max(0, len(self.p2_data) // 2 - window_size)
                
                for i in range(start_search, len(self.p2_data) - window_size + 1):
                    window = self.p2_data[i: i + window_size]
                    current_std = np.std(window)
                    if current_std < min_std:
                        min_std = current_std
                        best_start_idx = i
                        
                end_idx = best_start_idx + window_size
                p2_mean_window = np.mean(self.p2_data[best_start_idx:end_idx])
                cv_percent = (min_std / p2_mean_window * 100) if p2_mean_window > 0 else 0
                
                # Destaque visual da janela no gráfico
                if self.times and len(self.times) > end_idx:
                    t_start = self.times[best_start_idx]
                    t_end = self.times[end_idx - 1]
                    self.ax.axvspan(t_start, t_end, alpha=0.18, color='#a6e3a1', zorder=0,
                                   label=f'Regime Estável (CV={cv_percent:.1f}%)')
                    
                    # Highlight regime start point if detected
                    if idx_ss is not None and idx_ss < len(self.times):
                        self.ax.axvline(x=self.times[idx_ss], color='#89b4fa',
                                        linestyle='--', alpha=0.5, label='Início Regime')
                    
                    self.ax.legend(fontsize=8)
                    self.canvas.draw_idle()
                
            # Determine point number (count existing + 1)
            existing_tests = self.db.get_ensaios_by_amostra(amostra_id)
            ponto_n = len(existing_tests) + 1
            
            # 4. Save Test (bruto + regime)
            self.db.add_ensaio(
                amostra_id, ponto_n, p1_avg, p2_avg, massa, duracao, v1_avg, v2_avg,
                p_pasta_regime=p_pasta_regime,
                p_linha_regime=p_linha_regime,
                massa_regime=massa_regime,
                duracao_regime=duracao_regime,
                idx_inicio_regime=idx_ss,
                ratio_integral=ratio,
                cv_regime=cv_regime
            )
            
            # 5. Validação cruzada massa vs integral efetiva (Melhoria 5)
            integral_ef_total = sum(ef_p2_data) if ef_p2_data else 0
            status_text = f"✓ Ponto {ponto_n} salvo para '{nome}'"
            
            if integral_ef_total > 0:
                K_current = massa / integral_ef_total
                
                if hasattr(self, '_K_calibration') and self._K_calibration is not None:
                    m_esperada = self._K_calibration * integral_ef_total
                    erro_rel = abs(massa - m_esperada) / m_esperada * 100 if m_esperada > 0 else 0
                    
                    if erro_rel > 30:
                        status_text += (f" ⚠️ Massa ({massa:.1f}g) difere "
                                       f"{erro_rel:.0f}% da estimativa ({m_esperada:.1f}g)")
                
                # Update K with exponential moving average
                if self._K_calibration is None:
                    self._K_calibration = K_current
                else:
                    self._K_calibration = 0.7 * self._K_calibration + 0.3 * K_current
            
            if ratio is not None:
                if ratio < 0.30:
                    status_text += f"\n⚠️ Regime curto ({ratio*100:.0f}% da massa) — aguarde mais tempo na próxima vez"
                else:
                    status_text += f" (✓ regime: {ratio*100:.0f}% da massa)"
            
            self.lbl_status.configure(text=status_text)
            
        except Exception as e:
            tk.messagebox.showerror("Erro", f"Erro ao salvar: {e}")

    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        # Restore callback when frame is shown
        if self.controller.is_connected:
            self.controller.on_pressure_reading = self.update_plot_callback
            
        if self.controller.is_connected and not self.controller.linha_calibrada:
            if not hasattr(self, '_calib_banner'):
                self._calib_banner = ctk.CTkLabel(
                    self, text="⚠  Sensor Linha sem calibração! Vá à aba Calibração antes de coletar.",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color="#1e1e2e", fg_color="#f9e2af",
                    corner_radius=6, height=32)
                self._calib_banner.pack(fill="x", padx=20, pady=(0, 5), before=self.graph_frame)
        else:
            if hasattr(self, '_calib_banner'):
                self._calib_banner.destroy()
                delattr(self, '_calib_banner')
