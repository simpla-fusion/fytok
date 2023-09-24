import os
import pathlib

from fytok.Tokamak import Tokamak
from spdm.view.View import display

WORKSPACE = "/home/salmon/workspace"  # "/ssd01/salmon_work/workspace/"

os.environ["SP_DATA_MAPPING_PATH"] = f"{WORKSPACE}/fytok_data/mapping"

if __name__ == "__main__":

    output_path = pathlib.Path(f"{WORKSPACE}/output")

    tok = Tokamak(f"EAST+MDSplus://{WORKSPACE}/fytok_data/mdsplus/~t/?enable=efit_east&shot=70754")

    tok.refresh(time=5.0)

    display(tok, output=output_path/f"{tok.device}_rz.svg")

    display(tok,  output=output_path/f"{tok.device}_top.svg", view="TOP")
