import os
import pathlib

import numpy as np
from fytok.Tokamak import Tokamak
from fytok.utils.logger import logger
from spdm.data.File import File
from spdm.data.Entry import Entry, open_entry
from spdm.view.View import display

WORKSPACE = "/home/salmon/workspace"  # "/ssd01/salmon_work/workspace/"

os.environ["SP_DATA_MAPPING_PATH"] = f"{WORKSPACE}/fytok_data/mapping"

if __name__ == "__main__":

    output_path = pathlib.Path(f"{WORKSPACE}/output")

    device = "nstx"

    entry = open_entry(f"file+mhdin://{WORKSPACE}/omas/omas/machine_mappings/support_files/{device}/04202005Av1_0/mhdin.dat")

    with File(f"/home/salmon/workspace/fytok_data/mapping/{device}/imas/3/{device}.xml", mode="w", root="mapping", format="xml") as f:
        f.write(entry.dump())

    # entry = open_entry(f"file+mhdin://{WORKSPACE}/omas/omas/machine_mappings/support_files/iter/mhdin.dat")

    # with File(f"/home/salmon/workspace/fytok_data/mapping/iter_n/imas/3/iter_n.xml", mode="w", root="mapping", format="xml") as f:
    #     f.write(entry.dump())

    tok = Tokamak(device)

    display(tok, title=f"{tok.device.upper()} RZ   View ", output=output_path/f"{tok.device}_rz.svg")
    # display(tok, title=f"{tok.device.upper()} Top  View ", output=output_path/"east_top.svg", view="TOP")
