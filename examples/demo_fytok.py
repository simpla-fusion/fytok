
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fytok.Tokamak import Tokamak
import scipy.constants
from spdm.data.Collection import Collection
from spdm.data.File import File
from spdm.numerical.Function import Function
from spdm.util.logger import logger
from spdm.util.plot_profiles import plot_profiles

if __name__ == "__main__":
    # db = Collection(schema="mapping",
    #                 source="mdsplus:///home/salmon/public_data/~t/?tree_name=efit_east",
    #                 mapping={"schema": "EAST", "version": "imas/3",
    #                          "path": "/home/salmon/workspace/fytok/data/mapping"})
    # doc = db.open(shot=55555, time_slice=40)

    # device = File("/home/salmon/workspace/fytok/data/mapping/EAST/imas/3/static/config.xml").entry
    # equilibrium = File("/home/salmon/workspace/fytok/examples/data/g063982.04800",  format="geqdsk").entry

    device = File("/home/salmon/workspace/fytok/data/mapping/ITER/imas/3/static/config.xml").entry
    equilibrium = File(
        "/home/salmon/workspace/fytok/examples/data/NF-076026/geqdsk_550s_partbench_case1",
        # "/home/salmon/workspace/data/15MA inductive - burn/Increased domain R-Z/High resolution - 257x513/g900003.00230_ITER_15MA_eqdsk16VVHR.txt",
        # "/home/salmon/workspace/data/Limiter plasmas-7.5MA li=1.1/Limiter plasmas 7.5MA-EQDSK/Limiter_7.5MA_outbord.EQDSK",
        format="geqdsk").entry

    # profile = pd.read_csv('/home/salmon/workspace/data/15MA inductive - burn/profile.txt', sep='\t')

    tok = Tokamak({
        "radial_grid": {"axis": 64, "primary": "rho_tor_norm"},
        "wall":  device.wall,
        "pf_active": device.pf_active,
        "equilibrium": {
            "vacuum_toroidal_field": equilibrium.vacuum_toroidal_field,
            "global_quantities": equilibrium.global_quantities,
            "profiles_1d": equilibrium.profiles_1d,
            "profiles_2d": equilibrium.profiles_2d,
            "coordinate_system": {"grid": {"dim1": 64, "dim2": 256}}
        },
        "core_profiles": {
            "electrons": {
                "density":     1e19,
                "temperature": lambda x: (1-x**2)**2
            },
            "conductivity_parallel": 1.0,
            "psi":   1.0,
        }
    })

    fig = plt.figure()

    tok.plot(fig.gca(),
             wall={"limiter": {"edgecolor": "green"},  "vessel": {"edgecolor": "blue"}},
             pf_active={"facecolor": 'red'},

             equilibrium={"mesh": False, "boundary": True,
                          "scalar_field": [
                              ("coordinate_system.norm_grad_psi", {"levels": 32, "linewidths": 0.1}),
                              ("psirz", {"levels": 32, "linewidths": 0.1}),
                          ],
                          }
             )

    plt.savefig("/home/salmon/workspace/output/contour.svg", transparent=True)

    plot_profiles(
        [
            [
                (tok.equilibrium.profiles_1d.ffprime,            r"$ff^{\prime}$"),
                (Function(equilibrium.profiles_1d.psi_norm,
                          equilibrium.profiles_1d.f_df_dpsi),   r"$ff^{\prime}_{0}$"),
            ],
            [
                (tok.equilibrium.profiles_1d.fpol,              r"$fpol$"),
                (Function(equilibrium.profiles_1d.psi_norm,
                          np.abs(equilibrium.profiles_1d.f)),   r"$\left|f_{pol0}\right|$"),
            ],
            [
                (tok.equilibrium.profiles_1d.q,                    r"$q$"),
                (tok.equilibrium.profiles_1d.dphi_dpsi,                    r"$\frac{d\phi}{d\psi}$"),
                (Function(equilibrium.profiles_1d.psi_norm, equilibrium.profiles_1d.q), r"$q_0$"),
                # (Function(profile["Fp"].values, profile["q"].values),             r"$q_{1}$"),

            ],
            [
                (tok.equilibrium.profiles_1d.rho_tor,           r"$\rho_{tor}$"),
                # (Function(profile["Fp"].values, profile["rho"].values),             r"$\rho_{tor,0}$"),
                (tok.equilibrium.profiles_1d.dvolume_drho_tor / ((scipy.constants.pi**2) * 4.0 * tok.equilibrium.vacuum_toroidal_field.r0),
                    r"$\frac{dV/d\rho_{tor}}{4\pi^2 R_0}$"),
            ],

            # (tok.equilibrium.profiles_1d.phi,                   r"$\Phi$"),
            # (tok.equilibrium.profiles_1d.dpsi_drho_tor,         r"$\frac{d\psi}{d\rho_{tor}}$"),
            # [
            #     (Function(equilibrium.profiles_1d.psi_norm, equilibrium.profiles_1d.q), r"$q_0$"),
            #     (tok.equilibrium.profiles_1d.q,                 r"$q$"),
            #     (tok.equilibrium.profiles_1d.dphi_dpsi,         r"$\frac{d\phi}{d\psi}$"),
            # ],
            (tok.equilibrium.profiles_1d.rho_tor,                r"$\rho_{tor}$"),

            [
                (tok.equilibrium.profiles_1d.volume,                r"$V$"),
                (Function(tok.equilibrium.profiles_1d.rho_tor, tok.equilibrium.profiles_1d.dvolume_drho_tor.view(np.ndarray)).antiderivative,
                 r"$\int \frac{dV}{d\rho_{tor}}  d\rho_{tor}$"),
                (tok.equilibrium.profiles_1d.dvolume_dpsi.antiderivative * \
                 (tok.equilibrium.global_quantities.psi_boundary - tok.equilibrium.global_quantities.psi_axis),\
                 r"$\int \frac{dV}{d\psi}  d\psi$"),
            ],
            # (tok.equilibrium.profiles_1d.dvolume_drho_tor,      r"$\frac{dV}{d\rho}$"),
            # (tok.equilibrium.profiles_1d.dpsi_drho_tor,         r"$\frac{d\psi}{d\rho_{tor}}$"),
            # (tok.equilibrium.profiles_1d.drho_tor_dpsi,         r"$\frac{d\rho_{tor}}{d\psi}$"),
            # (tok.equilibrium.profiles_1d.gm1,                   r"$\left<\frac{1}{R^2}\right>$"),
            # (tok.equilibrium.profiles_1d.gm2,       r"$\left<\frac{\left|\nabla \rho\right|^2}{R^2}\right>$"),
            # (tok.equilibrium.profiles_1d.gm3,                   r"$\left<\left|\nabla \rho\right|^2\right>$"),
            # (tok.equilibrium.profiles_1d.gm7,                   r"$\left<\left|\nabla \rho\right|\right>$"),
            # (tok.equilibrium.profiles_1d.dphi_dpsi, r"$\frac{d\phi}{d\psi}$"),
            # (tok.equilibrium.profiles_1d.drho_tor_dpsi, r"$\frac{d\rho_{tor}}{d\psi}$"),
            # (tok.core_profiles.electrons.temperature, r"$T_{e}$"),
            [
                (tok.equilibrium.coordinate_system.surface_integrate2(lambda r, z:1.0/r**2), \
                 r"$\left<\frac{1}{R^2}\right>$"),
                (tok.equilibrium.coordinate_system.surface_integrate(1/tok.equilibrium.coordinate_system.r**2), \
                 r"$\left<\frac{1}{R^2}\right>$"),
            ]

        ],
        # x_axis=(tok.equilibrium.profiles_1d.rho_tor_norm,   {"label": r"$\rho_{N}$"}),  # asd
        # x_axis=(tok.equilibrium.profiles_1d.phi,   {"label": r"$\Phi$"}),  # asd
        x_axis=(tok.equilibrium.profiles_1d.psi_norm,  {"label": r"$\psi_{N}$"}),  # asd
        grid=True) .savefig("/home/salmon/workspace/output/profiles_1d.svg", transparent=True)

    psi_norm = tok.radial_grid.psi_norm
    rho_tor_norm = tok.radial_grid.rho_tor_norm

    r_ped = np.sqrt(0.88)

    n_src = Function(rho_tor_norm, lambda x: 7.5e20 * np.exp(15.0*(x**2-1.0)))

    diff = Function(rho_tor_norm,
                    [lambda r:r < r_ped, lambda r:r >= r_ped],
                    [lambda x:0.5 + (x**2), lambda x: 0.11])

    v_pinch = diff * rho_tor_norm * 1.385 / equilibrium.vacuum_toroidal_field.r0

    gamma = tok.equilibrium.profiles_1d.dvolume_drho_tor  \
        * tok.equilibrium.profiles_1d.gm2    \
        / tok.equilibrium.profiles_1d.fpol \
        * tok.equilibrium.profiles_1d.dpsi_drho_tor \
        / ((scipy.constants.pi*2.0)**2)

    j_parallel = -gamma.derivative  \
        / tok.equilibrium.profiles_1d.rho_tor[-1]**2 \
        * tok.equilibrium.profiles_1d.dpsi_drho_tor  \
        * (tok.equilibrium.profiles_1d.fpol**2) \
        / (scipy.constants.mu_0*tok.vacuum_toroidal_field.b0) \
        * (scipy.constants.pi)

    # j_parallel = Function(gamma.x,  j_parallel )

    tok.update(
        core_transport={
            "conductivity_parallel": 1.0,
            "electrons": {"particles": {
                "d": diff,
                "v": - v_pinch}}
        },

        core_sources={
            "electrons": {
                "particles": n_src
            },
            "j_parallel": j_parallel.pullback(psi_norm, rho_tor_norm).view(np.ndarray),
            "conductivity_parallel": 1.0e-8
        },

        boundary_conditions={
            "current": {
                "identifier": {"index": 1},
                "value": tok.equilibrium.global_quantities.psi_boundary
            },
            "electrons": {
                "particles": {
                    "identifier": {"index": 1},
                    "value": 4.6e19
                },
                "energy": {
                    "identifier": {"index": 1},
                    "value": 2.183  # 　keV
                }
            },
            "ion": [
                {
                    "label": "H",
                    "a": 1.0,
                    "z_ion": 1,
                    "particles": {
                        "identifier": {"index": 1},
                        "value": (1, 0, 4.6e19)
                    },
                    "energy": {
                        "identifier": {"index": 1},
                        "value": (1, 0, 4.6e19)
                    }
                }
            ]
        }
    )

    psi_norm = tok.equilibrium.profiles_1d.psi_norm
    rho_tor_norm = tok.equilibrium.profiles_1d.rho_tor_norm
    # rho_tor_bdry = tok.core_profiles.grid.rho_tor[-1]

    plot_profiles(
        [
            # (tok.core_profiles.electrons.source,              {"color": "green", "label": r"$S_{edge}$"}),
            [
                (tok.core_profiles.psi,              r"$\psi^{+}$"),
                (tok.equilibrium.profiles_1d.psi.pullback(psi_norm, rho_tor_norm),              r"$\psi^{-}$"),
            ],
            [
                (tok.core_profiles.electrons.diff,          {"color": "green", "label": r"D"}),
                # (Function(profile["x"].values, profile["Dn"].values),                         r"$D$"),
                (np.abs(tok.core_profiles.electrons.conv),  {"color": "black",  "label": r"$\left|v\right|$"}),
            ],
            # (tok.core_profiles.vprime,          r"vprime"),
            # (tok.core_profiles.gm3,             r"gm3"),
            # # (tok.core_profiles.electrons.a,      r"a"),
            # # (tok.core_profiles.electrons.b,      r"b"),
            # [
            #     (tok.core_profiles.electrons.d,      r"d"),
            #     (tok.core_profiles.electrons.e,      r"e"),
            # ],
            # (tok.core_profiles.electrons.f,      r"f"),
            # (tok.core_profiles.electrons.g,      r"g"),
            [
                (tok.core_profiles.electrons.density,                           r"$n_{e}$"),
                # (Function(profile["x"].values, profile["NE"].values*1e19),                         r"$n_{e,0}$"),
            ],

            [
                (tok.core_profiles.electrons.density.derivative, {"color": "green", "label":  r"$n_{e}^{\prime}$"}),
                (tok.core_profiles.electrons.density_prime,      {"color": "black", "label":  r"$n_{e}^{\prime}$"}),
            ],

            [
                (tok.core_profiles.electrons.s_exp_flux,    {"color": "green", "label": r"Source"}),
                (tok.core_profiles.electrons.diff_flux,     {"color": "black", "label": r"Diffusive flux"}),
                (tok.core_profiles.electrons.conv_flux,     {"color": "red",  "label": r"Convective flux"}),
                (tok.core_profiles.electrons.residual,      {"color": "blue",   "label": r"Residual"}),
            ],

        ],
        x_axis=(tok.core_profiles.electrons.density.x,   {"label": r"$\rho_{N}$"}),  # x axis,
        # index_slice=slice(-100,None, 1),
        grid=True) .savefig("/home/salmon/workspace/output/electron_1d.svg", transparent=True)

    logger.info("Done")
