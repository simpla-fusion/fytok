
import numpy as np
import pandas as pd
import scipy.constants

from fytok.modules.transport.CoreTransport import CoreTransport
from fytok.Tokamak import Tokamak
from spdm.data.Collection import Collection
from spdm.data.File import File
from spdm.data.Function import Function
from spdm.data.Node import _next_
from spdm.util.logger import logger
from spdm.util.plot_profiles import plot_profiles, sp_figure

import transport.nclass as nclass

if __name__ == "__main__":

    device = File("/home/salmon/workspace/fytok/data/mapping/ITER/imas/3/static/config.xml").entry

    equilibrium = File(
        # "/home/salmon/workspace/fytok/examples/data/NF-076026/geqdsk_550s_partbench_case1",
        "/home/salmon/workspace/data/15MA inductive - burn/Increased domain R-Z/High resolution - 257x513/g900003.00230_ITER_15MA_eqdsk16VVHR.txt",
        # "/home/salmon/workspace/data/Limiter plasmas-7.5MA li=1.1/Limiter plasmas 7.5MA-EQDSK/Limiter_7.5MA_outbord.EQDSK",
        format="geqdsk").entry

    profile = pd.read_csv('/home/salmon/workspace/data/15MA inductive - burn/profile.txt', sep='\t')

    equilibrium.time_slice[-1].coordinate_system = {"grid": {"dim1": 128, "dim2": 256}}

    ne = Function(profile["x"].values, profile["NE"].values*1.0e19)
    Te = Function(profile["x"].values, profile["TE"].values)
    Ti = Function(profile["x"].values, profile["TI"].values)

    tok = Tokamak({
        "radial_grid": {"axis": 64},
        "wall":  device.wall,
        "pf_active": device.pf_active,
        "tf": device.tf,
        "magnetics": device.magnetics,
        "equilibrium": equilibrium,
        "core_profiles": {
            "profiles_1d": [{
                "electrons": {
                    "label": "electrons",
                    "density":     ne,          # 1.0e19,
                    "temperature": Te,          # lambda x: (1-x**2)**2,
                },
                "ion": [
                    {

                        "label": "H^+",
                        "z_ion": 1,
                        "neutral_index": 1,
                        "element": [{"a": 1, "z_n": 1, "atoms_n": 1}],
                        "density":   0.5*ne,    # 0.5e19,
                        "temperature": Ti,      # lambda x: (1-x**2)**2
                    },
                    {
                        "label": "D^+",
                        "z_ion": 1,
                        "element": [{"a": 2, "z_n": 1, "atoms_n": 1}],
                        "neutral_index": 2,
                        "density":    0.5*ne,   # 0.5e19,
                        "temperature": Ti,      # lambda x: (1-x**2)**2
                    }
                ],
                "conductivity_parallel": 1.0,
                "psi":   1.0,
            }]
        }
    })

    if False:
        sp_figure(tok,
                  wall={"limiter": {"edgecolor": "green"},  "vessel": {"edgecolor": "blue"}},
                  pf_active={"facecolor": 'red'},
                  equilibrium={
                      "mesh": True,
                      "boundary": True,
                      "scalar_field": [
                          #   ("coordinate_system.norm_grad_psi", {"levels": 32, "linewidths": 0.1}),
                          ("psirz", {"levels": 32, "linewidths": 0.1}),
                      ],
                  }
                  ) .savefig("/home/salmon/workspace/output/tokamak.svg", transparent=True)

    eq = tok.equilibrium.time_slice[-1]

    plot_profiles(
        [
            (eq.profiles_1d.dpressure_dpsi,                                                   r"$dP/d\psi$"),
            [
                (eq.profiles_1d.ffprime,                                                   r"$ff^{\prime}$"),
                (Function(eq.profiles_1d.psi_norm,  eq.profiles_1d.f_df_dpsi),         r"$ff^{\prime}_{0}$"),
            ],
            [
                (eq.profiles_1d.fpol,                                                             r"$fpol$"),
                (Function(eq.profiles_1d.psi_norm, np.abs(eq.profiles_1d.f)),    r"$\left|f_{pol0}\right|$"),
            ],
            [
                (Function(profile["Fp"].values, profile["q"].values),                        r"$q^{\star}$"),
                (eq.profiles_1d.q,                                                                   r"$q$"),
                (eq.profiles_1d.dphi_dpsi,                                         r"$\frac{d\phi}{d\psi}$"),
            ],
            [
                (Function(profile["Fp"].values, profile["rho"].values),             r"$\rho_{tor}^{\star}$"),
                (eq.profiles_1d.rho_tor,                                                    r"$\rho_{tor}$"),
            ],
            [
                (Function(profile["Fp"].values, profile["x"].values),             r"$\rho_{tor,0}^{\star}$"),
                (eq.profiles_1d.rho_tor_norm,                                             r"$\rho_{tor,0}$"),
            ],
            [
                (Function(profile["Fp"].values, profile["Jtot"].values*1e6),     r"$j_{\parallel}^{\star}$"),
                (eq.profiles_1d.j_parallel,                                              r"$j_{\parallel}$"),
            ],
            # [
            #     (eq.profiles_1d.geometric_axis.r,                                 r"$geometric_{axis.r}$"),
            #     (eq.profiles_1d.r_inboard,                                               r"$r_{inboard}$"),
            #     (eq.profiles_1d.r_outboard,                                             r"$r_{outboard}$"),
            # ],

            # [
            #     (eq.profiles_1d.volume,                r"$V$"),
            #     # (Function(eq.profiles_1d.rho_tor, eq.profiles_1d.dvolume_drho_tor).antiderivative,
            #     #  r"$\int \frac{dV}{d\rho_{tor}}  d\rho_{tor}$"),
            #     (eq.profiles_1d.dvolume_dpsi.antiderivative * \
            #      (eq.global_quantities.psi_boundary - eq.global_quantities.psi_axis),\
            #      r"$\int \frac{dV}{d\psi}  d\psi$"),
            # ],

            (eq.profiles_1d.gm1,                                         r"$gm1=\left<\frac{1}{R^2}\right>$"),
            (eq.profiles_1d.gm2,                r"$gm2=\left<\frac{\left|\nabla \rho\right|^2}{R^2}\right>$"),
            (eq.profiles_1d.gm3,                            r"$gm3=\left<\left|\nabla \rho\right|^2\right>$"),
            (eq.profiles_1d.gm7,                              r"$gm7=\left<\left|\nabla \rho\right|\right>$"),
            (eq.profiles_1d.dphi_dpsi,                                              r"$\frac{d\phi}{d\psi}$"),
            (eq.profiles_1d.drho_tor_dpsi,                                    r"$\frac{d\rho_{tor}}{d\psi}$"),
            (eq.profiles_1d.dvolume_drho_tor,                                          r"$\frac{dV}{d\rho}$"),
            (eq.profiles_1d.dpsi_drho_tor,                                    r"$\frac{d\psi}{d\rho_{tor}}$"),
            # [
            #     (eq.coordinate_system.surface_integrate2(lambda r, z:1.0/r**2), \
            #      r"$\left<\frac{1}{R^2}\right>$"),
            #     (eq.coordinate_system.surface_integrate(1/eq.coordinate_system.r**2), \
            #      r"$\left<\frac{1}{R^2}\right>$"),
            # ]

        ],
        x_axis=(eq.profiles_1d.psi_norm,                                                        r"$\psi_{N}$"),
        grid=True, fontsize=16
    ) .savefig("/home/salmon/workspace/output/equilibrium.svg", transparent=True)

    if False:
        core_profile = tok.core_profiles.profiles_1d[-1]
        plot_profiles(
            [
                [
                    (Function(profile["x"].values, profile["NE"].values*1.0e19),            r"$n_{e}^{\star}$"),
                    (core_profile.electrons.density,                                        r"$n_e$"),
                    *[(ion.density,                         f"$n_{{{ion.label}}}$") for ion in core_profile.ion],

                ],
                [
                    (Function(profile["x"].values, profile["TE"].values),                   r"$T_{e}^{\star}$"),
                    (core_profile.electrons.temperature,                                    r"$T_e$"),
                    *[(ion.temperature,                      f"$T_{{{ion.label}}}$") for ion in core_profile.ion],
                ],

            ],
            x_axis=(core_profile.grid.rho_tor_norm,    r"$\sqrt{\Phi/\Phi_{bdry}}$"),  # x axis,
            grid=True, fontsize=10
        ) .savefig("/home/salmon/workspace/output/core_profile.svg", transparent=True)

        core_transport = CoreTransport({
            "identifier": {
                "name": "neoclassical",
                "index": 5,
                "description": "by NCLASS"
            }
        },  grid=eq.radial_grid("rho_tor_norm"),   time=eq.time)

        core_transport.profiles_1d[_next_] = {"time": 0.0}

        core_transport1d = core_transport.profiles_1d[-1]

        nclass.transport_nclass(eq, core_profile, core_transport1d)

        plot_profiles(
            [
                [
                    (core_transport1d.electrons.particles.flux,                            r"$\Gamma_e$"),
                    *[(ion.particles.flux,        f"$\Gamma_{{{ion.label}}}$") for ion in core_transport1d.ion],
                ],
                [
                    (core_transport1d.electrons.particles.d,                                    r"$D_e$"),
                    *[(ion.particles.d,           f"$D_{{{ion.label}}}$") for ion in core_transport1d.ion],
                ],
                [
                    (core_transport1d.electrons.particles.v,                                    r"$v_e$"),
                    *[(ion.particles.v,           f"$v_{{{ion.label}}}$") for ion in core_transport1d.ion],
                ],
                [
                    (core_transport1d.electrons.energy.flux,                                    r"$q_e$"),
                    *[(ion.energy.flux,        f"$q_{{{ion.label}}}$") for ion in core_transport1d.ion],
                ],
                [
                    (Function(profile["x"].values, profile["Xi"].values),            r"$\chi_{i}^{\star}$"),
                    (Function(profile["x"].values, profile["XiNC"].values),       r"$\chi_{i,nc}^{\star}$"),
                    (core_transport1d.electrons.energy.d,                                      r"$\chi_e$"),
                    *[(ion.energy.d,           f"$\chi_{{{ion.label}}}$") for ion in core_transport1d.ion],
                ],
                [
                    (core_transport1d.electrons.energy.v,      r"$v_{Te}$"),
                    *[(ion.energy.v,           f"$v_{{T,{ion.label}}}$") for ion in core_transport1d.ion],
                ],
                [
                    (Function(profile["x"].values, profile["Jbs"].values),      r"$j_{bootstrap}^{\star}$"),
                    (core_transport1d.j_bootstrap,                                      r"$j_{bootstrap}$"),
                ]
            ],
            x_axis=(core_transport1d.grid_v.rho_tor_norm,                     r"$\sqrt{\Phi/\Phi_{bdry}}$"),
            annotation=core_transport.identifier.name,
            grid=True, fontsize=10) .savefig("/home/salmon/workspace/output/core_transport.svg", transparent=True)

    logger.debug("====== DONE ========")
