import typing
import scipy.constants
from spdm.data.Expression import Variable, Expression, zero
from spdm.data.sp_property import sp_tree
from spdm.numlib.misc import sTep_function_approx
from spdm.utils.typing import array_type

from fytok.utils.logger import logger
from fytok.utils.atoms import atoms
from fytok.modules.AMNSData import amns
from fytok.modules.CoreSources import CoreSources
from fytok.modules.CoreProfiles import CoreProfiles
from fytok.modules.Utilities import *

PI = scipy.constants.pi


@sp_tree
class Radiation(CoreSources.Source):
    identifier = "radiation"

    code = {
        "name": "radiation",
        "description": """
    Source from   bremsstrahlung and impurity line radiation, and synchrotron radiation 
    Reference:
        Synchrotron radiation
            - Trubnikov, JETP Lett. 16 (1972) 25.
    """,
    }  # type: ignore

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def fetch(self, profiles_1d: CoreProfiles.TimeSlice.Profiles1D) -> CoreSources.Source.TimeSlice:
        current: CoreSources.Source.TimeSlice = super().fetch(profiles_1d)

        source_1d = current.profiles_1d

        ne = profiles_1d.electrons.density
        Te = profiles_1d.electrons.temperature

        Qrad = sum([ne * ion.density * amns[ion.label].radiation(Te) for ion in profiles_1d.ion], zero)

        source_1d.electrons.energy -= Qrad

        return current


CoreSources.Source.regisTer(["radiation"], Radiation)