
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.constants
from spdm.util.logger import logger
from spdm.util.plot_profiles import plot_profiles

if __name__ == "__main__":
    profile = pd.read_csv('/home/salmon/workspace/data/15MA inductive - burn/profile.txt', sep='\t')

    plot_profiles(
        [
            [
                (profile["NE"].values,          r"$N_{e}^{\star}$"),
            ],
            [
                (profile["TE"].values,          r"$T_{e}^{\star}$"),
            ],
            [
                (profile["Jext"].values,        r"$j_{ext}^{\star}$"),
                (profile["Jnb"].values,         r"$j_{nb}^{\star}$"),
                (profile["Jrf"].values,         r"$j_{rf}^{\star}$"),
                (profile["Jext"].values
                 - profile["Jnb"].values
                 - profile["Jrf"].values,       {"color": "red", "linestyle": "dashed", "label": r"$J_{ext}-J_{nb}-J_{rf}$"}),
            ],

            [
                (profile["Jnoh"].values,        r"$j_{noh}^{\star}$"),
                (profile["Jbs"].values,         r"$j_{bootstrap}^{\star}$"),
                (profile["Jnb"].values,         r"$j_{nb}^{\star}$"),
                (profile["Jrf"].values,         r"$j_{rf}^{\star}$"),

                (profile["Jnoh"].values
                 - profile["Jbs"].values
                 - profile["Jnb"].values
                 - profile["Jrf"].values,        {"color": "red", "linestyle": "dashed", "label": r"$J_{noh}^{\star}-J_{bs}^{\star}-J_{nb}^{\star}-J_{rf}^{\star}$"}),
            ],

            [

                (profile["Jtot"].values,        r"$j_{\parallel}^{\star}$"),
                (profile["Joh"].values,         r"$j_{oh}^{\star}$"),
                (profile["Jnoh"].values,        r"$j_{noh}^{\star}$"),
                (profile["Jtot"].values
                 - profile["Jnoh"].values
                 - profile["Joh"].values,        {"color": "red", "linestyle": "dashed", "label": r"$j_{\parallel}^{\star}-j_{oh}^{\star}-j_{noh}^{\star}$"}),

            ],

            [
                (profile["Paux"].values,        r"auxilliary power density"),
                (profile["PeEX"].values,        r"RF+NB heating of electrons"),
                (profile["Pex"].values,         r"RF heating of electrons"),
                (profile["Pnbe"].values,        r"NB heating of electrons"),

                (profile["Paux"].values
                 - profile["Pex"].values
                 - profile["Pnbe"].values,        {"color": "red", "linestyle": "dashed", "label": r"rms"}),

            ],


            [
                (profile["Pdt"].values,         r"$\alpha$-heating"),
                (profile["Pdti"].values,        r"heating of ions by alphas"),
                (profile["Pdte"].values,        r"heating of elecrons by alphas"),
                (profile["Pdt"].values
                 - profile["Pdti"].values
                 - profile["Pdte"].values,     {"color": "red", "linestyle": "dashed", "label": r"rms"}),

            ],
            [
                (profile["Prad"].values,        r"total radiative loss"),
                (profile["Plin"].values,        r"Plin"),
                (profile["Psyn"].values,        r"electron synchrotoron radiaion"),
                (profile["Pbrm"].values,        r"Pbrm"),

                (profile["Prad"].values
                    - profile["Psyn"].values
                    - profile["Pbrm"].values
                    - profile["Plin"].values,     {"color": "red", "linestyle": "dashed", "label": r"rms"}),

            ],
            [
                (profile["Pibm"].values,        r"Beam power absorbed by ions"),
                (profile["Peic"].values,
                 r"?electron-ion heat exchange $\frac{3}{\tau_{ei}}n_{e}\left(T_{e}-T_{i}\right)\frac{m}{M}$"),
                (profile["Pix"].values,         r"auxiliary heating"),
                (profile["Pneu"].values,        r"?electron thermal losses due to ionzation of cold neutrals"),
            ],
            (profile["Poh"].values,         r"Joul heating power density $\sigma_{\parallel}\cdot E^2$"),
            (profile["Xi"].values,          r"ion heat conductivity $\chi_i$"),


        ],
        x_axis=(profile["x"].values,   {"label": r"$\rho_{N}$"}),  # x axis,
        # index_slice=slice(-100,None, 1),
        grid=True) .savefig("/home/salmon/workspace/output/profiles_exp.svg", transparent=True)