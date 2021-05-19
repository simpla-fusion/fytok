import collections
from dataclasses import dataclass
from functools import cached_property
from typing import Sequence, Union

import matplotlib.pyplot as plt
import numpy as np
import scipy
import scipy.integrate
from numpy import arctan2, cos, sin, sqrt
from scipy.optimize import fsolve, root_scalar
from spdm.data.AttributeTree import AttributeTree, as_attribute_tree
from spdm.data.Field import Field
from spdm.data.Function import Function
from spdm.data.Node import Dict, List
from spdm.data.Profiles import Profiles
from spdm.data.TimeSeries import TimeSeries, TimeSlice
from spdm.geometry.CubicSplineCurve import CubicSplineCurve
from spdm.geometry.Curve import Curve
from spdm.geometry.Point import Point
from spdm.mesh.CurvilinearMesh import CurvilinearMesh
from spdm.util.logger import logger
from spdm.util.utilities import convert_to_named_tuple, try_get

from ..common.GGD import GGD
from ..common.IDS import IDS
from ..common.Misc import Identifier, RZTuple, VacuumToroidalField

TOLERANCE = 1.0e-6
EPS = np.finfo(float).eps

TWOPI = 2.0*scipy.constants.pi


class MagneticCoordSystem(Dict):
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

    def __init__(self, *args,
                 vacuum_toroidal_field: VacuumToroidalField = None,
                 psirz: Field = None,
                 ffprime: Function = None,
                 pprime: Function = None,
                 **kwargs):
        """
            Initialize FluxSurface
        """
        super().__init__(*args, **kwargs)
        self._vacuum_toroidal_field = vacuum_toroidal_field
        self._fvac = abs(self._vacuum_toroidal_field.r0*self._vacuum_toroidal_field.b0)

        self._psirz = psirz
        self._ffprime = ffprime
        self._pprime = pprime

        dim1 = self["grid.dim1"]
        dim2 = self["grid.dim2"]

        if isinstance(dim1, np.ndarray):
            u = dim1
        elif dim1 == None:
            u = np.linspace(0.0001,  0.99,  len(self._ffprime))
        elif isinstance(dim2, int):
            u = np.linspace(0.0001,  0.99,  dim1)
        elif isinstance(dim2, np.ndarray):
            u = dim1
        else:
            u = np.asarray([dim1])

        if isinstance(dim2, np.ndarray):
            v = dim2
        elif dim2 == None:
            v = np.linspace(0.0,  1.0,  128)
        elif isinstance(dim2, int):
            v = np.linspace(0.0, 1.0,  dim2)
        elif isinstance(dim2, np.ndarray):
            v = dim2
        else:
            v = np.asarray([dim2])

        self._uv = [u, v]

    @property
    def vacuum_toroidal_field(self) -> VacuumToroidalField:
        return self._vacuum_toroidal_field

    def radial_grid(self, primary_axis=None, axis=None):
        """
            Radial grid
        """
        psi_norm = self.psi_norm

        if primary_axis == "psi_norm" or primary_axis is None:
            if axis is not None:
                psi_norm = axis
        else:
            p_axis = try_get(self, primary_axis)
            if isinstance(p_axis, Function):
                p_axis = p_axis.__array__()
            if not isinstance(p_axis, np.ndarray):
                raise NotImplementedError(primary_axis)
            psi_norm = Function(p_axis, psi_norm)(np.linspace(p_axis[0], p_axis[-1], p_axis.shape[0]))
        return RadialGrid(self, psi_norm)

    @cached_property
    def grid_type(self):
        return Identifier(**self["grid_type"]._as_dict())

    @cached_property
    def critical_points(self):
        opoints = []
        xpoints = []
        OXPoint = collections.namedtuple('OXPoint', "r z psi")
        for r, z, psi, D in self._psirz.find_peak():
            p = OXPoint(r, z, psi)

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

            bbox = self._psirz.coordinates.mesh.bbox
            Rmid = (bbox[0][0] + bbox[0][1])/2.0
            Zmid = (bbox[1][0] + bbox[1][1])/2.0

            opoints.sort(key=lambda x: (x.r - Rmid)**2 + (x.z - Zmid)**2)

            psi_axis = opoints[0].psi

            xpoints.sort(key=lambda x: (x.psi - psi_axis)**2)

        return opoints, xpoints

    def flux_surface_map(self, u, v=None):
        o_points, x_points = self.critical_points

        if len(o_points) == 0:
            raise RuntimeError(f"Can not find o-point!")
        else:
            R0 = o_points[0].r
            Z0 = o_points[0].z
            psi0 = o_points[0].psi

        if len(x_points) == 0:
            R1 = self.psirz.coordinates.bbox[1][0]
            Z1 = Z0
            psi1 = 0.0
            theta0 = 0
        else:
            R1 = x_points[0].r
            Z1 = x_points[0].z
            psi1 = x_points[0].psi
            theta0 = arctan2(Z1 - Z0, R1 - R0)
        Rm = sqrt((R1-R0)**2+(Z1-Z0)**2)

        if not isinstance(u, (np.ndarray, collections.abc.MutableSequence)):
            u = [u]
        u = np.asarray(u)
        if v is None:
            v = self._uv[1]
        elif not isinstance(v, (np.ndarray, collections.abc.MutableSequence)):
            v = np.asarray([v])

        theta = v*TWOPI  # +theta0
        psi = u*(psi1-psi0)+psi0

        for psi_val in psi:
            for theta_val in theta:
                r0 = R0
                z0 = Z0
                r1 = R0+Rm * cos(theta_val)
                z1 = Z0+Rm * sin(theta_val)

                if not np.isclose(self.psirz(r1, z1), psi_val):
                    try:
                        def func(r): return float(self.psirz((1.0-r)*r0+r*r1, (1.0-r)*z0+r*z1)) - psi_val
                        sol = root_scalar(func,  bracket=[0, 1], method='brentq')
                    except ValueError as error:
                        raise ValueError(f"Find root fialed! {error} {psi_val}")

                    if not sol.converged:
                        raise ValueError(f"Find root fialed!")

                    r1 = (1.0-sol.root)*r0+sol.root*r1
                    z1 = (1.0-sol.root)*z0+sol.root*z1

                yield r1, z1

    def create_mesh(self, u, v, *args, type_index=None):
        logger.debug(f"create mesh! type index={type_index} START")

        type_index = type_index or self.grid_type.index
        if type_index == 13:
            rz = np.asarray([[r, z] for r, z in self.flux_surface_map(u, v[:-1])]).reshape(len(u), len(v)-1, 2)
            rz = np.hstack((rz, rz[:, :1, :]))
            mesh = CurvilinearMesh(rz, [u, v], cycle=[False, True])
        else:
            raise NotImplementedError(f"TODO: reconstruct mesh {type_index}")
        logger.debug(f"create mesh! type index={type_index} DONE")

        return mesh

    def create_surface(self, psi_norm, v=None):
        if isinstance(psi_norm, CubicSplineCurve):
            return psi_norm
        elif psi_norm is None:
            return [self.create_surface(p) for p in self.psi_norm]
        elif isinstance(psi_norm, collections.abc.MutableSequence):
            return [self.create_surface(p) for p in psi_norm]
        elif isinstance(psi_norm, int):
            psi_norm = self.psi_norm[psi_norm]

        if np.abs(psi_norm) <= EPS:
            o, _ = self.critical_points
            return Point(*o)
        if v is None:
            v = self._uv[1]
        else:
            v = np.asarray(v)

        xy = np.asarray([[r, z] for r, z in self.flux_surface_map(psi_norm,  v[:-1])])
        xy = np.vstack((xy, xy[:1, :]))
        return CubicSplineCurve(v, xy, is_closed=True)

    @cached_property
    def surface_mesh(self):
        return self.create_surface(*self._uv)

    ###############################
    # 2-D

    def br(self, r, z):
        return -self.psirz(r,  z, dy=1)/r

    def bz(self, r, z):
        return self.psirz(r, z, dx=1)/r

    def bpol(self, r, z):
        return np.sqrt(self.br(r, z)**2+self.bz(r, z)**2)

    def surface_integrate2(self, fun, *args, **kwargs):
        return np.asarray([surf.integrate(lambda r, z: fun(r, z, *args, **kwargs)/self.bpol(r, z)) * (2*scipy.constants.pi) for surf in self.surface_mesh])

    @cached_property
    def mesh(self):
        return self.create_mesh(self._uv[0],  self._uv[1], type_index=13)

    @property
    def r(self):
        return self.mesh.xy[:, :, 0]

    @property
    def z(self):
        return self.mesh.xy[:, :, 1]

    def psirz(self, r, z, *args, **kwargs):
        return self._psirz(r, z, *args, **kwargs)

    @cached_property
    def dl(self):
        return np.asarray([self.mesh.axis(idx, axis=0).geo_object.dl(self.mesh.uv[1]) for idx in range(self.mesh.shape[0])])

    @cached_property
    def Br(self):
        return -self.psirz(self.r, self.z, dy=1) / self.r

    @cached_property
    def Bz(self):
        return self.psirz(self.r, self.z, dx=1) / self.r

    @cached_property
    def Btor(self):
        return 1.0 / self.r * self.fpol.__array__().reshape(self.mesh.shape[0], 1)

    @cached_property
    def Bpol(self):
        r"""
            .. math:: B_{pol} =   R / |\nabla \psi|
        """
        return np.sqrt(self.Br**2+self.Bz**2)

    @cached_property
    def B2(self):
        return (self.Br**2+self.Bz**2 + self.Btor**2)

    @cached_property
    def grad_psi2(self):
        return self.psirz(self.r, self.z, dx=1)**2+self.psirz(self.r, self.z, dy=1)**2

    @cached_property
    def norm_grad_psi(self):
        return np.sqrt(self.grad_psi2)

    def surface_integrate(self, alpha=None, *args, **kwargs):
        r"""
            .. math:: \left\langle \alpha\right\rangle \equiv\frac{2\pi}{V^{\prime}}\oint\alpha\frac{Rdl}{\left|\nabla\psi\right|}
        """
        if alpha is None:
            alpha = 1.0/self.Bpol
        else:
            alpha = alpha/self.Bpol
        return np.sum((np.roll(alpha, 1, axis=1)+alpha) * self.dl, axis=1) * (0.5*2*scipy.constants.pi)

    def surface_average(self,  *args, **kwargs):
        return self.surface_integrate(*args, **kwargs) / self.dvolume_dpsi

    def bbox(self, s=None):
        rz = np.asarray([(s.bbox[0]+self.bbox[1])*0.5 for s in self.surface_mesh]).T

    @dataclass
    class ShapePropety:
        # RZ position of the geometric axis of the magnetic surfaces (defined as (Rmin+Rmax) / 2 and (Zmin+Zmax) / 2 of the surface)
        geometric_axis: RZTuple
        # Minor radius of the plasma boundary(defined as (Rmax-Rmin) / 2 of the boundary)[m]
        minor_radius: np.ndarray  # (rmax - rmin)*0.5,
        # Elongation of the plasma boundary. [-]
        elongation: np.ndarray  # (zmax-zmin)/(rmax-rmin),
        # Elongation(upper half w.r.t. geometric axis) of the plasma boundary. [-]
        elongation_upper: np.ndarray  # (zmax-(zmax+zmin)*0.5)/(rmax-rmin),
        # longation(lower half w.r.t. geometric axis) of the plasma boundary. [-]
        elongation_lower: np.ndarray  # ((zmax+zmin)*0.5-zmin)/(rmax-rmin),
        # Triangularity of the plasma boundary. [-]
        triangularity: np.ndarray  # (rzmax-rzmin)/(rmax - rmin)*2,
        # Upper triangularity of the plasma boundary. [-]
        triangularity_upper: np.ndarray  # ((rmax+rmin)*0.5 - rzmax)/(rmax - rmin)*2,
        # Lower triangularity of the plasma boundary. [-]
        triangularity_lower: np.ndarray  # ((rmax+rmin)*0.5 - rzmin)/(rmax - rmin)*2,
        # Radial coordinate(major radius) on the inboard side of the magnetic axis[m]
        r_inboard: np.ndarray  # r_inboard,
        # Radial coordinate(major radius) on the outboard side of the magnetic axis[m]
        r_outboard: np.ndarray  # r_outboard,

    def shape_property(self, psi=None) -> ShapePropety:
        def shape_box(s: Curve):
            r, z = s.xy()
            rmin = np.min(r)
            rmax = np.max(r)
            zmin = np.min(z)
            zmax = np.max(z)
            rzmin = r[np.argmin(z)]
            rzmax = r[np.argmax(z)]
            r_inboard = s.point(0.5)[0]
            r_outboard = s.point(0)[0]
            return rmin, zmin, rmax, zmax, rzmin, rzmax, r_inboard, r_outboard

        if psi is None:
            pass
        elif not isinstance(psi, (np.ndarray, collections.abc.MutableSequence)):
            psi = [psi]

        sbox = np.asarray([[*shape_box(s)] for s in self.create_surface(psi)])

        if sbox.shape[0] == 1:
            rmin, zmin, rmax, zmax, rzmin, rzmax, r_inboard, r_outboard = sbox[0]
        else:
            rmin, zmin, rmax, zmax, rzmin, rzmax, r_inboard, r_outboard = sbox.T

        return MagneticCoordSystem.ShapePropety(
            # RZ position of the geometric axis of the magnetic surfaces (defined as (Rmin+Rmax) / 2 and (Zmin+Zmax) / 2 of the surface)
            RZTuple((rmin+rmax)*0.5, (zmin+zmax)*0.5),
            # Minor radius of the plasma boundary(defined as (Rmax-Rmin) / 2 of the boundary)[m]
            (rmax - rmin)*0.5,  # "minor_radius":
            # Elongation of the plasma boundary. [-]
            (zmax-zmin)/(rmax-rmin),  # "elongation":
            # Elongation(upper half w.r.t. geometric axis) of the plasma boundary. [-]
            (zmax-(zmax+zmin)*0.5)/(rmax-rmin),  # "elongation_upper":
            # longation(lower half w.r.t. geometric axis) of the plasma boundary. [-]
            ((zmax+zmin)*0.5-zmin)/(rmax-rmin),  # elongation_lower":
            # Triangularity of the plasma boundary. [-]
            (rzmax-rzmin)/(rmax - rmin)*2,  # "triangularity":
            # Upper triangularity of the plasma boundary. [-]
            ((rmax+rmin)*0.5 - rzmax)/(rmax - rmin)*2,  # "triangularity_upper":
            # Lower triangularity of the plasma boundary. [-]
            ((rmax+rmin)*0.5 - rzmin)/(rmax - rmin)*2,  # "triangularity_lower":
            # Radial coordinate(major radius) on the inboard side of the magnetic axis[m]
            r_inboard,  # "r_inboard":
            # Radial coordinate(major radius) on the outboard side of the magnetic axis[m]
            r_outboard,  # "r_outboard":
        )

    ###############################
    # 0-D

    @cached_property
    def magnetic_axis(self):
        o, _ = self.critical_points
        if not o:
            raise RuntimeError(f"Can not find magnetic axis")

        return Dict({
            "r": o[0].r,
            "z": o[0].z,
            "b_field_tor": NotImplemented
        })

    @cached_property
    def boundary(self):
        return self.create_surface(1.0)

    @cached_property
    def cocos_flag(self):
        return 1.0 if self.psi_boundary > self.psi_axis else -1.0

    @cached_property
    def psi_axis(self):
        """Poloidal flux at the magnetic axis  [Wb]."""
        o, _ = self.critical_points
        return o[0].psi

    @cached_property
    def psi_boundary(self):
        """Poloidal flux at the selected plasma boundary  [Wb]."""
        _, x = self.critical_points
        if len(x) > 0:
            return x[0].psi
        else:
            raise ValueError(f"No x-point")

    ###############################
    # 1-D
    @cached_property
    def dvolume_dpsi(self):
        r"""
            .. math:: V^{\prime} =  2 \pi  \int{ R / |\nabla \psi| * dl }
            .. math:: V^{\prime}(psi)= 2 \pi  \int{ dl * R / |\nabla \psi|}
        """
        return self.surface_integrate()

    @property
    def ffprime(self):
        return Function(self.psi_norm, self._ffprime)

    @cached_property
    def fpol(self):
        """Diamagnetic function (F=R B_Phi)  [T.m]."""
        fpol2 = self._ffprime.antiderivative * (2 * (self.psi_boundary - self.psi_axis))
        return Function(self.psi_norm,   np.sqrt(fpol2 - fpol2[-1] + self._fvac**2))

    @property
    def psi_norm(self):
        return self.mesh.uv[0]

    @cached_property
    def psi(self):
        return self.psi_norm * (self.psi_boundary-self.psi_axis) + self.psi_axis

    @cached_property
    def dq_dpsi(self):
        return Function(self.psi_norm, self.fpol*self.surface_integrate(1.0/(self.r**2)) *
                        ((self.psi_boundary-self.psi_axis) / (TWOPI)))

    @cached_property
    def phi(self):
        r"""
            Note:
            .. math::
                \Phi_{tor}\left(\psi\right) =\int_{0} ^ {\psi}qd\psi
        """
        return self.dq_dpsi.antiderivative

    @cached_property
    def rho_tor(self):
        """Toroidal flux coordinate. The toroidal field used in its definition is indicated under vacuum_toroidal_field/b0[m]"""
        return np.sqrt(self.phi/(scipy.constants.pi * abs(self._vacuum_toroidal_field.b0)))

    @cached_property
    def rho_tor_norm(self):
        return np.sqrt(self.phi/self.phi[-1])


