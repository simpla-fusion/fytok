import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import constants
# from spdm.numlib.smooth import rms_residual
from spdm.data.File import File
from spdm.data.Function import function_like
from spdm.utils.logger import logger
from spdm.view.plot_profiles import plot_profiles, sp_figure

from fytok.load_profiles import (load_core_profiles, load_core_source,
                                 load_core_transport, load_equilibrium)
from fytok.Tokamak import Tokamak

###################


if __name__ == "__main__":
    logger.info("====== START ========")
    output_path = pathlib.Path('/home/salmon/workspace/output')

    ###################################################################################################
    # baseline
    device_desc = File("/home/salmon/workspace/fytok_data/mapping/ITER/imas/3/static/config.xml", format="XML").read()

    ###################################################################################################
    # Initialize Tokamak

    tok = Tokamak(device_desc[{"wall", "pf_active", "tf", "magnetics"}])

    # Equilibrium
    eqdsk_file = File(
        "/home/salmon/workspace/data/15MA inductive - burn/Standard domain R-Z/High resolution - 257x513/g900003.00230_ITER_15MA_eqdsk16HR.txt", format="GEQdsk").read()

    tok["equilibrium"] = eqdsk_file

    tok["equilibrium"]["code"] = {"name": "dummy",
                                  "parameters": {
                                      "boundary": {"psi_norm": 0.995},
                                      "coordinate_system": {"psi_norm": np.linspace(0.001, 0.995, 64), "theta": 64}}
                                  }

    if True:
        sp_figure(tok,
                  wall={"limiter": {"edgecolor": "green"},
                        "vessel": {"edgecolor": "blue"}},
                  pf_active={"facecolor": 'red'},
                  equilibrium={
                      "contour": [0, 2],
                      "boundary": True,
                      "separatrix": True,
                  }
                  ) .savefig(output_path/"tokamak.svg", transparent=True)
