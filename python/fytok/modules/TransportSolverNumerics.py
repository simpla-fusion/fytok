from scipy import constants
from copy import copy
from fytok.utils.logger import logger
from spdm.data.sp_property import sp_tree, sp_property
from spdm.data.TimeSeries import TimeSlice
from spdm.utils.tags import _not_found_
from spdm.utils.typing import array_type, as_array
from .CoreProfiles import CoreProfiles
from .CoreSources import CoreSources
from .CoreTransport import CoreTransport
from .Equilibrium import Equilibrium
from .Utilities import *
from ..ontology import transport_solver_numerics

EPSILON = 1.0e-15
TOLERANCE = 1.0e-6

TWOPI = 2.0 * constants.pi


@sp_tree
class TransportSolverNumericsEquationPrimary:
    """Profile and derivatives a the primary quantity for a 1D transport equation"""

    identifier: str
    """ Identifier of the primary quantity of the transport equation. The description
        node contains the path to the quantity in the physics IDS (example:
        core_profiles/profiles_1d/ion(1)/density)"""

    label: str

    profile: array_type
    """ Profile of the primary quantity"""

    flux: array_type
    """ Flux of the primary quantity"""
    dflux_dr: array_type
    """ Flux of the primary quantity"""
    d_dr: array_type
    """ Radial derivative with respect to the primary coordinate"""

    d2_dr2: array_type
    """ Second order radial derivative with respect to the primary coordinate"""

    d_dt: array_type
    """ Time derivative"""

    d_dt_cphi: array_type
    """ Derivative with respect to time, at constant toroidal flux (for current
        diffusion equation)"""

    d_dt_cr: array_type
    """ Derivative with respect to time, at constant primary coordinate coordinate (for
        current diffusion equation)"""


@sp_tree
class TransportSolverNumericsEquation:

    computation_mode: int
    """
        Name          Index    Description
        static            0    Equation is not solved, no profile evolution
        interpretative    1    Equation is not solved, profile is evolved by interpolating from input objects
        predictive        2    Equation is solved, profile evolves
    """

    @sp_tree
    class EquationBC:
        identifier: Identifier
        """ Identifier of the boundary condition type.  ID =
            1: value of the field y;
            2: radial derivative of the field (-dy/drho_tor);
            3: scale length of the field y/(-dy/drho_tor);
            4: flux;
            5: generic boundary condition y expressed as a1y'+a2y=a3.
            6: equation not solved;
        """
        value: array_type
        """ Value of the boundary condition.
            For ID = 1 to 4, only the first position in the vector is used.
            For ID = 5, all three positions are used, meaning respectively a1, a2, a3.
        """
        rho_tor_norm: float
        """ Position, in normalised toroidal flux, at which the boundary condition is
        imposed. Outside this position, the value of the data are considered to be
        prescribed."""

    rho_tor_norm: array_type

    primary_quantity: TransportSolverNumericsEquationPrimary
    """ Profile and derivatives of the primary quantity of the transport equation"""

    boundary_condition: AoS[EquationBC]
    """ Set of boundary conditions of the transport equation"""

    coefficient: AoS
    """ Set of numerical coefficients involved in the transport equation"""

    convergence: AttributeTree
    """ Convergence details"""


@sp_tree(coordinate1="grid/rho_tor_norm")
class TransportSolverNumericsSolver1D:
    """Numerics related to 1D radial solver for a given time slice"""
    Equation = TransportSolverNumericsEquation

    grid: CoreRadialGrid
    """ Radial grid"""

    equation: AoS[TransportSolverNumericsEquation]
    """ Set of transport equations"""

    control_parameters: AttributeTree
    """ Solver-specific input or output quantities"""

    drho_tor_dt: Function = sp_property(units="m.s^-1")
    """ Partial derivative of the toroidal flux coordinate profile with respect to time"""

    d_dvolume_drho_tor_dt: Function = sp_property(units="m^2.s^-1")
    """ Partial derivative with respect to time of the derivative of the volume with
      respect to the toroidal flux coordinate"""


@sp_tree
class TransportSolverNumericsBC:
    """Boundary conditions of radial transport equations for a given time slice"""

    @sp_tree
    class ParticleBC:
        particles: array_type
        """ Particle flux"""

        energy: array_type
        """ Energy flux"""

        momentum: array_type
        """ Momentum flux"""

    rho_tor_norm: float
    """ Position, in normalised toroidal flux, at which the boundary condition is
       imposed. Outside this position, the value of the data are considered to be
       prescribed."""

    identifier: Identifier
    """ Identifier of the boundary condition type. ID = 1: poloidal flux; 2: ip; 3: loop
                voltage; 4: undefined; 5: generic boundary condition y expressed as a1y'+a2y=a3.
                6: equation not solved;"""

    current: float
    """ Boundary condition for the current diffusion equation."""

    electrons: ParticleBC
    """ Quantities related to the electrons"""

    ion: AoS[ParticleBC]
    """ Quantities related to the different ion species"""

    energy_ion_total: ParticleBC = sp_property(units="W.m^-3")
    """ Boundary condition for the ion total (sum over ion species) energy equation
       (temperature if ID = 1)"""

    momentum_tor: ParticleBC = sp_property(units="kg.m.s^-1")
    """ Boundary condition for the total plasma toroidal momentum equation (summed over
       ion species and electrons) (momentum if ID = 1)"""


