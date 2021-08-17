"""

"""

import collections
import enum
from itertools import chain
from math import isclose, log
from typing import (Any, Callable, Iterator, Mapping, Optional, Sequence,
                    Tuple, Type, Union)

from fytok.common.Atoms import atoms
from fytok.common.IDS import IDS
from fytok.common.Misc import Identifier, VacuumToroidalField
from fytok.transport.CoreProfiles import CoreProfiles
from fytok.transport.CoreSources import CoreSources
from fytok.transport.CoreTransport import CoreTransport, TransportCoeff
from fytok.transport.CoreTransportSolver import CoreTransportSolver
from fytok.transport.Equilibrium import Equilibrium
from fytok.transport.MagneticCoordSystem import RadialGrid
from matplotlib.pyplot import loglog
from numpy.core.fromnumeric import var
from spdm.data.Function import Function
from spdm.data.Node import Dict, List, _not_found_, sp_property
from spdm.numlib import constants, np
from spdm.numlib.bvp import BVPResult, solve_bvp
from spdm.numlib.misc import array_like
from spdm.util.logger import logger
from spdm.util.utilities import convert_to_named_tuple

EPSILON = 1.0e-15
TOLERANCE = 1.0e-6

TWOPI = 2.0 * constants.pi


class CoreTransportSolverBVP2(CoreTransportSolver):
    r"""
        Solve transport equations :math:`\rho=\sqrt{ \Phi/\pi B_{0}}`
        See  :cite:`hinton_theory_1976,coster_european_2010,pereverzev_astraautomated_1991`

            Solve transport equations

            Current Equation

            Args:
                core_profiles       : profiles at :math:`t-1`
                equilibrium         : Equilibrium
                transports          : CoreTransport
                sources             : CoreSources
                boundary_condition  :

            Note:
                .. math ::  \sigma_{\parallel}\left(\frac{\partial}{\partial t}-\frac{\dot{B}_{0}}{2B_{0}}\frac{\partial}{\partial\rho} \right) \psi= \
                            \frac{F^{2}}{\mu_{0}B_{0}\rho}\frac{\partial}{\partial\rho}\left[\frac{V^{\prime}}{4\pi^{2}}\left\langle \left|\frac{\nabla\rho}{R}\right|^{2}\right\rangle \
                            \frac{1}{F}\frac{\partial\psi}{\partial\rho}\right]-\frac{V^{\prime}}{2\pi\rho}\left(j_{ni,exp}+j_{ni,imp}\psi\right)
                    :label: transport_current


                if :math:`\psi` is not solved, then

                ..  math ::  \psi =\int_{0}^{\rho}\frac{2\pi B_{0}}{q}\rho d\rho

            Particle Transport
            Note:

                .. math::
                    \left(\frac{\partial}{\partial t}-\frac{\dot{B}_{0}}{2B_{0}}\frac{\partial}{\partial\rho}\rho\right)\
                    \left(V^{\prime}n_{s}\right)+\frac{\partial}{\partial\rho}\Gamma_{s}=\
                    V^{\prime}\left(S_{s,exp}-S_{s,imp}\cdot n_{s}\right)
                    :label: particle_density_transport

                .. math::
                    \Gamma_{s}\equiv-D_{s}\cdot\frac{\partial n_{s}}{\partial\rho}+v_{s}^{pinch}\cdot n_{s}
                    :label: particle_density_gamma

            Heat transport equations

            Note:

                ion

                .. math:: \frac{3}{2}\left(\frac{\partial}{\partial t}-\frac{\dot{B}_{0}}{2B_{0}}\frac{\partial}{\partial\rho}\rho\right)\
                            \left(n_{i}T_{i}V^{\prime\frac{5}{3}}\right)+V^{\prime\frac{2}{3}}\frac{\partial}{\partial\rho}\left(q_{i}+T_{i}\gamma_{i}\right)=\
                            V^{\prime\frac{5}{3}}\left[Q_{i,exp}-Q_{i,imp}\cdot T_{i}+Q_{ei}+Q_{zi}+Q_{\gamma i}\right]
                    :label: transport_ion_temperature

                electron

                .. math:: \frac{3}{2}\left(\frac{\partial}{\partial t}-\frac{\dot{B}_{0}}{2B_{0}}\frac{\partial}{\partial\rho}\rho\right)\
                            \left(n_{e}T_{e}V^{\prime\frac{5}{3}}\right)+V^{\prime\frac{2}{3}}\frac{\partial}{\partial\rho}\left(q_{e}+T_{e}\gamma_{e}\right)=
                            V^{\prime\frac{5}{3}}\left[Q_{e,exp}-Q_{e,imp}\cdot T_{e}+Q_{ei}-Q_{\gamma i}\right]
                    :label: transport_electron_temperature
        """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def transp_current(self, x: np.ndarray, y: np.ndarray, g: np.ndarray,
                       ym: Function,
                       conductivity_parallel: Function,
                       j_parallel: Function,
                       hyper_diff=1e-4,
                       **kwargs):

        conductivity_parallel = conductivity_parallel(x)

        j_parallel = j_parallel(x)

        ym = ym(x)

        yp = Function(x, y).derivative(x)

        inv_tau = self._inv_tau

        B0 = self._B0

        fpol = self._fpol(x)

        fpol2 = fpol**2

        vpr = self._vpr(x)

        gm2 = self._gm2(x)

        rho_tor_boundary = self._rho_tor_boundary

        a = conductivity_parallel * x * rho_tor_boundary

        b = conductivity_parallel * x * rho_tor_boundary

        c = (constants.mu_0 * B0 * rho_tor_boundary)/fpol2

        d = vpr * gm2 / fpol / (rho_tor_boundary)/(TWOPI)

        e = 0

        S = -  vpr * (j_parallel)/TWOPI

        dy = (-g + e * y + hyper_diff * yp)/(d + hyper_diff)

        dg = S

        if not np.isclose(inv_tau, 0.0):
            k_phi = self._k_phi
            Qimp_k_ns = self._Qimp_k_ns(x)
            C = (constants.mu_0 * B0 * k_phi) * (conductivity_parallel * (x*rho_tor_boundary)**2/fpol2)
            dg = dg - (a * y - b * ym) * inv_tau
            dg = dg + conductivity_parallel*Qimp_k_ns*y
            dg = dg + Function(x, C).derivative(x)*y + C*dy

        dg = dg*c

        dy = array_like(x, dy)

        dy[0] = 0

        dg = array_like(x, dg)

        return dy, dg

    def bc_current(self, ya: float, ga: float, yb: float, gb: float, bc: CoreTransportSolver.BoundaryConditions1D.BoundaryConditions,):

        # -----------------------------------------------------------
        # boundary condition, value
        # bc: CoreTransportSolver.BoundaryConditions1D.BoundaryConditions = self.boundary_conditions_1d.current
        # axis
        ua, va, wa = 0, 1, 0

        # Identifier of the boundary condition type.
        #   ID =    1: poloidal flux;
        #           2: ip;
        #           3: loop voltage;
        #           4: undefined;
        #           5: generic boundary condition y expressed as a1y'+a2y=a3.
        #           6: equation not solved; [eV]

        if bc.identifier.index == 1:  # poloidal flux;
            ub = 1
            vb = 0
            wb = bc.value[0]
        elif bc.identifier.index == 2:  # ip, total current inside x=1
            Ip = bc.value[0]
            ub = 0
            vb = 1
            wb = constants.mu_0 * Ip / self._fpol[-1]
        elif bc.identifier.index == 3:  # loop voltage;
            Uloop_bdry = bc.value[0]
            ub = 0
            vb = 1
            wb = (self._tau*Uloop_bdry + self._core_profiles_prev["psi"][-1])*d(1.0)
        elif bc.identifier.index == 5:  # generic boundary condition y expressed as a1y' + a2y=a3;
            ub = bc.value[1]
            vb = bc.value[0]
            wb = bc.value[2]
        elif bc.identifier.index == 6:  # equation not solved;
            raise NotImplementedError(bc.identifier.index)
        else:
            raise NotImplementedError(bc)

        return float((ua * ya + va * ga - wa)), float((ub * yb + vb * gb - wb))

    def transp_particle(self,
                        x: np.ndarray, y: np.ndarray, g: np.ndarray,
                        ym: Function,
                        n_diff:  Function,
                        n_vconv: Function,
                        n_src: Function,
                        hyper_diff=1e-4,
                        ** kwargs) -> Tuple[np.ndarray, np.ndarray]:

        inv_tau = self._inv_tau

        rho_tor_boundary = self._rho_tor_boundary

        k_phi = self._k_phi

        k_rho_bdry = self._k_rho_bdry

        vpr = self._vpr(x)

        vprm = self._vprm(x)

        gm3 = self._gm3(x)

        ym = ym(x)

        yp = Function(x, y).derivative(x)

        a = vpr

        b = vprm

        c = rho_tor_boundary

        d = vpr * gm3 * n_diff(x) / rho_tor_boundary

        e = vpr * gm3 * n_vconv(x)

        S = vpr * n_src(x)

        dy = (-g + e * y + hyper_diff * yp)/(d + hyper_diff)

        dg = S

        if not isclose(inv_tau, 0.0):
            dg = dg - (a * y - b * ym)*inv_tau + vpr * k_rho_bdry
            dg = dg + Function(x, vpr * x * k_phi).derivative(x)*y
            dg = dg + vpr * x * k_phi * dy

        dg = dg*c
        dy = array_like(x, dy)
        dg = array_like(x, dg)
        return dy, dg

        # -----------------------------------------------------------
        # boundary condition, value

    def bc_particle(self, ya: float, ga: float, yb: float, gb: float, bc: CoreTransportSolver.BoundaryConditions1D.BoundaryConditions,):

        # axis
        u0, v0, w0 = 0, 1, 0

        if bc.identifier.index == 1:
            u1 = 1
            v1 = 0
            w1 = bc.value[0]
        else:
            raise NotImplementedError(bc.identifier)

        return float((u0 * ya + v0 * ga - w0)), float((u1 * yb + v1 * gb - w1))

    def transp_energy(self, x: np.ndarray,  y: np.ndarray, g: np.ndarray,
                      ym: Function,
                      q_diff:  Function,
                      q_vconv:  Function,
                      q_src:  Function,
                      density: np.ndarray,
                      g_density: np.ndarray,
                      hyper_diff=1e-4,  **kwargs) -> Tuple[np.ndarray, np.ndarray]:

        inv_tau = self._inv_tau

        rho_tor_boundary = self._rho_tor_boundary

        k_phi = self._k_phi

        k_rho_bdry = self._k_rho_bdry

        vpr = self._vpr(x)

        vprm = self._vprm(x)

        vpr5_3 = vpr**(5/3)

        vpr5_3m = vprm**(5/3)

        inv_vpr23 = self._inv_vpr23(x)

        Qimp_k_ns = self._Qimp_k_ns(x)

        gm3 = self._gm3(x)

        # density = Y[(var_idx-1)*2]
        # g_density = Y[(var_idx-1)*2+1]
        # ym = Function(x0, Y0[var_idx*2])(x)
        # y = Y[var_idx*2]

        ym = ym(x)

        yp = Function(x, y).derivative(x)

        a = (3/2) * vpr5_3 * y

        b = (3/2) * vpr5_3m * ym

        c = rho_tor_boundary * inv_vpr23

        d = vpr * gm3 * density * q_diff(x) / rho_tor_boundary

        e = vpr * gm3 * density * q_vconv(x) + 3/2 * g_density

        S = vpr5_3 * q_src(x)

        dy = (-g + e * y + hyper_diff * yp)/(d + hyper_diff)

        dg = S

        if not isclose(inv_tau, 0.0):
            dg = dg - (a * y - b * ym)*inv_tau
            dg = dg + vpr5_3 * Qimp_k_ns * y
            dg = dg + Function(x,  vpr * (3/4)*k_phi * x * density).derivative(x) * y
            dg = dg + vpr * (3/4)*k_phi * x * density*dy

        dg = dg*c

        dy = array_like(x, dy)
        dg = array_like(x, dg)
        dy[0] = 0
        return dy, dg

    def bc_energy(self, ya: float, ga: float, yb: float, gb: float, bc: CoreTransportSolver.BoundaryConditions1D.BoundaryConditions,):

        # ----------------------------------------------
        # Boundary Condition
        # bc: CoreTransportSolver.BoundaryConditions1D.BoundaryConditions = \
        #     self.boundary_conditions_1d.fetch(var_id).energy

        # axis
        u0, v0, w0 = 0, 1, 0

        if bc.identifier.index == 1:
            u1 = 1
            v1 = 0
            w1 = bc.value[0]
        else:
            raise NotImplementedError(bc)

        return float((u0 * ya + v0 * ga - w0)), float((u1 * yb + v1 * gb - w1))

    def transp_rotation(self, var_idx: int, var_id: Sequence, x0: np.ndarray, Y0: np.ndarray,
                        inv_tau=None, hyper_diff=1e-4, **kwargs):
        r"""
            Rotation Transport
            .. math::  \left(\frac{\partial}{\partial t}-\frac{\dot{B}_{0}}{2B_{0}}\frac{\partial}{\partial\rho}\rho\right)\left(V^{\prime\frac{5}{3}}\left\langle R\right\rangle \
                        m_{i}n_{i}u_{i,\varphi}\right)+\frac{\partial}{\partial\rho}\Phi_{i}=V^{\prime}\left[U_{i,\varphi,exp}-U_{i,\varphi}\cdot u_{i,\varphi}+U_{zi,\varphi}\right]
                :label: transport_rotation
        """
        logger.warning(f"TODO: Rotation Transport is not implemented!")
        return 0.0

    def create_solver_electrons(self, *args,
                                core_profiles_prev_1d: CoreProfiles.Profiles1D,
                                core_transport_1d: CoreTransport.Model.Profiles1D,
                                core_sources_1d: CoreSources.Source.Profiles1D,
                                hyper_diff=1.0e-4,
                                **kwargsd):
        x0 = core_profiles_prev_1d.grid.rho_tor_norm
        Y0 = []
        var_list = []
        eq_list = []
        bc_list = []
        other_var_list = []

        # current
        psi = core_profiles_prev_1d.get("psi", None)

        if psi is None:
            psi = core_profiles_prev_1d.grid.psi

        psi = Function(core_profiles_prev_1d.grid.rho_tor_norm, psi)

        eq_list.append(lambda x, Y, _idx=len(Y0),
                       _ym=psi,
                       _conductivity_parallel=core_transport_1d.conductivity_parallel,
                       _j_parallel=core_sources_1d.j_parallel:
                       self.transp_current(
            x, Y[_idx], Y[_idx+1],
            ym=_ym,
            conductivity_parallel=_conductivity_parallel,
            j_parallel=_j_parallel,
            hyper_diff=hyper_diff))

        bc_list.append(lambda Ya, Yb, _idx=len(Y0), _bc=self.boundary_conditions_1d.current:
                       self.bc_current(Ya[_idx], Ya[_idx+1], Yb[_idx], Yb[_idx+1], _bc))

        Y0.append(psi)

        Y0.append(np.zeros_like(x0))

        var_list.append(["psi"])

        # electron density
        ne_idx = len(Y0)
        eq_list.append(lambda x, Y, _idx=len(Y0):
                       self.transp_particle(
            x, Y[_idx], Y[_idx+1],
            ym=core_profiles_prev_1d.electrons.density,
            n_diff=core_transport_1d.electrons.particles.d,
            n_vconv=core_transport_1d.electrons.particles.v,
            n_src=core_sources_1d.electrons.particles,
            hyper_diff=hyper_diff))

        bc_list.append(lambda Ya, Yb, _idx=len(Y0), _bc=self.boundary_conditions_1d.electrons.particles:
                       self.bc_particle(Ya[_idx], Ya[_idx+1], Yb[_idx], Yb[_idx+1], _bc))

        Y0.append(core_profiles_prev_1d.electrons.density(x0))

        Y0.append(np.zeros_like(x0))

        var_list.append(["electrons", "density"])

        # electron temperature
        eq_list.append(lambda x, Y, _idx=len(Y0):
                       self.transp_energy(
            x, Y[_idx], Y[_idx+1],
            ym=core_profiles_prev_1d.electrons.temperature,
            q_diff=core_transport_1d.electrons.energy.d,
            q_vconv=core_transport_1d.electrons.energy.v,
            q_src=core_sources_1d.electrons.energy,
            density=Y[_idx-2],
            g_density=Y[_idx-1],
            hyper_diff=hyper_diff))

        bc_list.append(lambda Ya, Yb, _idx=len(Y0), _bc=self.boundary_conditions_1d.electrons.energy:
                       self.bc_energy(Ya[_idx], Ya[_idx+1], Yb[_idx], Yb[_idx+1], _bc))

        Y0.append(core_profiles_prev_1d.electrons.temperature(x0))

        Y0.append(np.zeros_like(x0))

        var_list.append(["electrons", "temperature"])

        # ion   temperature
        Z_total = sum([ion.z for ion in core_profiles_prev_1d.ion if not ion.is_impurity])

        n_imp = sum([ion.z_ion_1d*ion.density for ion in core_profiles_prev_1d.ion if ion.is_impurity])
        # g_imp = sum([ion.z_ion_1d*ion.density_flux for ion in core_profiles_1d.ion if not ion.is_impurity])

        # ions
        for ion in core_profiles_prev_1d.ion:
            if ion.is_impurity:
                continue

            eq_list.append(lambda x, Y, _idx=len(Y0),
                           _ym=core_profiles_prev_1d.ion[{"label": ion.label}].temperature,
                           _ne_idx=ne_idx,
                           _n_imp=n_imp,
                           _n_ratio=ion.z/Z_total,
                           _q_trans=core_transport_1d.ion[{"label": ion.label}].energy,
                           _q_src=core_sources_1d.ion[{"label": ion.label}].energy:
                           self.transp_energy(
                x, Y[_idx], Y[_idx+1],
                ym=_ym,
                density=_n_ratio*(Y[_ne_idx] - _n_imp(x)),
                g_density=_n_ratio*(Y[_ne_idx+1]),
                q_diff=_q_trans.d,
                q_vconv=_q_trans.v,
                q_src=_q_src,
                hyper_diff=hyper_diff))

            bc_list.append(lambda Ya, Yb, _idx=len(Y0), _bc=self.boundary_conditions_1d.ion[{"label": ion.label}].energy:
                           self.bc_energy(Ya[_idx], Ya[_idx+1], Yb[_idx], Yb[_idx+1], _bc))

            var_list.append(["ion", {"label": ion.label}, "temperature"])

            Y0.append(core_profiles_prev_1d.ion[{"label": ion.label}].temperature(x0))

            Y0.append(np.zeros_like(x0))

        Y0 = np.vstack(Y0)

        return var_list, x0, Y0, eq_list, bc_list, other_var_list

    def create_solver_ion(self, *args,
                          core_profiles_prev_1d: CoreProfiles.Profiles1D,
                          core_transport_1d: CoreTransport.Model.Profiles1D,
                          core_sources_1d: CoreSources.Source.Profiles1D,
                          hyper_diff=1.0e-4,
                          **kwargsd):
        x0 = core_profiles_prev_1d.grid.rho_tor_norm
        Y0 = []
        var_list = []
        eq_list = []
        bc_list = []
        other_var_list = []

        # current
        psi = core_profiles_prev_1d.get("psi", None)

        if psi is None:
            psi = core_profiles_prev_1d.grid.psi

        psi = Function(core_profiles_prev_1d.grid.rho_tor_norm, psi)

        eq_list.append(lambda x, Y, _idx=len(Y0),
                       _ym=psi,
                       _conductivity_parallel=core_transport_1d.conductivity_parallel,
                       _j_parallel=core_sources_1d.j_parallel:
                       self.transp_current(
            x, Y[_idx], Y[_idx+1],
            ym=_ym,
            conductivity_parallel=_conductivity_parallel,
            j_parallel=_j_parallel,
            hyper_diff=hyper_diff))

        bc_list.append(lambda Ya, Yb, _idx=len(Y0), _bc=self.boundary_conditions_1d.current:
                       self.bc_current(Ya[_idx], Ya[_idx+1], Yb[_idx], Yb[_idx+1], _bc))

        Y0.append(psi)

        Y0.append(np.zeros_like(x0))

        var_list.append(["psi"])

        # ion   temperature
        Z_total = sum([ion.z for ion in core_profiles_prev_1d.ion if not ion.is_impurity])

        n_imp = sum([ion.z_ion_1d*ion.density for ion in core_profiles_prev_1d.ion if ion.is_impurity])
        g_imp = sum([ion.z_ion_1d*ion.get("density_flux", 0)
                     for ion in core_profiles_prev_1d.ion if not ion.is_impurity])

        ion_list = []
        
        # ions
        for ion in core_profiles_prev_1d.ion:
            if ion.is_impurity:
                continue
            ion_list.append((len(Y0), ion.z))
            # density
            eq_list.append(lambda x, Y, _idx=len(Y0):
                           self.transp_particle(
                x, Y[_idx], Y[_idx+1],
                ym=core_profiles_prev_1d.electrons.density,
                n_diff=core_transport_1d.electrons.particles.d,
                n_vconv=core_transport_1d.electrons.particles.v,
                n_src=core_sources_1d.electrons.particles,
                hyper_diff=hyper_diff))

            bc_list.append(lambda Ya, Yb, _idx=len(Y0), _bc=self.boundary_conditions_1d.electrons.particles:
                           self.bc_particle(Ya[_idx], Ya[_idx+1], Yb[_idx], Yb[_idx+1], _bc))

            Y0.append(core_profiles_prev_1d.electrons.density(x0))

            Y0.append(np.zeros_like(x0))

            var_list.append(["ion", {"label": ion.label}, "density"])

            # temperature
            eq_list.append(lambda x, Y, _idx=len(Y0),
                           _ym=core_profiles_prev_1d.ion[{"label": ion.label}].temperature,
                           _q_trans=core_transport_1d.ion[{"label": ion.label}].energy,
                           _q_src=core_sources_1d.ion[{"label": ion.label}].energy:
                           self.transp_energy(
                x, Y[_idx], Y[_idx+1],
                ym=_ym,
                density=Y[_idx-2],
                g_density=Y[_idx-1],
                q_diff=_q_trans.d,
                q_vconv=_q_trans.v,
                q_src=_q_src,
                hyper_diff=hyper_diff))

            bc_list.append(lambda Ya, Yb, _idx=len(Y0), _bc=self.boundary_conditions_1d.ion[{"label": ion.label}].energy:
                           self.bc_energy(Ya[_idx], Ya[_idx+1], Yb[_idx], Yb[_idx+1], _bc))

            var_list.append(["ion", {"label": ion.label}, "temperature"])

            Y0.append(core_profiles_prev_1d.ion[{"label": ion.label}].temperature(x0))

            Y0.append(np.zeros_like(x0))

        # electron temperature
        eq_list.append(lambda x, Y, _idx=len(Y0),
                       _ym=core_profiles_prev_1d.electrons.temperature,
                       _n_imp=n_imp,
                       _g_imp=g_imp,
                       _q_diff=core_transport_1d.electrons.energy.d,
                       _q_vconv=core_transport_1d.electrons.energy.v,
                       _q_src=core_sources_1d.electrons.energy, :
                       self.transp_energy(
            x, Y[_idx], Y[_idx+1],
            ym=_ym,
            q_diff=_q_diff,
            q_vconv=_q_vconv,
            q_src=_q_src,
            density=np.sum([Y[i]*z for i, z in ion_list]) + _n_imp,
            g_density=np.sum([Y[i+1] * z for i, z in ion_list]) + _g_imp,
            hyper_diff=hyper_diff))

        bc_list.append(lambda Ya, Yb, _idx=len(Y0), _bc=self.boundary_conditions_1d.electrons.energy:
                       self.bc_energy(Ya[_idx], Ya[_idx+1], Yb[_idx], Yb[_idx+1], _bc))

        Y0.append(core_profiles_prev_1d.electrons.temperature(x0))

        Y0.append(np.zeros_like(x0))

        var_list.append(["electrons", "temperature"])

        Y0 = np.vstack(Y0)

        return var_list, x0, Y0, eq_list, bc_list, other_var_list

    def update_global_variable(self,
                               core_profiles_prev: CoreProfiles,
                               equilibrium_next: Equilibrium,
                               equilibrium_prev: Equilibrium = None,
                               dt=None,
                               **kwargs):
        # $rho_tor_{norm}$ normalized minor radius                [-]
        rho_tor_norm = core_profiles_prev.profiles_1d.grid.rho_tor_norm

        psi_norm = core_profiles_prev.profiles_1d.grid.psi_norm

        # -----------------------------------------------------------
        # Equilibrium

        if equilibrium_prev is None:
            equilibrium_prev = equilibrium_next

        self._tau = dt if dt is not None else equilibrium_next.time-equilibrium_prev.time

        self._inv_tau = 0.0 if isclose(self._tau, 0.0) else 1.0/self._tau

        # $R_0$ characteristic major radius of the device   [m]
        self._R0 = equilibrium_next.vacuum_toroidal_field.r0

        # $B_0$ magnetic field measured at $R_0$            [T]
        self._B0 = equilibrium_next.vacuum_toroidal_field.b0

        self._B0m = equilibrium_prev.vacuum_toroidal_field.b0

        # Grid
        self._rho_tor_boundary = equilibrium_next.profiles_1d.rho_tor[-1]

        self._rho_tor_boundary_m = equilibrium_prev.profiles_1d.rho_tor[-1]

        self._k_B = (self._B0 - self._B0m) / (self._B0 + self._B0m) * self._inv_tau * 2.0

        self._k_rho_bdry = (self._rho_tor_boundary - self._rho_tor_boundary_m) / \
            (self._rho_tor_boundary + self._rho_tor_boundary_m)*self._inv_tau*2.0

        self._k_phi = self._k_B + self._k_rho_bdry

        # diamagnetic function,$F=R B_\phi$                 [T*m]
        self._fpol = Function(rho_tor_norm,  equilibrium_next.profiles_1d.fpol(psi_norm))

        # $\frac{\partial V}{\partial\rho}$ V',             [m^2]

        self._vpr = Function(rho_tor_norm, equilibrium_next.profiles_1d.dvolume_drho_tor(psi_norm))

        self._vprm = Function(rho_tor_norm,  equilibrium_prev.profiles_1d.dvolume_drho_tor(psi_norm))

        self._vpr5_3 = np.abs(self._vpr)**(5/3)
        self._vpr5_3m = np.abs(self._vprm)**(5/3)

        if np.isclose(equilibrium_next.profiles_1d.dvolume_drho_tor(psi_norm[0]), 0.0):
            self._inv_vpr23 = Function(
                rho_tor_norm[1:], equilibrium_next.profiles_1d.dvolume_drho_tor(psi_norm[1:])**(-2/3))
        else:
            self._inv_vpr23 = Function(rho_tor_norm,   equilibrium_next.profiles_1d.dvolume_drho_tor(psi_norm)**(-2/3))

        # $q$ safety factor                                 [-]
        self._qsf = Function(rho_tor_norm,   equilibrium_next.profiles_1d.q(psi_norm))
        self._gm1 = Function(rho_tor_norm,   equilibrium_next.profiles_1d.gm1(psi_norm))
        self._gm2 = Function(rho_tor_norm,   equilibrium_next.profiles_1d.gm2(psi_norm))
        self._gm3 = Function(rho_tor_norm,   equilibrium_next.profiles_1d.gm3(psi_norm))

        self._Qimp_k_ns = (3*self._k_rho_bdry - self._k_phi * self._vpr.derivative())

    def solve(self, /,
              core_profiles_prev: CoreProfiles,
              core_transport: CoreTransport.Model,
              core_sources: CoreSources.Source,
              equilibrium_next: Equilibrium,
              equilibrium_prev: Equilibrium = None,
              dt=None,
              quasi_neutral: str = "electrons",
              hyper_diff=1.0e-4,
              tolerance=1.0e-3,
              max_nodes=250, **kwargs) -> Tuple[float, CoreProfiles]:

        self.update_global_variable(
            core_profiles_prev=core_profiles_prev,
            core_transport=core_transport,
            core_sources=core_sources,
            equilibrium_next=equilibrium_next,
            equilibrium_prev=equilibrium_prev,
            dt=dt,
            hyper_diff=hyper_diff,
        )

        if quasi_neutral == "electrons":
            var_list, x0, Y0, eq_list, bc_list, *_ = self.create_solver_electrons(
                core_profiles_prev_1d=core_profiles_prev.profiles_1d,
                core_transport_1d=core_transport.profiles_1d,
                core_sources_1d=core_sources.profiles_1d,
                hyper_diff=hyper_diff
            )
        else:
            var_list, x0, Y0, eq_list, bc_list, *_ = self.create_solver_ion(
                core_profiles_1d=core_profiles_prev.profiles_1d,
                core_transport_1d=core_transport.profiles_1d,
                core_sources_1d=core_sources.profiles_1d,
                hyper_diff=hyper_diff
            )

        def func(x, Y, _eq_list=eq_list) -> np.ndarray:
            v_list = sum([list(eq(x, Y)) for eq in _eq_list], [])
            return np.vstack([array_like(x, d) for d in v_list])

        def bc_func(Ya: np.ndarray, Yb: np.ndarray, /, _bc_list=bc_list) -> np.ndarray:
            return np.asarray(sum([list(bc(Ya, Yb)) for bc in _bc_list], []))

        sol = solve_bvp(func, bc_func, x0, Y0, tolerance=tolerance, max_nodes=max_nodes, **kwargs)

        residual = np.max(sol.rms_residuals)

        core_profiles_next = CoreProfiles()

        profiles_1d_next = core_profiles_next.profiles_1d

        profiles_1d_next["grid"] = equilibrium_next.radial_grid.remesh("rho_tor_norm", sol.x)

        rho_tor_norm = profiles_1d_next.grid.rho_tor_norm

        profiles_1d_next["electrons"] = {**atoms["e"]}

        profiles_1d_next["ion"] = [
            {**atoms[ion.label],
             "z_ion_1d":ion.z_ion_1d(rho_tor_norm),
             "is_impurity":ion.is_impurity,
             }
            for ion in core_profiles_prev.profiles_1d.ion
        ]
        profiles_1d_next["conductivity_parallel"] = Function(
            rho_tor_norm, core_transport.profiles_1d.conductivity_parallel(rho_tor_norm))

        profiles_1d_next["j_total"] = Function(rho_tor_norm, core_sources.profiles_1d.j_parallel(rho_tor_norm))

        for idx, var_id in enumerate(var_list):
            profiles_1d_next[var_id] = Function(rho_tor_norm, sol.y[idx*2])
            profiles_1d_next[var_id[:-1]+[f"{var_id[-1]}_flux"]] = Function(rho_tor_norm, sol.y[idx*2+1])

        profiles_1d_next["rms_residuals"] = Function((rho_tor_norm[: -1]+rho_tor_norm[1:])*0.5, sol.rms_residuals)

        logger.info(
            f"Solve transport equations [{'Success' if sol.success else 'Failed'}] : max reduisal={residual} \n  {var_list}")

        return residual,  core_profiles_next


__SP_EXPORT__ = CoreTransportSolverBVP2
