import pathlib
import os
import numpy as np
from spdm.data.File import File
from spdm.view.View import display
from spdm.utils.logger import logger
from fytok.modules.Equilibrium import Equilibrium
from fytok.Tokamak import Tokamak

DATA_PATH = "/home/salmon/workspace/fytok_data"

# GACODE_PATH=os.environ['GACODE_PATH']
# SP_OUTPUT=os.environ['SP_OUTPUT']

if __name__ == "__main__":

    # output_path = pathlib.Path(SP_OUTPUT)

     eq = Equilibrium("GEQdsk:///home/salmon/workspace/gacode/neo/tools/input/profile_data/g141459.03890")


    # display(eq, title=f"EQUILIBRIUM", output=output_path/"EQUILIBRIUM.svg")

    tok = Tokamak(f"file+MDSplus[EAST]://{DATA_PATH}/mdsplus/~t/?tree_name=efit_east#70745")

    logger.debug(tok.pf_active.coil[1].current(1.2))

    logger.info("Done")