class RadialGrid:
    r"""
        Radial grid
    """

    def __init__(self,  coordinate_system: MagneticCoordSystem, psi_norm=None) -> None:

        self._coordinate_system = coordinate_system
        self._psi_axis = coordinate_system.psi_axis
        self._psi_boundary = coordinate_system.psi_boundary

        if isinstance(psi_norm, int):
            self._psi_norm = np.linspace(0, 1.0,  psi_norm)
        elif psi_norm is None:
            self._psi_norm = coordinate_system.psi_norm
        else:
            self._psi_norm = np.asarray(psi_norm)

    def __serialize__(self) -> Dict:
        return {
            "psi_norm": self.psi_norm,
            "rho_tor_norm": self.rho_tor_norm,
        }

    def pullback(self, psi_norm):
        return RadialGrid(self._coordinate_system, psi_norm)

    @property
    def vacuum_toroidal_field(self):
        return self._coordinate_system.vacuum_toroidal_field

    @cached_property
    def psi_magnetic_axis(self):
        """Poloidal flux at the magnetic axis  [Wb]."""
        return self._psi_axis

    @cached_property
    def psi_boundary(self):
        """Poloidal flux at the selected plasma boundary  [Wb]."""
        return self._psi_boundary

    @property
    def psi_norm(self):
        return self._psi_norm

    @cached_property
    def psi(self):
        """Poloidal magnetic flux {dynamic} [Wb]. This quantity is COCOS-dependent, with the following transformation"""
        return self.psi_norm * (self.psi_boundary-self.psi_magnetic_axis)+self.psi_magnetic_axis

    @cached_property
    def rho_tor_norm(self):
        r"""Normalised toroidal flux coordinate. The normalizing value for rho_tor_norm, is the toroidal flux coordinate 
            at the equilibrium boundary (LCFS or 99.x % of the LCFS in case of a fixed boundary equilibium calculation, 
            see time_slice/boundary/b_flux_pol_norm in the equilibrium IDS) {dynamic} [-]
        """
        return self._coordinate_system.rho_tor_norm(self.psi_norm)

    @cached_property
    def rho_tor(self):
        r"""Toroidal flux coordinate. rho_tor = sqrt(b_flux_tor/(pi*b0)) ~ sqrt(pi*r^2*b0/(pi*b0)) ~ r [m]. 
            The toroidal field used in its definition is indicated under vacuum_toroidal_field/b0 {dynamic} [m]"""
        return self._coordinate_system.rho_tor

    @cached_property
    def rho_pol_norm(self):
        r"""Normalised poloidal flux coordinate = sqrt((psi(rho)-psi(magnetic_axis)) / (psi(LCFS)-psi(magnetic_axis))) {dynamic} [-]"""
        return self._coordinate_system.rho_pol_norm

    @cached_property
    def area(self):
        """Cross-sectional area of the flux surface {dynamic} [m^2]"""
        return self._coordinate_system.area

    @cached_property
    def surface(self):
        """Surface area of the toroidal flux surface {dynamic} [m^2]"""
        return self._coordinate_system.surface

    @cached_property
    def volume(self):
        """Volume enclosed inside the magnetic surface {dynamic} [m^3]"""
        return self._coordinate_system.volume

    @cached_property
    def dvolume_drho_tor(self) -> Function:
        return self._coordinate_system.dvolume_drho_tor
