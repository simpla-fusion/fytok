import collections
from functools import cached_property

import numpy as np
import scipy.constants
from fytok.modules.transport.CoreProfiles import CoreProfiles
from fytok.modules.transport.CoreTransport import CoreTransport
from fytok.modules.transport.Equilibrium import Equilibrium
from fytok.modules.transport.MagneticCoordSystem import RadialGrid
from spdm.data.Function import Function
from spdm.data.Node import _next_
from spdm.data.TimeSeries import TimeSeries, TimeSlice
from spdm.util.logger import logger


# class NeoClassicalProfiles1D(CoreTransport.Model.TimeSlice):
#     def __init__(self, *args, grid: RadialGrid,
#                  equilibrium: Equilibrium.TimeSlice = None,
#                  core_profile: CoreProfiles.TimeSlice = None,
#                  **kwargs):
#         super().__init__(*args, grid=grid, **kwargs)


class NeoClassical(CoreTransport.Model):
    """
        Neoclassiical Transport Model
        ===============================


        References:
        =============
        - Tokamaks, Third Edition, Chapter 4 Confinement,p149,  J.A.Wesson 2003
    """

    # Profiles1D = NeoClassicalProfiles1D

    def __init__(self, d, *args, **kwargs):
        super().__init__(collections.ChainMap({
            "identifier": {
                "name": f"{self.__class__.__name__}",
                "index": 5,
                "description": f"{self.__class__.__name__}"
            }}, d or {}), *args, **kwargs)


__SP_EXPORT__ = NeoClassical
