
import pathlib
import re
import typing

import numpy as np
import pandas as pd
from scipy import constants
from spdm.data.Entry import Entry
from spdm.data.Expression import Piecewise, Variable
from spdm.data.File import File
from spdm.data.Function import Function
from spdm.numlib.smooth import smooth_1d
from spdm.utils.logger import logger

TWOPI = 2.0*constants.pi


def load_core_profiles(d):

    bs_r_norm = d["x"].values

    # Core profile
    r_ped = 0.96  # np.sqrt(0.88)
    i_ped = np.argmin(np.abs(bs_r_norm-r_ped))
    # fmt:off
    bs_psi_norm = d["Fp"].values
    # bs_psi = bs_psi_norm*(psi_boundary-psi_axis)+psi_axis

    b_Te =    smooth_1d(d["TE"].values,     bs_r_norm, i_end=i_ped-10, window_len=21)*1000
    b_Ti =    smooth_1d(d["TI"].values,     bs_r_norm, i_end=i_ped-10, window_len=21)*1000
    b_ne =    smooth_1d(d["NE"].values,     bs_r_norm, i_end=i_ped-10, window_len=21)*1.0e19
    b_nDT =   smooth_1d(d["Nd+t"].values,   bs_r_norm, i_end=i_ped-10, window_len=21)*1.0e19*0.5
    b_nHe =   smooth_1d(d["Nath"].values,   bs_r_norm, i_end=i_ped-10, window_len=21)*1.0e19
    b_nImp =  smooth_1d(d["Nz"].values,     bs_r_norm, i_end=i_ped-10, window_len=21)*1.0e19
    b_zeff = d["Zeff"].values
    # fmt:on

    z_eff_star = b_zeff-(b_nDT*2.0+4*b_nHe)/b_ne
    z_imp = 1-(b_nDT*2.0+2*b_nHe)/b_ne
    b = -2*z_imp/(0.02+0.0012)
    c = (z_imp**2-0.02*z_eff_star)/0.0012/(0.02+0.0012)

    z_Ar = np.asarray((-b+np.sqrt(b**2-4*c))/2)
    z_Be = np.asarray((z_imp-0.0012*z_Ar)/0.02)
    # b_nDT = b_ne * (1.0 - 0.02*4 - 0.0012*18) - b_nHe*2.0

    # Zeff = Function(bs_r_norm, baseline["Zeff"].values)
    # e_parallel = baseline["U"].values / (TWOPI * R0)

    return {
        "time": 0.0,
        "grid": {
            "rho_tor_norm":  bs_r_norm,
            "rho_tor":  d["rho"].values,

            "psi_norm": bs_psi_norm,
            "psi": None,
            "psi_magnetic_axis": None,
            "psi_boundary": None,

        },
        "electrons": {"label": "e", "density":  b_ne,   "temperature": b_Te, },
        "ion": [
            {"label": "D",  "density":      b_nDT,      "temperature": b_Ti},
            {"label": "T",  "density":      b_nDT,      "temperature": b_Ti},
            {"label": "He",
             "density_thermal": b_nHe,
             "density_fast": 0.0,
             "temperature": b_Ti,
             "has_fast_particle": True
             },
            {"label": "Be", "density":  0.02*b_ne,      "temperature": b_Ti, "z_ion_1d": z_Be,  "is_impurity": True},
            {"label": "Ar", "density": 0.0012*b_ne,     "temperature": b_Ti, "z_ion_1d": z_Ar,  "is_impurity": True},
        ],
        # "e_field": {"parallel":  Function(e_parallel,bs_r_norm)},
        # "conductivity_parallel": Function(baseline["Joh"].values*1.0e6 / baseline["U"].values * (TWOPI * grid.r0),bs_r_norm),

        "rho_tor":          d["rho"].values,
        "zeff":             d["Zeff"].values,
        "vloop":            d["U"].values,
        "j_ohmic":          d["Joh"].values*1.0e6,
        "j_non_inductive":  d["Jnoh"].values*1.0e6,
        "j_bootstrap":      d["Jbs"].values*1.0e6,
        "j_total":          d["Jtot"].values*1.0e6,
        "XiNC":             d["XiNC"].values,

        "ffprime":          d["EQFF"].values*1.0e6,
        "pprime":           d["EQPF"].values*1.0e6,
    }


