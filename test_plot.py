import numpy as np
import pandas as pd
import reologia_plot as rp
import modelos_reologicos as models

gd_app_arr = np.array([10, 50, 100, 500, 1000])
tau_arr = np.array([1000, 3000, 5000, 15000, 25000])
tau_err = tau_arr * 0.05

log_gd = np.log(gd_app_arr)
log_tau = np.log(tau_arr)
local_n_primes = np.gradient(log_tau, log_gd)
local_n_primes = np.clip(local_n_primes, 0.05, 3.0)
n_prime_global = np.mean(local_n_primes)

gd_true_arr = gd_app_arr * ((3 * n_prime_global + 1) / (4 * n_prime_global))
eta_arr = tau_arr / gd_true_arr

gd_mean = gd_true_arr.copy()
tau_mean = tau_arr.copy()
eta_mean = eta_arr.copy()

gd_fit = np.logspace(np.log10(max(1e-3, gd_mean.min())), np.log10(gd_mean.max()), 100)

from scipy.optimize import curve_fit
p0 = models.MODELS['Lei da Potência'][2](gd_mean, tau_mean)
popt, _ = curve_fit(models.MODELS['Lei da Potência'][0], gd_mean, tau_mean, p0=p0, bounds=models.MODELS['Lei da Potência'][3])
tau_fit = models.MODELS['Lei da Potência'][0](gd_fit, *popt)

fig1, _ = rp.plotar_curva_fluxo(gd_true_arr, tau_arr, gd_mean, tau_mean, tau_err, gd_fit, tau_fit, 'Lei da Potência', 0.99, 'K=10\nn=0.5')
fig1.savefig('test_plot_curva_fluxo.png')

fig2, _ = rp.plotar_viscosidade(gd_true_arr, eta_arr, gd_mean, eta_mean, tau_err/gd_mean)
fig2.savefig('test_plot_viscosidade.png')

mods = [{'nome': 'Lei da Potência', 'tau_fit': tau_fit, 'r2': 0.99, 'params': '...'}]
fig3, _ = rp.plotar_ajuste_modelos(gd_true_arr, tau_arr, gd_mean, tau_mean, tau_err, gd_fit, mods)
fig3.savefig('test_plot_ajuste_modelos.png')

print("Graphs generated successfully.")
