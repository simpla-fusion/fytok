import typing

from fytok._imas.lastest.wall import _T_wall

from spdm.geometry.GeoObject import GeoObject
from spdm.geometry.Polyline import Polyline
from spdm.utils.logger import logger


class Wall(_T_wall):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __geometry__(self, view="RZ", **kwargs) -> GeoObject | typing.List[GeoObject]:
        if view != "RZ":
            return None
        desc = self.description_2d[0]  # 0 for equilibrium codes
        return {  # geo
            "limiter": Polyline(desc.limiter.unit[0].outline.r,
                                desc.limiter.unit[0].outline.z),

            "vessel_inner": Polyline(desc.vessel.unit[0].annular.outline_inner.r,
                                     desc.vessel.unit[0].annular.outline_inner.z),

            "vessel_outer": Polyline(desc.vessel.unit[0].annular.outline_outer.r,
                                     desc.vessel.unit[0].annular.outline_outer.z)
        }, {  # styles
            "limiter": {"$matplotlib": {"edgecolor": "green"}},
            "vessel_inner": {"$matplotlib": {"edgecolor": "blue"}},
            "vessel_outer": {"$matplotlib": {"edgecolor": "blue"}}

        },