@sp_tree
class TransportSolverNumericsTimeSlice(TimeSlice):

    Solver1D = TransportSolverNumericsSolver1D

    solver_1d: TransportSolverNumericsSolver1D
    """ Numerics related to 1D radial solver, for various time slices."""


@sp_tree
class TransportSolverNumerics(Module):
    r"""Solve transport equations
        :math:`\rho=\sqrt{ \Phi/\pi B_{0}}`
    """

    _plugin_prefix = 'fytok.plugins.transport_solver_numerics.'

    solver: Identifier

    primary_coordinate: Identifier

    TimeSlice = TransportSolverNumericsTimeSlice

    time_slice: TimeSeriesAoS[TransportSolverNumericsTimeSlice]

    def solve(self,
              current: TimeSlice,
              previous: TimeSlice | None,
              *args, **kwargs):
        raise NotImplementedError(f"{self.__class__.__name__}.solve() is not implemented!")

    def refresh(self, *args,  equilibrium: Equilibrium, **kwargs):
        """
            solve transport equation until residual < tolerance
        """

        eq_grid = equilibrium.time_slice.current.profiles_1d.grid

        rho_tor_norm = kwargs.pop("rho_tor_norm", self.code.parameters.rho_tor_norm)

        if rho_tor_norm is None or rho_tor_norm is _not_found_:
            rho_tor_norm = np.linspace(0.01, 0.995, len(eq_grid.rho_tor_norm))

        grid = copy(eq_grid).remesh(rho_tor_norm)

        # ions = self.code.parameters.get("ions", [])
        # # fmt:off
        # equations = {
        #     "psi"                          :{                      "boundary_condition": []},
        #     "electrons.density_thermal"    :{"profile": 3.0e19,    "boundary_condition": [{"identifier": {"index": 4}, "value": [0]}, {"identifier": {"index": 1}, "value": [3.0e19]}]},
        #     "electrons.density_fast"       :{                      "boundary_condition": []},
        #     "electrons.temperature"        :{                      "boundary_condition": []},
        #     "electrons.momentum"           :{                      "boundary_condition": []},
        # }
        # for label in ions:
        #     update_tree(equations, None, {
        #     f"ion.{label}.density_thermal" :{"profile": 3.0e19,    "boundary_condition": []},
        #     f"ion.{label}.temperature"     :{                      "boundary_condition": []},
        #     f"ion.{label}.density_fast"    :{                      "boundary_condition": []},
        #     f"ion.{label}.temperature"     :{                      "boundary_condition": []},
        #     f"ion.{label}.momentum"        :{                      "boundary_condition": []},
        #     })
        # equations = update_tree(kwargs.pop("equation", None),equations)

        equation=kwargs.pop("equation", {})

        equ = []

        for key,value in equation.items(): 
            equ.append({"primary_quantity": {"identifier": key.replace('.','/'),   "profile": value.pop("profile",None)},**value})

        super().refresh(*args, {"solver_1d": {"grid": grid, "equation": equ}}, equilibrium=equilibrium, **kwargs)

        self.solve(self.time_slice.current, self.time_slice.previous, **self.dependences)

        # current = super().refresh({
        #     "primary_coordinate":  "rho_tor_norm",
        #     "vacuum_toroidal_field": eq.vacuum_toroidal_field,
        #     "solver_1d": {"grid": grid, "equation": equations}
        # })

        # current.refresh(
        #     *args,
        #     core_profiles=core_profiles,
        #     equilibrium=equilibrium,
        #     core_transport=core_transport,
        #     core_sources=core_sources,
        #     ** kwargs)

        # solver_1d: TransportSolverNumericsSolver1D = self.time_slice.current.solver_1d

        # core_profiles_1d["grid"] = solver_1d.grid

        # for equ in solver_1d.equation:
        #     core_profiles_1d[equ.primary_quantity.identifier] = equ.primary_quantity.profile


    def advance(self, *args, **kwargs):

        return super().advance(
            *args,
            {
                "solver_1d": {"equation": []}
            }, **kwargs)
