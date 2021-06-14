
import collections
import datetime
import getpass
from typing import ChainMap, Union

import matplotlib.pyplot as plt
from spdm.data.Function import Function
from spdm.data.Node import Dict, Node, sp_property
from spdm.flow.Actor import Actor
from spdm.numlib import constants, np
from spdm.util.logger import logger

##################################
from .common.Misc import VacuumToroidalField
from .device.Magnetics import Magnetics
from .device.PFActive import PFActive
from .device.TF import TF
from .device.Wall import Wall
# ---------------------------------
from .transport.CoreProfiles import CoreProfiles
from .transport.CoreSources import CoreSources
from .transport.CoreTransport import CoreTransport
# ---------------------------------
from .transport.EdgeProfiles import EdgeProfiles
from .transport.EdgeSources import EdgeSources
from .transport.EdgeTransport import EdgeTransport
# ---------------------------------
from .transport.Equilibrium import Equilibrium
from .transport.MagneticCoordSystem import RadialGrid
from .transport.TransportSolver import TransportSolver

##################################
TWOPI = constants.pi*2.0


class Tokamak(Actor):
    """Tokamak
        功能：
            - 描述装置在单一时刻的状态，
            - 在时间推进时，确定各个子系统之间的依赖和演化关系，

    """

    def __init__(self, d=None, * args, grid: Union[RadialGrid, np.ndarray, None] = None, **kwargs):
        super().__init__(collections.ChainMap(d or {}, kwargs))
        self._time = 0.0
        self._grid = grid

    @property
    def time(self):
        return self._time

    @property
    def grid(self):
        if not isinstance(self._grid, RadialGrid):
            self._grid = self.equilibrium.time_slice.coordinate_system.radial_grid("rho_tor_norm")
        return self._grid
    # --------------------------------------------------------------------------

    @sp_property
    def wall(self) -> Wall:
        return self.get("wall", {})

    @sp_property
    def tf(self) -> TF:
        return self.get("tf", {})

    @sp_property
    def pf_active(self) -> PFActive:
        return self.get("pf_active", {})

    @sp_property
    def magnetics(self) -> Magnetics:
        return self.get("magnetics", {})
    # --------------------------------------------------------------------------

    @sp_property
    def equilibrium(self) -> Equilibrium:
        return self.get("equilibrium", {})

    @sp_property
    def core_profiles(self) -> CoreProfiles:
        return self.get("core_profiles", {})

    @sp_property
    def core_transport(self) -> CoreTransport:
        """Core plasma transport of particles, energy, momentum and poloidal flux."""
        return self.get("core_transport", {})

    @sp_property
    def core_sources(self) -> CoreSources:
        """Core plasma thermal source terms (for the transport equations of the thermal species).
            Energy terms correspond to the full kinetic energy equation
            (i.e. the energy flux takes into account the energy transported by the particle flux)
        """
        return self.get("core_sources", {})

    @sp_property
    def edge_profiles(self) -> EdgeProfiles:
        return self.get("edge_profiles", {})

    @sp_property
    def edge_transport(self) -> EdgeTransport:
        """Edge plasma transport. Energy terms correspond to the full kinetic energy equation
         (i.e. the energy flux takes into account the energy transported by the particle flux)
        """
        return self.get("edge_transport", {})

    @sp_property
    def edge_sources(self) -> EdgeSources:
        """Edge plasma sources. Energy terms correspond to the full kinetic energy equation
         (i.e. the energy flux takes into account the energy transported by the particle flux)
        """
        return self.get("edge_sources", {})

    @sp_property
    def transport_solver(self) -> TransportSolver:
        return self.get("transport_solver", {})

    def advance(self,  dt=None, /,  time=None, **kwargs):

        time = super().advance(time=time, dt=dt)

        self.wall.advance(time=time, update=False)

        self.pf_active.advance(time=time, update=False)

        self.equilibrium.advance(time=time, update=False)

        self.core_profiles.advance(time=time, update=False)

        self.core_sources.advance(time=time, update=False)

        self.core_transport.advance(time=time, update=False)

    def update(self, d=None, /, constraints: Equilibrium.Constraints = None,  max_iteration=1,  enable_edge=False,  tolerance=1.0e-6, **kwargs):
        super().update(collections.ChainMap(d or {}, kwargs))

        for nstep in range(max_iteration):

            self.core_profiles.update()

            self.equilibrium.update(
                constraints=constraints,
                core_profiles=self.core_profiles,
                wall=self.wall,
                pf_active=self.pf_active,
                magnetics=self.magnetics)

            self.core_sources.update(equilibrium=self.equilibrium, core_profiles=self.core_profiles)

            self.core_transport.update(equilibrium=self.equilibrium, core_profiles=self.core_profiles)

            if enable_edge:
                self.edge_transport.update(equilibrium=self.equilibrium, core_profiles=self.core_profiles)

                self.edge_sources.update(equilibrium=self.equilibrium, core_profiles=self.core_profiles)

                self.edge_profiles.update()

                # TODO: update boundary condition
                self.transport_solver.update()

            redisual = self.transport_solver.solve(**kwargs)

            logger.debug(f"time={self.time}  iterator step {nstep}/{max_iteration} redisual={redisual}")

            if redisual < tolerance:
                break

        if redisual > tolerance:
            logger.warning(
                f"The solution does not converge, and the number of iterations exceeds the maximum {max_iteration}")
        return redisual

    def plot(self, axis=None, /,  **kwargs):

        if axis is None:
            axis = plt.gca()

        if kwargs.get("wall", True) is not False:
            self.wall.plot(axis, **kwargs.get("wall", {}))

        if kwargs.get("pf_active", True) is not False:
            self.pf_active.plot(axis, **kwargs.get("pf_active", {}))

        if kwargs.get("equilibrium", True) is not False:
            self.equilibrium.plot(axis,  **kwargs.get("equilibrium", {}))

        axis.set_aspect('equal')
        axis.axis('scaled')
        axis.set_xlabel(r"Major radius $R$ [m]")
        axis.set_ylabel(r"Height $Z$ [m]")
        # axis.legend()

        return axis

    # def initialize(self):
    #     r"""
    #         Set initial conditions self-consistently

    #     """

    #     gamma = self.equilibrium.profiles_1d.dvolume_drho_tor  \
    #         * self.equilibrium.profiles_1d.gm2    \
    #         / self.equilibrium.profiles_1d.fpol \
    #         * self.equilibrium.profiles_1d.dpsi_drho_tor \
    #         / (TWOPI**2)

    #     j_total = -gamma.derivative  \
    #         / self.equilibrium.profiles_1d.rho_tor[-1]**2 \
    #         * self.equilibrium.profiles_1d.dpsi_drho_tor  \
    #         * (self.equilibrium.profiles_1d.fpol**2) \
    #         / (constants.mu_0*self.vacuum_toroidal_field.b0) \
    #         * (constants.pi)

    #     j_total[1:] /= self.equilibrium.profiles_1d.dvolume_drho_tor[1:]
    #     j_total[0] = 2*j_total[1]-j_total[2]

    #     self.core_sources["j_parallel"] = j_total
