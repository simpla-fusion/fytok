import typing
from dataclasses import dataclass

import numpy as np
from _imas.utilities import _T_rz1d_dynamic_aos, _T_core_radial_grid, _T_rz0d_dynamic_aos
from spdm.data.Dict import Dict
from spdm.data.Entry import Entry
from spdm.data.Function import Function, function_like
from spdm.data.Node import Node
from spdm.data.sp_property import sp_property
from spdm.utils.logger import logger
_T = typing.TypeVar("_T")

RZTuple1D = _T_rz1d_dynamic_aos
RZTuple = _T_rz0d_dynamic_aos
# class RZTuple(_T_rz1d_dynamic_aos):
#     r = sp_property(type="dynamic", units="m", ndims=1, data_type=float)
#     z = sp_property(type="dynamic", units="m", ndims=1, data_type=float)
CoreRadialGrid = _T_core_radial_grid


class _CoreRadialGrid(_T_core_radial_grid):
    """ Radial grid """

    def remesh(self, label: str = "psi_norm", new_axis: np.ndarray = None, ):

        logger.warning("TODO: incorrect implement! need fix!")

        axis = self._as_child(label)

        if isinstance(axis, np.ndarray) and isinstance(new_axis, np.ndarray) \
                and axis.shape == new_axis.shape and np.allclose(axis, new_axis):
            return self

        if new_axis is None:
            new_axis = np.linspace(axis[0], axis[-1], len(axis))
        elif isinstance(new_axis, int):
            new_axis = np.linspace(0, 1.0, new_axis)
        elif not isinstance(new_axis, np.ndarray):
            raise TypeError(new_axis)

        return CoreRadialGrid(
            {
                "psi_magnetic_axis": self.psi_magnetic_axis,
                "psi_boundary":     self.psi_boundary,
                "psi":              function_like(axis,  self.psi)(new_axis) if label != "psi_norm" else new_axis,
                "rho_tor_norm":     new_axis,
                # rho_pol_norm=Function(axis,  self.rho_pol_norm)(new_axis) if label != "rho_pol_norm" else new_axis,
                # area=Function(axis,  self.area)(new_axis) if label != "area" else new_axis,
                # surface=Function(axis,  self.surface)(new_axis) if label != "surface" else new_axis,
                # volume=Function(axis,  self.volume)(new_axis) if label != "volume" else new_axis,
                "dvolume_drho_tor": function_like(axis,  self.dvolume_drho_tor)(new_axis),
            },
            parent=self._parent
        )