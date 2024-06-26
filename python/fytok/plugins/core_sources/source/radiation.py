import scipy.constants
from spdm.core.Expression import zero
from spdm.core.sp_property import sp_tree
from spdm.utils.tags import _not_found_
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

        if ne is _not_found_ or Te is _not_found_:
            raise RuntimeError(f"{ne} {Te}")

        Qrad = sum(
            [
                ne * ion.density * amns[ion.label].radiation(Te)
                for ion in profiles_1d.ion
                if ion.density is not _not_found_
            ],
            zero,
        )

        source_1d.electrons.energy -= Qrad

        return current


CoreSources.Source.register(["radiation"], Radiation)
