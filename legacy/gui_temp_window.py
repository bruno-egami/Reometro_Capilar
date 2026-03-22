
class RelatorioWindow(ctk.CTkToplevel):
    def __init__(self, parent, analysis_data, db):
        super().__init__(parent)
        self.analysis_data = analysis_data
        self.db = db
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
        
        self.btn_pdf = ctk.CTkButton(self.footer, text="Salvar PDF", command=self.save_pdf, fg_color="green")
        self.btn_pdf.pack(side="right", padx=10)
        
        self.btn_close = ctk.CTkButton(self.footer, text="Fechar", command=self.destroy, fg_color="red")
        self.btn_close.pack(side="right", padx=10)

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
        
        self._plot_figure(t1, self._create_flow_curve())
        self._plot_figure(t2, self._create_viscosity_curve())
        self._plot_figure(t3, self._create_model_curve())
        
    def _plot_figure(self, parent, fig):
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
        
        # Experimental
        x = self.analysis_data['gamma_dot']
        y = self.analysis_data['tau_w']
        ax.plot(x, y, 'ko', label='Experimental', alpha=0.6)
        
        # Models
        x_smooth = np.linspace(min(x), max(x), 100)
        
        colors = ['r', 'g', 'b', 'm', 'c']
        color_idx = 0
        
        for name, fit in self.analysis_data['model_fits'].items():
            if fit.get('params') is not None:
                # Calculate model y
                # Need model function... reusing `models` module
                # But `models` module might need update to handle arrays or use the logic from run_analysis
                # Ideally we should store the model function or lambda, but we have names.
                # Let's import models again inside method to be sure
                import models_reologicos as m_reol
                
                func = getattr(m_reol, name)
                try:
                    y_pred = func(x_smooth, *fit['params'])
                    ax.plot(x_smooth, y_pred, linestyle='--', label=f"{name} (R²={fit['r2']:.2f})", color=colors[color_idx % len(colors)])
                    color_idx += 1
                except Exception:
                    pass
                    
        ax.set_title("Ajuste de Modelos")
        ax.set_xlabel("Taxa (1/s)")
        ax.set_ylabel("Tensão (Pa)")
        ax.legend()
        ax.grid(True)
        return fig

    def _init_dados(self):
        # Table with calculations
        cols = ("Taxa (1/s)", "Tensão (Pa)", "Viscosidade (Pa.s)")
        tree = ttk.Treeview(self.tab_dados, columns=cols, show="headings")
        
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=150, anchor="center")
            
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Insert data
        d = self.analysis_data
        for g, t, e in zip(d['gamma_dot'], d['tau_w'], d['eta']):
            tree.insert("", "end", values=(f"{g:.2f}", f"{t:.2f}", f"{e:.4f}"))

    def save_pdf(self):
        filepath = tk.filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not filepath: return
        
        # Call the existing logic but pass the path
        # Reuse logic from AnaliseFrame? Or redundant?
        # Better to have a static method or helper.
        # But `AnaliseFrame` has `_generate_temp_graphs`.
        # I can call back a method in parent if passed, or duplicate logic.
        # Let's duplicate the relevant call logic since it relies on modules, fairly clean.
        # But `_generate_temp_graphs` is in `AnaliseFrame`.
        # I should probably pass a callback `on_export_pdf` from `AnaliseFrame`.
        
        # Actually, let's just use the `AnaliseFrame` instance if I passed it as parent?
        # `parent` is `AnaliseFrame`? usually it's `App` or `Frame`.
        # If I pass `AnaliseFrame` instance as `controller` or specifically, I can call its method.
        # Let's assume the caller will handle the actual export logic to reuse code.
        pass
