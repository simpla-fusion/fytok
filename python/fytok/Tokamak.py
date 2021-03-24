import collections
import copy
import math
from functools import cached_property

import matplotlib.pyplot as plt
import numpy as np
import scipy.integrate
from spdm.data.Field import Field
from spdm.data.Function import Function
from spdm.data.Node import Node, _next_
from spdm.data.PhysicalGraph import PhysicalGraph
from spdm.util.logger import logger

from .modules.device.PFActive import PFActive
from .modules.device.TF import TF
from .modules.device.Wall import Wall
from .modules.transport.CoreProfiles import CoreProfiles
from .modules.transport.CoreSources import CoreSources
from .modules.transport.CoreTransport import CoreTransport
from .modules.transport.EdgeProfiles import EdgeProfiles
from .modules.transport.EdgeSources import EdgeSources
from .modules.transport.EdgeTransport import EdgeTransport
from .modules.transport.Equilibrium import Equilibrium
from .modules.transport.TransportSolver import TransportSolver
from .util.RadialGrid import RadialGrid


class Tokamak(PhysicalGraph):
    """Tokamak
        功能：
            - 描述装置在单一时刻的状态，
            - 在时间推进时，确定各个子系统之间的依赖和演化关系，

    """

    def __init__(self,  data=None,  *args, **kwargs):
        super().__init__(data, *args,  **kwargs)

        self._time = PhysicalGraph(self["equilibrium.time"].__fetch__())
        self._vacuum_toroidal_field = PhysicalGraph(self["equilibrium.vacuum_toroidal_field"].__fetch__())

    # --------------------------------------------------------------------------

    @property
    def time(self):
        return self._time

    @property
    def vacuum_toroidal_field(self):
        return self._vacuum_toroidal_field

    @cached_property
    def wall(self):
        return Wall(self["wall.description_2d"], parent=self)

    @cached_property
    def tf(self):
        return TF(self["tf"], parent=self)

    @cached_property
    def pf_active(self):
        return PFActive(self["pf_active"], parent=self)

    # --------------------------------------------------------------------------

    @cached_property
    def equilibrium(self):
        return Equilibrium(self["equilibrium.time_slice"],
                           vacuum_toroidal_field=self["equilibrium.vacuum_toroidal_field"].__fetch__(), parent=self)

    @cached_property
    def core_profiles(self):
        return CoreProfiles(self["core_profiles"],   parent=self)

    @cached_property
    def edge_profiles(self):
        return EdgeProfiles(self["edge_profiles"],   parent=self)

    @cached_property
    def core_transport(self):
        """Core plasma transport of particles, energy, momentum and poloidal flux."""
        return CoreTransport(self["core_transport"] or [],   parent=self)

    @cached_property
    def core_sources(self):
        """Core plasma thermal source terms (for the transport equations of the thermal species).
            Energy terms correspond to the full kinetic energy equation
            (i.e. the energy flux takes into account the energy transported by the particle flux)
        """
        return CoreSources(self["core_sources"] or [],   parent=self)

    @cached_property
    def edge_transports(self):
        """Edge plasma transport. Energy terms correspond to the full kinetic energy equation
         (i.e. the energy flux takes into account the energy transported by the particle flux)
        """
        return EdgeTransport(self["edge_transport.mode"], parent=self)

    @cached_property
    def edge_sources(self):
        """Edge plasma sources. Energy terms correspond to the full kinetic energy equation
         (i.e. the energy flux takes into account the energy transported by the particle flux)
        """
        return CoreSources(self["edge_sources.mode"], parent=self)

    @cached_property
    def transport(self):
        return TransportSolver(self["transport_solver"], parent=self)

    @cached_property
    def constraints(self):
        return PhysicalGraph(self["constraints"], parent=self)

    # --------------------------------------------------------------------------
    def update(self, *args, time=None,   max_iters=1,  tolerance=0.1,   ** kwargs):

        convergence = False

        if time is None:
            time = self._time

        core_profiles_prev = self.core_profiles

        for iter_count in range(max_iters):
            logger.debug(f"Iterator = {iter_count}")

            for src in self.core_sources:
                src.update(time=time, equilibrium=self.equilibrium)

            for trans in self.core_transport:
                trans.update(time=time, equilibrium=self.equilibrium)

            core_profiles_next = self.transport.update(core_profiles_prev,
                                                       equilibrium=self.equilibrium,
                                                       core_transport=self.core_transport,
                                                       core_sources=self.core_sources,
                                                       boundary_condition=self.boundary_condition
                                                       )

            # .. todo:: integrate core and edge
            # edge_profiles_old = copy(edge_profiles_iter)

            # edge_profiles_iter = self._transport_edge_solver(
            #     edge_profiles_old, dt,
            #     core_profiles_next,
            #     equilibrium=self._equilibrium,
            #     transports=self.edge_transports,
            #     sources=self.edge_sources,
            #     **kwargs)

            if self.check_converge(core_profiles_prev, core_profiles_next, tolerance):
                convergence = True
                break

            core_profiles_prev = core_profiles_next

            self.equilibrium.update(time=time, profiles=core_profiles_next, constraints=self.constraints)

        if not convergence:
            raise RuntimeError(f"Does not converge! iter_count={iter_count}")
        else:
            self._core_profiles = core_profiles_next

    def check_converge(self, core_profiles_prev, core_profiles_next, tolerance):
        return True
    # --------------------------------------------------------------------------

    def save(self, uri, *args, **kwargs):
        raise NotImplementedError()

    def plot(self, axis=None, *args,   **kwargs):

        if axis is None:
            axis = plt.gca()

        self.wall.plot(axis, **kwargs.get("wall", {}))

        self.pf_active.plot(axis, **kwargs.get("pf_active", {}))

        self.equilibrium.plot(axis, **kwargs.get("equilibrium", {}))

        axis.set_aspect('equal')
        axis.axis('scaled')
        axis.set_xlabel(r"Major radius $R$ [m]")
        axis.set_ylabel(r"Height $Z$ [m]")
        # axis.legend()
        return axis

    def initialize_profile(self, spec="electrons", n0=1.0e19, w_scale=5,  x_ped=0.9, d_ped=0.2):
        r""" Setup dummy profile　
                core_transport
                core_sources
                core_profiles
        """

        gamma = self.equilibrium.magnetic_flux_coordinates.dvolume_drho_tor  \
            * self.equilibrium.magnetic_flux_coordinates.gm2    \
            / self.equilibrium.magnetic_flux_coordinates.fpol \
            * self.equilibrium.magnetic_flux_coordinates.dpsi_drho_tor \
            / (4.0*(scipy.constants.pi**2))

        rho_tor_norm = np.linspace(0, 1.0, len(gamma))

        gamma = Function(rho_tor_norm, gamma)

        j_total = -gamma.derivative  \
            / self.equilibrium.magnetic_flux_coordinates.rho_tor[-1]**2 \
            * self.equilibrium.magnetic_flux_coordinates.dpsi_drho_tor  \
            * (self.equilibrium.magnetic_flux_coordinates.fpol**2) \
            / (scipy.constants.mu_0*self.vacuum_toroidal_field.b0) \
            * (scipy.constants.pi)

        j_total[1:] /= self.equilibrium.magnetic_flux_coordinates.dvolume_drho_tor[1:]

        j_total[0] = 2*j_total[1]-j_total[2]

        self.core_transport[_next_] = {"identifier": {"name": f"Dummy transport", "index": 0}}

        self.core_sources[_next_] = {"identifier": {"name": f"Dummy source", "index": 0},
                                     "profiles_1d": {"j_parallel": j_total,
                                                     "conductivity_parallel": 1.0e-8
                                                     }
                                     }

        # self.core_sources[-1]["profiles_1d.j_parallel"] = j_total

        # self.core_sources[-1]["profiles_1d.conductivity_parallel"] = 1.0e-8

        if isinstance(spec, str):
            spec = {spec: {}}
        elif not isinstance(spec, collections.abc.Mapping):
            raise TypeError(type(spec))

        # rho_tor_norm = self.grid.rho_tor_norm

        rho_tor_boundary = self.equilibrium.magnetic_flux_coordinates.rho_tor[-1]

        psi_norm = self.equilibrium.magnetic_flux_coordinates.rho_tor_norm.invert(rho_tor_norm)

        vpr = self.equilibrium.magnetic_flux_coordinates.dvolume_drho_tor(psi_norm)

        gm3 = self.equilibrium.magnetic_flux_coordinates.gm3(psi_norm)

        H = vpr * gm3

        for sp, desc in spec.items():
            n_s = desc.get("density", n0)

            w_scale_s = desc.get("w_scale", w_scale)

            def n_core(x): return (1-(x/w_scale_s)**2)**2

            def dn_core(x): return -4*x*(1-(x/w_scale_s)**2)/(w_scale_s**2)

            def n_ped(x): return n_core(x_ped) - (1.0-x_ped) * dn_core(x_ped) * (1.0 - np.exp((x-x_ped)/(1.0-x_ped)))

            def dn_ped(x): return dn_core(x_ped) * np.exp((x-x_ped)/(1.0-x_ped))

            integral_src = Function(rho_tor_norm, -d_ped * H * dn_ped(rho_tor_norm)/(rho_tor_boundary**2))

            self.core_transport[-1].profiles_1d[sp].particles.d = lambda x: 2.0 * d_ped + (x**2)

            self.core_transport[-1].profiles_1d[sp].particles.v = \
                (self.core_transport[-1].profiles_1d[sp].particles.d(rho_tor_norm) * dn_core(rho_tor_norm) - d_ped*dn_ped(rho_tor_norm)) \
                / (rho_tor_boundary) / n_core(rho_tor_norm) * (rho_tor_norm < x_ped)

            self.core_sources[-1].profiles_1d[sp].particles = n_s * integral_src.derivative/vpr

            desc["density"] = n_s * (n_core(rho_tor_norm)*(rho_tor_norm < x_ped) +
                                     n_ped(rho_tor_norm) * (rho_tor_norm >= x_ped))

            self.core_profiles.profiles_1d[sp] |= desc

        if "electrons" not in spec:
            raise NotImplementedError()