def load_core_transport(profiles, R0: float, B0: float = None):

    bs_r_norm = profiles["x"].values

    _x = Variable(0, name="rho_tor_norm")

    # Core profiles
    r_ped = 0.96  # np.sqrt(0.88)
    i_ped = np.argmin(np.abs(bs_r_norm-r_ped))

    # Core Transport

    Cped = 0.17
    Ccore = 0.4
    # Function( profiles["Xi"].values,bs_r_norm)  Cped = 0.2
    chi = Piecewise([Ccore*(1.0 + 3*(_x**2)),   Cped],        [(_x < r_ped), (_x >= r_ped)])
    chi_e = Piecewise([0.5 * Ccore*(1.0 + 3*(_x**2)),   Cped],  [(_x < r_ped), (_x >= r_ped)])

    D = 0.1*(chi+chi_e)

    v_pinch_ne = -0.6 * D * _x / R0
    v_pinch_Te = 2.5 * chi_e * _x / R0
    v_pinch_ni = D * _x / R0
    v_pinch_Ti = chi * _x / R0

    return {
        "grid_d": {"rho_tor_norm": bs_r_norm},
        "conductivity_parallel":  profiles["Joh"].values*1.0e6 / profiles["U"].values * (TWOPI * R0),
        "electrons": {
            "label": "e",
            "particles":   {"d": D,     "v": v_pinch_ne},
            "energy":      {"d": chi_e, "v": v_pinch_Te},
        },
        "ion": [
            {
                "label": "D",
                "particles": {"d":  D, "v": v_pinch_ni},
                "energy": {"d":  chi, "v": v_pinch_Ti},
            },
            {
                "label": "T",
                "particles": {"d":  D, "v": v_pinch_ni},
                "energy": {"d":  chi, "v": v_pinch_Ti},
            },
            {
                "label": "He",
                "particles": {"d": D, "v": v_pinch_ni},
                "energy": {"d": chi, "v": v_pinch_Ti},
            }
        ]}


def load_core_source(profiles, R0: float, B0: float = None):
    bs_r_norm = profiles["x"].values

    _x = Variable(0, name="rho_tor_norm")

    S = 9e20 * np.exp(15.0*(_x**2-1.0))

    Q_e = (profiles["Poh"].values
           + profiles["Pdte"].values
           + profiles["Paux"].values
           - profiles["Peic"].values
           - profiles["Prad"].values
           # - profiles["Pneu"].values
           )*1e6/constants.electron_volt

    Q_DT = (profiles["Peic"].values
            + profiles["Pdti"].values
            + profiles["Pibm"].values
            )*1e6/constants.electron_volt

    Q_He = (- profiles["Pdti"].values
            - profiles["Pdte"].values
            )*1e6/constants.electron_volt

    # Core Source
    return {
        "grid": {"rho_tor_norm": bs_r_norm},
        "j_parallel": (
            # profiles["Jtot"].values
            profiles["Joh"].values
            # + profiles["Jbs"].values
            + profiles["Jnb"].values
            + profiles["Jrf"].values
        ) * 1e6,  # A/m^2
        "electrons": {"label": "e",  "particles": S, "energy": Q_e},
        "ion": [
            {"label": "D",          "particles": S*0.5,      "energy": Q_DT*0.5},
            {"label": "T",          "particles": S*0.5,      "energy": Q_DT*0.5},
            {"label": "He",         "particles": S*0.01,      "energy": Q_He}
        ]}


def load_scenario_ITER(path):
    path = pathlib.Path(path)
    scenario = {
        "name": "15MA Inductive at burn-ASTRA",
        "description": "15MA Inductive at burn-ASTRA"
    }

    # eq_file = path/"Standard domain R-Z/Medium resolution - 129x257/g900003.00230_ITER_15MA_eqdsk16MR.txt"

    profiles_file = path/'15MA Inductive at burn-ASTRA.xls'

    logger.info(f"Load scenario/profiles from {profiles_file}")

    excel_file = pd.read_excel(profiles_file, sheet_name=1)

    desc = {}
    for s in excel_file.iloc[0, 3:7]:
        res = re.match(r'(\w+)=(\d+\.?\d*)(\D+)', s)
        desc[res.group(1)] = (float(res.group(2)), str(res.group(3)))

    time = [0.0]

    vacuum_toroidal_field = {"r0": desc["R"][0], "b0": [desc["B"][0]]}

    d_core_profiles = pd.read_excel(profiles_file, sheet_name=1, header=10, usecols="B:BN")

    scenario["core_profiles"] = {
        'vacuum_toroidal_field': vacuum_toroidal_field,
        "time": time,
        "profiles_1d": [load_core_profiles(d_core_profiles)]
    }

    scenario["core_transport"] = {
        "time": time,
        'vacuum_toroidal_field': vacuum_toroidal_field,
        "model": [
            {"code": {"name": "dummy"},
             "profiles_1d": [load_core_transport(d_core_profiles, vacuum_toroidal_field["r0"])]}
        ]
    }

    scenario["core_sources"] = {
        "time": time,
        'vacuum_toroidal_field': vacuum_toroidal_field,

        "source": [
            {"code": {"name": "dummy"},
             "profiles_1d": [load_core_source(d_core_profiles, vacuum_toroidal_field["r0"])]
             }]
    }

    eq_file = path/"Increased domain R-Z/Medium resolution - 129x257/g900003.00230_ITER_15MA_eqdsk16VVMR.txt"

    scenario["equilibrium"] = {
        "time": time,
        'vacuum_toroidal_field': vacuum_toroidal_field,
    }

    scenario["equilibrium"].update(File(eq_file, format="GEQdsk").read().dump())

    logger.info(f"Load scenario/equilibrium from {eq_file}")

    return scenario


def load_scenario(path):
    return load_scenario_ITER(path)
