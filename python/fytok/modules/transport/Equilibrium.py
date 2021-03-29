import collections
from functools import cached_property

import matplotlib.pyplot as plt
import numpy as np
import scipy
from numpy import arctan2, cos, sin, sqrt
from numpy.lib.arraysetops import isin
from scipy.optimize import fsolve, root_scalar
from spdm.data.Field import Field
from spdm.data.Function import Function
from spdm.data.PhysicalGraph import PhysicalGraph
from spdm.util.logger import logger
from spdm.data.mesh.CurvilinearMesh import CurvilinearMesh

TOLERANCE = 1.0e-6


class Equilibrium(PhysicalGraph):
    r"""Description of a 2D, axi-symmetric, tokamak equilibrium; result of an equilibrium code.

        Reference:
            - O. Sauter and S. Yu Medvedev, "Tokamak coordinate conventions: COCOS", Computer Physics Communications 184, 2 (2013), pp. 293--302.

        COCOS  11

        #    Top view
        #             ***************
        #            *               *
        #           *   ***********   *
        #          *   *           *   *
        #         *   *             *   *
        #         *   *             *   *
        #     Ip  v   *             *   ^  \phi
        #         *   *    Z o--->R *   *
        #         *   *             *   *
        #         *   *             *   *
        #         *   *     Bpol    *   *
        #          *   *     o     *   *
        #           *   ***********   *
        #            *               *
        #             ***************
        #               Bpol x
        #            Poloidal view
        #        ^Z
        #        |
        #        |       ************
        #        |      *            *
        #        |     *         ^    *
        #        |     *   \rho /     *
        #        |     *       /      *
        #        +-----*------X-------*---->R
        #        |     *  Ip, \phi   *
        #        |     *              *
        #        |      *            *
        #        |       *****<******
        #        |       Bpol,\theta
        #        |
        #            Cylindrical coordinate      : (R,\phi,Z)
        #    Poloidal plane coordinate   : (\rho,\theta,\phi)
    """

    IDS = "transport.equilibrium"

    DEFAULT_PLUGIN = "FreeGS"

    def __init__(self, *args,   **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def vacuum_toroidal_field(self):
        return self["vacuum_toroidal_field"]

    @property
    def time(self):
        return self._parent.time

    def update(self, *args, time=None, ** kwargs):
        if time is not None:
            self._time = time

        logger.debug(f"Solve Equilibrium [{self.__class__.__name__}] at: Done")

        self.update_cache()

    def update_cache(self):
        del self.global_quantities
        del self.profiles_1d
        self.profiles_2d.update()
        del self.boundary
        del self.boundary_separatrix
        del self.coordinate_system

    @cached_property
    def psirz(self):
        mesh_type = self["profiles_2d.grid_type.name"] or "rectilinear"
        dim1 = self["profiles_2d.grid.dim1"]
        dim2 = self["profiles_2d.grid.dim2"]
        return Field(self["profiles_2d.psi"], dim1, dim2, mesh_type=mesh_type)

    @cached_property
    def critical_points(self):
        opoints = []
        xpoints = []

        for r, z, psi, D in self.psirz.find_peak():
            p = PhysicalGraph({"r": r, "z": z, "psi": psi})

            if D < 0.0:  # saddle/X-point
                xpoints.append(p)
            else:  # extremum/ O-point
                opoints.append(p)

        # wall = getattr(self._parent._parent, "wall", None)
        # if wall is not None:
        #     xpoints = [p for p in xpoints if wall.in_limiter(p.r, p.z)]

        if not opoints:
            raise RuntimeError(f"Can not find o-point!")
        else:

            bbox = self.psirz.coordinates.mesh.bbox
            Rmid = (bbox[0][0] + bbox[0][1])/2.0
            Zmid = (bbox[1][0] + bbox[1][1])/2.0

            opoints.sort(key=lambda x: (x.r - Rmid)**2 + (x.z - Zmid)**2)

            psi_axis = opoints[0].psi

            xpoints.sort(key=lambda x: (x.psi - psi_axis)**2)

        return opoints, xpoints

    def find_flux_surface(self, u, v=None):
        o_points, x_points = self.critical_points

        if len(o_points) == 0:
            raise RuntimeError(f"Can not find O-point!")
        else:
            R0 = o_points[0].r
            Z0 = o_points[0].z
            psi0 = o_points[0].psi

        if len(x_points) == 0:
            R1 = self._psirz.coordinates.bbox[1][0]
            Z1 = Z0
            psi1 = 0.0
        else:
            R1 = x_points[0].r
            Z1 = x_points[0].z
            psi1 = x_points[0].psi

        theta0 = arctan2(R1 - R0, Z1 - Z0)
        Rm = sqrt((R1-R0)**2+(Z1-Z0)**2)

        if not isinstance(u, (np.ndarray, collections.abc.Sequence)):
            u = [u]

        if v is None:
            v = np.linspace(0, 2.0*scipy.constants.pi, 128, endpoint=False)
        elif not isinstance(v, (np.ndarray, collections.abc.Sequence)):
            v = [v]

        for p in u:
            for t in v:
                psival = p*(psi1-psi0)+psi0

                r0 = R0
                z0 = Z0
                r1 = R0+Rm*sin(t+theta0)
                z1 = Z0+Rm*cos(t+theta0)

                if not np.isclose(self.psirz(r1, z1), psival):
                    try:
                        def func(r): return float(self.psirz((1.0-r)*r0+r*r1, (1.0-r)*z0+r*z1)) - psival
                        sol = root_scalar(func,  bracket=[0, 1], method='brentq')
                    except ValueError as error:
                        raise ValueError(f"Find root fialed! {error} {psival}")

                    if not sol.converged:
                        raise ValueError(f"Find root fialed!")

                    r1 = (1.0-sol.root)*r0+sol.root*r1
                    z1 = (1.0-sol.root)*z0+sol.root*z1

                yield r1, z1

    @cached_property
    def profiles_1d(self):
        return Equilibrium.Profiles1D(self["profiles_1d"], parent=self)

    @cached_property
    def profiles_2d(self):
        return Equilibrium.Profiles2D(self["profiles_2d"], parent=self)

    @cached_property
    def global_quantities(self):
        return Equilibrium.GlobalQuantities(self["global_quantities"], parent=self)

    @cached_property
    def boundary(self):
        return Equilibrium.Boundary(self["boundary"], parent=self)

    @cached_property
    def boundary_separatrix(self):
        return Equilibrium.BoundarySeparatrix(self["boundary_separatrix"], parent=self)

    @cached_property
    def constraints(self):
        return Equilibrium.Constraints(self["constraints"], parent=self)

    @cached_property
    def coordinate_system(self):
        return Equilibrium.CoordinateSystem(self["coordinate_system"], parent=self)

    class CoordinateSystem(PhysicalGraph):
        r"""
            Flux surface coordinate system on a square grid of flux and poloidal angle

            .. math::
                V^{\prime}\left(\rho\right)=\frac{\partial V}{\partial\rho}=2\pi\int_{0}^{2\pi}\sqrt{g}d\theta=2\pi\oint\frac{R}{\left|\nabla\rho\right|}dl

            .. math::
                \left\langle\alpha\right\rangle\equiv\frac{2\pi}{V^{\prime}}\int_{0}^{2\pi}\alpha\sqrt{g}d\theta=\frac{2\pi}{V^{\prime}}\varoint\alpha\frac{R}{\left|\nabla\rho\right|}dl

            Magnetic Flux Coordinates
            psi         :                     ,  flux function , $B \cdot \nabla \psi=0$ need not to be the poloidal flux funcion $\Psi$
            theta       : 0 <= theta   < 2*pi ,  poloidal angle
            phi         : 0 <= phi     < 2*pi ,  toroidal angle
        """

        def __init__(self,  *args,   ** kwargs):
            """
                Initialize FluxSurface
            """
            super().__init__(self, *args,   **kwargs)

        @cached_property
        def mesh(self):

            if self.grid_type.index != None and int(self.grid_type.index) < 10 or str(self.grid_type.name) == "rectangle":
                return NotImplemented

            dim1 = self.grid.dim1
            dim2 = self.grid.dim2

            if dim1 == None:
                u = np.linspace(0.0,  1.0,  64)
            elif isinstance(dim2, int):
                u = np.linspace(0.0,  1.0,  dim1)
            elif isinstance(dim2, np.ndarray):
                u = dim1
            else:
                u = np.asarray([dim1])

            if dim2 == None:
                v = np.linspace(0.0,  scipy.constants.pi*2.0,  128)
            elif isinstance(dim2, int):
                v = np.linspace(0.0,  scipy.constants.pi*2.0,  dim2)
            elif isinstance(dim2, np.ndarray):
                v = dim2
            else:
                v = np.asarray([dim2])

            rz = np.asarray([[r, z] for r, z in self._parent.find_flux_surface(u, v[:-1])]).reshape(len(u), len(v)-1, 2)
            r = np.hstack([rz[:, :, 0], rz[:, :1, 0]])
            z = np.hstack([rz[:, :, 1], rz[:, :1, 1]])

            return CurvilinearMesh([r, z], [u, v], cycle=[False, True])

        @property
        def r(self):
            return self.mesh.xy[0]

        @property
        def z(self):
            return self.mesh.xy[1]

        @cached_property
        def jacobian(self):
            return self.r/self.norm_grad_psi

        @property
        def psi_norm(self):
            return self.mesh.uv[0]

        @cached_property
        def psi(self):
            return self.psi_norm * (self.psi_boundary-self.psi_axis) + self.psi_axis

        @cached_property
        def grad_psi(self):
            return self._parent.psirz(self.r, self.z, dx=1), self._parent.psirz(self.r, self.z, dy=1)

        @cached_property
        def norm_grad_psi(self):
            r"""
                .. math:: V^{\prime} =   R / |\nabla \psi|
            """
            grad_psi_r, grad_psi_z = self.grad_psi
            return np.sqrt(grad_psi_r**2+grad_psi_z**2)

        @cached_property
        def dl(self):
            return np.asarray([self.mesh.axis(idx, axis=0).geo_object.dl(self.mesh.uv[1]) for idx in range(self.mesh.shape[0])])

        def _surface_integral(self, J, *args, **kwargs):
            r"""
                .. math:: \left\langle \alpha\right\rangle \equiv\frac{2\pi}{V^{\prime}}\oint\alpha\frac{Rdl}{\left|\nabla\psi\right|}
            """
            if J is None:
                J = self.jacobian
            else:
                J = J*self.jacobian

            return np.sum(0.5*(np.roll(J, 1, axis=1)+J) * self.dl, axis=1)

        def surface_average(self,  *args, **kwargs):
            return self._surface_integral(*args, **kwargs) / self.vprime * (2*scipy.constants.pi)

        @cached_property
        def vprime(self):
            r"""
                .. math:: V^{\prime} =  2 \pi  \int{ R / |\nabla \psi| * dl }
                .. math:: V^{\prime}(psi)= 2 \pi  \int{ dl * R / |\nabla \psi|}
            """
            return self._surface_integral() * (2*scipy.constants.pi)

        @cached_property
        def B2(self):
            return (self.norm_grad_psi**2) + self.fpol.reshape(list(self.drho_tor_dpsi.shape)+[1]) ** 2/(self.r**2)

    class Constraints(PhysicalGraph):
        def __init__(self, *args,  **kwargs):
            super().__init__(*args, **kwargs)

    class GlobalQuantities(PhysicalGraph):
        def __init__(self,  *args,  **kwargs):
            super().__init__(*args, **kwargs)

        @property
        def beta_pol(self):
            """Poloidal beta. Defined as betap = 4 int(p dV) / [R_0 * mu_0 * Ip^2]  [-]"""
            return NotImplemented

        @property
        def beta_tor(self):
            """Toroidal beta, defined as the volume-averaged total perpendicular pressure divided by (B0^2/(2*mu0)), i.e. beta_toroidal = 2 mu0 int(p dV) / V / B0^2  [-]"""
            return NotImplemented

        @property
        def beta_normal(self):
            """Normalised toroidal beta, defined as 100 * beta_tor * a[m] * B0 [T] / ip [MA]  [-]"""
            return NotImplemented

        @property
        def ip(self):
            """Plasma current (toroidal component). Positive sign means anti-clockwise when viewed from above.  [A]."""
            return NotImplemented

        @property
        def li_3(self):
            """Internal inductance  [-]"""
            return NotImplemented

        @property
        def volume(self):
            """Total plasma volume  [m^3]"""
            return NotImplemented

        @property
        def area(self):
            """Area of the LCFS poloidal cross section  [m^2]"""
            return NotImplemented

        @property
        def surface(self):
            """Surface area of the toroidal flux surface  [m^2]"""
            return NotImplemented

        @property
        def length_pol(self):
            """Poloidal length of the magnetic surface  [m]"""
            return NotImplemented

        @property
        def magnetic_axis(self):
            """Magnetic axis position and toroidal field	structure"""
            return PhysicalGraph({"r":  self["magnetic_axis.r"],
                                  "z":  self["magnetic_axis.z"],
                                  # self.profiles_2d.b_field_tor(opt[0][0], opt[0][1])
                                  "b_field_tor": self["magnetic_axis.b_field_tor"]
                                  })

        @cached_property
        def x_points(self):
            _, x = self._parent.critical_points
            return x

        @cached_property
        def psi_axis(self):
            """Poloidal flux at the magnetic axis  [Wb]."""
            o, _ = self._parent.critical_points
            return o[0].psi

        @cached_property
        def psi_boundary(self):
            """Poloidal flux at the selected plasma boundary  [Wb]."""
            _, x = self._parent.critical_points
            if len(x) > 0:
                return x[0].psi
            else:
                raise ValueError(f"No x-point")

        @cached_property
        def cocos_flag(self):
            return 1.0 if self.psi_boundary > self.psi_axis else -1.0

        @property
        def q_axis(self):
            """q at the magnetic axis  [-]."""
            return NotImplemented

        @property
        def q_95(self):
            """q at the 95% poloidal flux surface
            (IMAS uses COCOS=11: only positive when toroidal current
            and magnetic field are in same direction)  [-]."""
            return NotImplemented

        @property
        def q_min(self):
            """Minimum q value and position structure"""
            return NotImplemented

        @property
        def energy_mhd(self):
            """Plasma energy content: 3/2 * int(p, dV) with p being the total pressure(thermal + fast particles)[J].  Time-dependent  Scalar [J]"""
            return NotImplemented

    class Profiles1D(PhysicalGraph):
        """Equilibrium profiles (1D radial grid) as a function of the poloidal flux	"""

        def __init__(self, *args,  **kwargs):
            super().__init__(*args, **kwargs)
            self._psi_norm = self._parent.coordinate_system.mesh.uv[0]
            # self._ffprime = self["f_df_dpsi"]
            d = self["f_df_dpsi"]
            d = Function(np.linspace(0, 1.0, len(d)), d)

            if isinstance(d, Function):
                res = Function(self.psi_norm, d(self.psi_norm))
            elif isinstance(d, np.ndarray) and len(d) == len(self.psi_norm):
                res = Function(self.psi_norm, d)
            else:
                raise TypeError(type(d))
            self._ffprime = res
            self._fvac = self._parent.vacuum_toroidal_field.r0*self._parent.vacuum_toroidal_field.b0

        @property
        def psi_norm(self):
            """Normalized poloidal flux  [Wb]. """
            return self._psi_norm

        @cached_property
        def psi(self):
            """Poloidal flux  [Wb]. """
            return self._psi_norm * (self._parent.global_quantities.psi_axis - self._parent.global_quantities.psi_boundary) + self._parent.global_quantities.psi_axis

        # @cached_property
        # def phi(self):
        #     """Toroidal flux  [Wb] """
        #     return self._parent.coordinate_system.phi

        @cached_property
        def vprime(self):
            r"""
                .. math:: V^{\prime} =  2 \pi  \int{ R / |\nabla \psi| * dl }
                .. math:: V^{\prime}(psi)= 2 \pi  \int{ dl * R / |\nabla \psi|}
            """
            return self._coord.surface_integral() * (2*scipy.constants.pi)

        @cached_property
        def dvolume_dpsi(self):
            r"""
                Radial derivative of the volume enclosed in the flux surface with respect to Psi[m ^ 3.Wb ^ -1].
            """
            return self.vprime*self.cocos_flag

        @cached_property
        def volume(self):
            """Volume enclosed in the flux surface[m ^ 3]"""
            return self.vprime.antiderivative

        @cached_property
        def ffprime(self):
            """	Derivative of F w.r.t. Psi, multiplied with F  [T^2.m^2/Wb]. """
            return self._ffprime

        @property
        def f_df_dpsi(self):
            """	Derivative of F w.r.t. Psi, multiplied with F  [T^2.m^2/Wb]. """
            return self._ffprime

        @cached_property
        def fpol(self):
            """Diamagnetic function (F=R B_Phi)  [T.m]."""
            psi_axis = self._parent.global_quantities.psi_axis
            psi_boundary = self._parent.global_quantities.psi_boundary
            f2 = self.ffprime.antiderivative
            f2 *= (2.0*(psi_boundary-psi_axis))

            f2 += self._fvac**2
            return np.sqrt(f2)

        @property
        def f(self):
            """Diamagnetic function (F=R B_Phi)  [T.m]."""
            return self.fpol

        @cached_property
        def q(self):
            r"""
                Safety factor
                (IMAS uses COCOS=11: only positive when toroidal current and magnetic field are in same direction)  [-].
                .. math:: q(\psi)=\frac{d\Phi}{d\psi}=\frac{FV^{\prime}\left\langle R^{-2}\right\rangle }{4\pi^{2}}
            """
            return self.surface_average(1.0/(self.R**2)) * self.fpol * self.vprime / (scipy.constants.pi*2)**2

        @cached_property
        def dvolume_drho_tor(self)	:
            """Radial derivative of the volume enclosed in the flux surface with respect to Rho_Tor[m ^ 2]"""
            return self.dvolume_dpsi * self.dpsi_drho_tor

        @cached_property
        def dvolume_dpsi_norm(self):
            """Radial derivative of the volume enclosed in the flux surface with respect to Psi[m ^ 3.Wb ^ -1]. """
            return NotImplemented

        @cached_property
        def phi(self):
            r"""
                Note:
                    !!! COORDINATE　DEPENDENT!!!

                .. math ::
                    \Phi_{tor}\left(\psi\right)=\int_{0}^{\psi}qd\psi
            """
            return self.q.antiderivative

        @cached_property
        def rho_tor(self):
            """Toroidal flux coordinate. The toroidal field used in its definition is indicated under vacuum_toroidal_field/b0  [m]"""
            return np.sqrt(self.phi/(scipy.constants.pi * self.b0))

        @cached_property
        def rho_tor_norm(self):
            return self.rho_tor/self.rho_tor[-1]

        @cached_property
        def drho_tor_dpsi(self)	:
            r"""
                .. math ::

                    \frac{d\rho_{tor}}{d\psi}=\frac{d}{d\psi}\sqrt{\frac{\Phi_{tor}}{\pi B_{0}}} \
                                            =\frac{1}{2\sqrt{\pi B_{0}\Phi_{tor}}}\frac{d\Phi_{tor}}{d\psi} \
                                            =\frac{q}{2\pi B_{0}\rho_{tor}}

            """
            return self.q/(2.0*scipy.constants.pi*self.b0)

        @cached_property
        def dpsi_drho_tor(self)	:
            """
                Derivative of Psi with respect to Rho_Tor[Wb/m].

                Todo:
                    FIXME: dpsi_drho_tor(0) = ???
            """
            return (2.0*scipy.constants.pi*self.b0)*self.rho_tor/self.q

        @cached_property
        def gm1(self):
            r"""
                Flux surface averaged 1/R ^ 2  [m ^ -2]
                .. math:: \left\langle\frac{1}{R^{2}}\right\rangle
            """
            return self.surface_average(1.0/(self.R**2))

        @cached_property
        def gm2(self):
            r"""
                Flux surface averaged .. math:: \left | \nabla \rho_{tor}\right|^2/R^2  [m^-2]
                .. math:: \left\langle\left|\frac{\nabla\rho}{R}\right|^{2}\right\rangle
            """
            return self.surface_average((self.norm_grad_rho_tor/self.R)**2)

        @cached_property
        def gm3(self):
            r"""
                Flux surface averaged .. math:: \left | \nabla \rho_{tor}\right|^2  [-]
                .. math:: {\left\langle \left|\nabla\rho\right|^{2}\right\rangle}
            """
            return self.surface_average(self.norm_grad_rho_tor**2)

        @cached_property
        def gm4(self):
            r"""
                Flux surface averaged 1/B ^ 2  [T ^ -2]
                .. math:: \left\langle \frac{1}{B^{2}}\right\rangle
            """
            return self.surface_average(1.0/self.B2)

        @cached_property
        def gm5(self):
            r"""
                Flux surface averaged B ^ 2  [T ^ 2]
                .. math:: \left\langle B^{2}\right\rangle
            """
            return self.surface_average(self.B2)

        @cached_property
        def gm6(self):
            r"""
                Flux surface averaged  .. math:: \left | \nabla \rho_{tor}\right|^2/B^2  [T^-2]
                .. math:: \left\langle \frac{\left|\nabla\rho\right|^{2}}{B^{2}}\right\rangle
            """
            return self.surface_average(self.norm_grad_rho_tor**2/self.B2)

        @cached_property
        def gm7(self):
            r"""
                Flux surface averaged .. math: : \left | \nabla \rho_{tor}\right |  [-]
                .. math:: \left\langle \left|\nabla\rho\right|\right\rangle
            """
            return self.surface_average(self.norm_grad_rho_tor)

        @cached_property
        def gm8(self):
            r"""
                Flux surface averaged R[m]
                .. math:: \left\langle R\right\rangle
            """
            return self.surface_average(self.R)

        @cached_property
        def gm9(self):
            r"""
                Flux surface averaged 1/R[m ^ -1]
                .. math:: \left\langle \frac{1}{R}\right\rangle
            """
            return self.surface_average(1.0/self.R)

        @cached_property
        def magnetic_shear(self):
            """Magnetic shear, defined as rho_tor/q . dq/drho_tor[-]	 """
            return self.rho_tor/self.q * self.q.derivative

        @cached_property
        def r_inboard(self):
            """Radial coordinate(major radius) on the inboard side of the magnetic axis[m]"""
            return NotImplemented

        @cached_property
        def r_outboard(self):
            """Radial coordinate(major radius) on the outboard side of the magnetic axis[m]"""
            return NotImplemented

        @cached_property
        def rho_volume_norm(self)	:
            """Normalised square root of enclosed volume(radial coordinate). The normalizing value is the enclosed volume at the equilibrium boundary
                (LCFS or 99.x % of the LCFS in case of a fixed boundary equilibium calculation)[-]"""
            return NotImplemented

        @cached_property
        def area(self):
            """Cross-sectional area of the flux surface[m ^ 2]"""
            return NotImplemented

        @cached_property
        def darea_dpsi(self):
            """Radial derivative of the cross-sectional area of the flux surface with respect to psi[m ^ 2.Wb ^ -1]. """
            return NotImplemented

        @cached_property
        def darea_drho_tor(self)	:
            """Radial derivative of the cross-sectional area of the flux surface with respect to rho_tor[m]"""
            return NotImplemented

        @cached_property
        def surface(self):
            """Surface area of the toroidal flux surface[m ^ 2]"""
            return NotImplemented

        @cached_property
        def trapped_fraction(self)	:
            """Trapped particle fraction[-]"""
            return NotImplemented

        @cached_property
        def b_field_max(self):
            """Maximum(modulus(B)) on the flux surface(always positive, irrespective of the sign convention for the B-field direction)[T]"""
            return NotImplemented

        @cached_property
        def beta_pol(self):
            """Poloidal beta profile. Defined as betap = 4 int(p dV) / [R_0 * mu_0 * Ip ^ 2][-]"""
            return NotImplemented

    class Profiles2D(PhysicalGraph):
        """
            Equilibrium 2D profiles in the poloidal plane.
        """

        def __init__(self,  *args, ** kwargs):
            super().__init__(*args, **kwargs)

        @property
        def grid_type(self):
            return self._parent.coordinate_system.grid_type

        @cached_property
        def grid(self):
            return self._parent.coordinate_system.grid

        @property
        def r(self):
            """Values of the major radius on the grid  [m] """
            return self._parent.coordinate_system.mesh.xy[0]

        @property
        def z(self):
            """Values of the Height on the grid  [m] """
            return self._parent.coordinate_system.mesh.xy[1]

        @cached_property
        def psi(self):
            """Values of the poloidal flux at the grid in the poloidal plane  [Wb]. """
            return self.apply_psifunc(lambda p: p, unit="Wb")

        @cached_property
        def theta(self):
            """	Values of the poloidal angle on the grid  [rad] """
            return NotImplementedError()

        @cached_property
        def phi(self):
            """	Toroidal flux  [Wb]"""
            return self.apply_psifunc("phi")

        @cached_property
        def j_tor(self):
            """	Toroidal plasma current density  [A.m^-2]"""
            return self.apply_psifunc("j_tor")

        @cached_property
        def j_parallel(self):
            """	Parallel (to magnetic field) plasma current density  [A.m^-2]"""
            return self.apply_psifunc("j_parallel")

        @cached_property
        def b_field_r(self):
            """R component of the poloidal magnetic field  [T]"""
            return self.psirz(self.r, self.z, dx=1)/(self.r*scipy.constants.pi*2.0)

        @cached_property
        def b_field_z(self):
            """Z component of the poloidal magnetic field  [T]"""
            return - self.psirz(self.r, self.z, dy=1)/(self.r*scipy.constants.pi*2.0)

        @cached_property
        def b_field_tor(self):
            """Toroidal component of the magnetic field  [T]"""
            return self.apply_psifunc("fpol")/self.r

        def apply_psifunc(self, func, *args, **kwargs):
            if isinstance(func, str):
                func = self._parent.profiles_1d.interpolate(func)

            NX = self.grid.dim1.shape[0]
            NY = self.grid.dim2.shape[0]

            res = np.full([NX, NY], np.nan)

            for i in range(NX):
                for j in range(NY):
                    res[i, j] = func(self.psirz(self.r[i, j], self.z[i, j]))
            return res

    class Boundary(PhysicalGraph):
        def __init__(self, *args, ntheta=129, ** kwargs):
            super().__init__(*args, **kwargs)
            self._ntheta = ntheta

        @cached_property
        def type(self):
            """0 (limiter) or 1 (diverted)  """
            return 1

        @cached_property
        def outline(self):
            """RZ outline of the plasma boundary  """
            RZ = np.asarray([[r, z] for r, z in self._parent.find_flux_surface(1.0)])
            return PhysicalGraph({"r": RZ[:, 0], "z": RZ[:, 1]})

        @cached_property
        def x_point(self):
            _, xpt = self._parent.critical_points
            return xpt

        @cached_property
        def psi(self):
            """Value of the poloidal flux at which the boundary is taken  [Wb]"""
            return self._parent.psi_boundary

        @cached_property
        def psi_norm(self):
            """Value of the normalised poloidal flux at which the boundary is taken (typically 99.x %),
                the flux being normalised to its value at the separatrix """
            return self.psi*0.99

        @cached_property
        def geometric_axis(self):
            """RZ position of the geometric axis (defined as (Rmin+Rmax) / 2 and (Zmin+Zmax) / 2 of the boundary)"""
            return PhysicalGraph(
                {
                    "r": (min(self.outline.r)+max(self.outline.r))/2,
                    "z": (min(self.outline.z)+max(self.outline.z))/2
                })

        @cached_property
        def minor_radius(self):
            """Minor radius of the plasma boundary(defined as (Rmax-Rmin) / 2 of the boundary) [m]	"""
            return (max(self.outline.r)-min(self.outline.r))*0.5

        @cached_property
        def elongation(self):
            """Elongation of the plasma boundary Click here for further documentation. [-]	"""
            return (max(self.outline.z)-min(self.outline.z))/(max(self.outline.r)-min(self.outline.r))

        @cached_property
        def elongation_upper(self):
            """Elongation(upper half w.r.t. geometric axis) of the plasma boundary Click here for further documentation. [-]	"""
            return (max(self.outline.z)-self.geometric_axis.z)/(max(self.outline.r)-min(self.outline.r))

        @cached_property
        def elongation_lower(self):
            """Elongation(lower half w.r.t. geometric axis) of the plasma boundary Click here for further documentation. [-]	"""
            return (self.geometric_axis.z-min(self.outline.z))/(max(self.outline.r)-min(self.outline.r))

        @cached_property
        def triangularity(self):
            """Triangularity of the plasma boundary Click here for further documentation. [-]	"""
            return (self.outline.r[np.argmax(self.outline.z)]-self.outline.r[np.argmin(self.outline.z)])/self.minor_radius

        @cached_property
        def triangularity_upper(self):
            """Upper triangularity of the plasma boundary Click here for further documentation. [-]	"""
            return (self.geometric_axis.r - self.outline.r[np.argmax(self.outline.z)])/self.minor_radius

        @cached_property
        def triangularity_lower(self):
            """Lower triangularity of the plasma boundary Click here for further documentation. [-]"""
            return (self.geometric_axis.r - self.outline.r[np.argmin(self.outline.z)])/self.minor_radius

        @cached_property
        def strike_point(self)	:
            """Array of strike points, for each of them the RZ position is given	struct_array [max_size=unbounded]	1- 1...N"""
            return NotImplemented

        @cached_property
        def active_limiter_point(self):
            """	RZ position of the active limiter point (point of the plasma boundary in contact with the limiter)"""
            return NotImplemented

    class BoundarySeparatrix(PhysicalGraph):
        def __init__(self, *args,  ** kwargs):
            super().__init__(*args, **kwargs)

    ####################################################################################
    # Plot proflies
    def plot(self, axis=None, *args, profiles=[], vec_field=[], mesh=True, boundary=True, levels=32, oxpoints=True,   **kwargs):
        """learn from freegs
        """
        if axis is None:
            axis = plt.gca()

        # R = self.profiles_2d.r
        # Z = self.profiles_2d.z
        # psi = self.profiles_2d.psi(R, Z)

        # axis.contour(R[1:-1, 1:-1], Z[1:-1, 1:-1], psi[1:-1, 1:-1], levels=levels, linewidths=0.2)

        if oxpoints is not False:
            o_point, x_point = self.critical_points
            axis.plot(o_point[0].r,
                      o_point[0].z,
                      'g.',
                      linewidth=0.5,
                      markersize=2,
                      label="Magnetic axis")

            if len(x_point) > 0:
                for idx, p in enumerate(x_point):
                    axis.plot(p.r, p.z, 'rx')
                    axis.text(p.r, p.z, idx,
                              horizontalalignment='center',
                              verticalalignment='center')

                axis.plot([], [], 'rx', label="X-Point")

        if boundary is not False:
            boundary_points = np.vstack([self.boundary.outline.r,
                                         self.boundary.outline.z]).T

            axis.add_patch(plt.Polygon(boundary_points, color='r', linestyle='dashed',
                                       linewidth=0.5, fill=False, closed=True))
            axis.plot([], [], 'r--', label="Separatrix")

        if mesh is not False:
            for idx in range(0, self.coordinate_system.mesh.shape[0], 4):
                ax0 = self.coordinate_system.mesh.axis(idx, axis=0)
                axis.add_patch(plt.Polygon(ax0.xy.T, fill=False, closed=True, color="b", linewidth=0.2))

            for idx in range(0, self.coordinate_system.mesh.shape[1], 4):
                ax1 = self.coordinate_system.mesh.axis(idx, axis=1)
                axis.plot(ax1.xy[0], ax1.xy[1],  "r", linewidth=0.2)

        # for k, opts in profiles:
        #     d = self.profiles_2d[k]
        #     if d is not NotImplemented and d is not None:
        #         axis.contourf(R[1:-1, 1:-1], Z[1:-1, 1:-1], d[1:-1, 1:-1], **opts)

        for u, v, opts in vec_field:
            uf = self.profiles_2d[u]
            vf = self.profiles_2d[v]
            axis.streamplot(self.profiles_2d.grid.dim1[1:-1],
                            self.profiles_2d.grid.dim2[1:-1],
                            vf[1:-1, 1:-1].transpose(1, 0),
                            uf[1:-1, 1:-1].transpose(1, 0), **opts)

        return axis

    def fetch_profile(self, d):
        if isinstance(d, str):
            data = d
            opts = {"label": d}
        elif isinstance(d, collections.abc.Mapping):
            data = d.get("name", None)
            opts = d.get("opts", {})
        elif isinstance(d, tuple):
            data, opts = d
        elif isinstance(d, PhysicalGraph):
            data = d.data
            opts = d.opts
        else:
            raise TypeError(f"Illegal profile type! {d}")

        if isinstance(opts, str):
            opts = {"label": opts}

        if isinstance(data, str):
            nlist = data.split(".")
            if len(nlist) == 1:
                data = self.profiles_1d[nlist[0]]
            elif nlist[0] == 'cache':
                data = self.profiles_1d[nlist[1:]]
            else:
                data = self.profiles_1d[nlist]
        elif isinstance(data, list):
            data = np.array(data)
        elif isinstance(d, np.ndarray):
            pass
        else:
            raise TypeError(f"Illegal data type! {type(data)}")

        return data, opts

    def plot_profiles(self, fig_axis, axis, profiles):
        if not isinstance(profiles, list):
            profiles = [profiles]

        for idx, data in enumerate(profiles):
            ylabel = None
            opts = {}
            if isinstance(data, tuple):
                data, ylabel = data
            if isinstance(data, str):
                ylabel = data

            if not isinstance(data, list):
                data = [data]

            for d in data:
                value, opts = self.fetch_profile(d)

                if value is not NotImplemented and value is not None and len(value) > 0:
                    fig_axis[idx].plot(axis.data, value, **opts)
                else:
                    logger.error(f"Can not find profile '{d}'")

            fig_axis[idx].legend(fontsize=6)

            if ylabel:
                fig_axis[idx].set_ylabel(ylabel, fontsize=6).set_rotation(0)
            fig_axis[idx].labelsize = "media"
            fig_axis[idx].tick_params(labelsize=6)
        return fig_axis[-1]

    def plot_full(self, *args,
                  axis=("psi_norm",   r'$(\psi-\psi_{axis})/(\psi_{boundary}-\psi_{axis}) [-]$'),
                  profiles=None,
                  profiles_2d=[],
                  vec_field=[],
                  surface_mesh=False,
                  **kwargs):

        axis, axis_opts = self.fetch_profile(axis)

        assert (axis.data is not NotImplemented)
        nprofiles = len(profiles) if profiles is not None else 0
        if profiles is None or nprofiles <= 1:
            fig, ax_right = plt.subplots(ncols=1, nrows=1, sharex=True)
        else:
            fig, axs = plt.subplots(ncols=2, nrows=nprofiles, sharex=True)
            # left
            ax_left = self.plot_profiles(axs[:, 0], axis, profiles)

            ax_left.set_xlabel(axis_opts.get("label", "[-]"), fontsize=6)

            # right
            gs = axs[0, 1].get_gridspec()
            for ax in axs[:, 1]:
                ax.remove()  # remove the underlying axes
            ax_right = fig.add_subplot(gs[:, 1])

        if surface_mesh:
            self.coordinate_system.plot(ax_right)
        self.plot(ax_right, profiles=profiles_2d, vec_field=vec_field, **kwargs.get("equilibrium", {}))

        self._tokamak.plot_machine(ax_right, **kwargs.get("machine", {}))

        ax_right.legend()
        fig.tight_layout()

        fig.subplots_adjust(hspace=0)
        fig.align_ylabels()

        return fig

    # # Poloidal beta. Defined as betap = 4 int(p dV) / [R_0 * mu_0 * Ip^2]  [-]
    # self.global_quantities.beta_pol = NotImplemented
    # # Toroidal beta, defined as the volume-averaged total perpendicular pressure divided by (B0^2/(2*mu0)), i.e. beta_toroidal = 2 mu0 int(p dV) / V / B0^2  [-]
    # self.global_quantities.beta_tor = NotImplemented
    # # Normalised toroidal beta, defined as 100 * beta_tor * a[m] * B0 [T] / ip [MA]  [-]
    # self.global_quantities.beta_normal = NotImplemented
    # # Plasma current (toroidal component). Positive sign means anti-clockwise when viewed from above.  [A].
    # self.global_quantities.ip = NotImplemented
    # # Internal inductance  [-]
    # self.global_quantities.li_3 = NotImplemented
    # # Total plasma volume  [m^3]
    # self.global_quantities.volume = NotImplemented
    # # Area of the LCFS poloidal cross section  [m^2]
    # self.global_quantities.area = NotImplemented
    # # Surface area of the toroidal flux surface  [m^2]
    # self.global_quantities.surface = NotImplemented
    # # Poloidal length of the magnetic surface  [m]
    # self.global_quantities.length_pol = NotImplemented
    # # Poloidal flux at the magnetic axis  [Wb].
    # self.global_quantities.psi_axis = NotImplemented
    # # Poloidal flux at the selected plasma boundary  [Wb].
    # self.global_quantities.psi_boundary = NotImplemented
    # # Magnetic axis position and toroidal field	structure
    # self.global_quantities.magnetic_axis = NotImplemented
    # # q at the magnetic axis  [-].
    # self.global_quantities.q_axis = NotImplemented
    # # q at the 95% poloidal flux surface (IMAS uses COCOS=11: only positive when toroidal current and magnetic field are in same direction)  [-].
    # self.global_quantities.q_95 = NotImplemented
    # # Minimum q value and position	structure
    # self.global_quantities.q_min = NotImplemented
    # # Plasma energy content = 3/2 * int(p,dV) with p being the total pressure (thermal + fast particles) [J]. Time-dependent; Scalar  [J]
    # self.global_quantities.energy_mhd = NotImplemented
