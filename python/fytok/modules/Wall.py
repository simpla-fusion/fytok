import typing

from spdm.geometry.Circle import Circle
from spdm.geometry.GeoObject import GeoObject
from spdm.geometry.Polyline import Polyline
from spdm.utils.tags import _not_found_

from .._ontology import wall

from ..utils.logger import logger


class Wall(wall._T_wall):

    def __geometry__(self, view_point="RZ", **kwargs) -> GeoObject | typing.List[GeoObject]:

        geo = {}
        styles = {}

        desc = self.description_2d[0]  # 0 for equilibrium codes

        match view_point.lower():
            case "top":

                vessel_r = desc.vessel.unit[0].annular.outline_outer.r
                # vessel_z = desc.vessel.unit[0].annular.outline_outer.z
                geo["vessel_outer"] = [Circle(0.0, 0.0, vessel_r.min()), Circle(0.0, 0.0, vessel_r.max())]

            case "rz":
                if desc.limiter.unit[0].outline.r is not _not_found_:
                    geo["limiter"] = Polyline(desc.limiter.unit[0].outline.r,
                                              desc.limiter.unit[0].outline.z)
                units = []
                for unit in desc.vessel.unit:
                    if unit.annular is not _not_found_:
                        units.append({
                            "annular": {
                                "vessel_inner": Polyline(unit.annular.outline_inner.r,
                                                         unit.annular.outline_inner.z),

                                "vessel_outer": Polyline(unit.annular.outline_outer.r,
                                                         unit.annular.outline_outer.z),
                            }})

                    else:

                        elements = []
                        for element in unit.element:
                            elements.append(Polyline(element.outline.r,
                                                     element.outline.z,
                                                     name=element.name)
                                            )
                        units.append({"element":   elements})

                    geo["unit"] = units
        styles = {  #
            "limiter": {"$matplotlib": {"edgecolor": "green"}},
            "vessel_inner": {"$matplotlib": {"edgecolor": "blue"}},
            "vessel_outer": {"$matplotlib": {"edgecolor": "blue"}}
        }
        return geo, styles
