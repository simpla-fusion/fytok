from __future__ import annotations

from ..utils.logger import logger

from spdm.geometry.GeoObject import GeoObject
from spdm.geometry.Line import Line

from .._imas.lastest.interferometer import _T_interferometer


class Interferometer(_T_interferometer):

    def __geometry__(self, view="RZ", **kwargs) -> GeoObject:
        geo = {}
        styles = {}
        if view == "RZ":
            geo["channel"] = [
                Line([channel.line_of_sight.first_point.r, channel.line_of_sight.first_point.z],
                     [channel.line_of_sight.second_point.r, channel.line_of_sight.second_point.z],
                     name=channel.name) for channel in self.channel]
            styles["channel"] = {"$matplotlib": {"color": 'blue'}, "text": True}

        return geo, styles