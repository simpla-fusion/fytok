import typing
import scipy.constants
from spdm.data.Expression import Variable, Expression, zero
from spdm.data.sp_property import sp_tree
from fytok.utils.atoms import nuclear_reaction, atoms
from fytok.modules.CoreSources import CoreSources
from fytok.utils.logger import logger


@sp_tree
class FusionReaction(CoreSources.Source):
    """[summary]

    Args:
        CoreSources ([type]): [description]


    $\\alpha$输运模型参考[@angioniGyrokineticCalculationsDiffusive2008; @angioniGyrokineticSimulationsImpurity2009]

    * energetic $\\alpha$ particle density $n_{\\alpha}$

    $$
    \\frac{\\partial n_{\\alpha}}{\\partial t}+\\nabla\\left(-D_{\\alpha}\\nabla n_{\\alpha}+Vn_{\\alpha}\\right)=-\\frac{n_{\\alpha}}{\\tau_{sd}^{*}}+n_{D}n_{T}\\left\\langle \\sigma v\\right\\rangle _{DT}
    $$

    * $He$ ash density $n_{He}$

    $$
    \\frac{\\partial n_{He}}{\\partial t}+\\nabla\\left(-D_{He}\\nabla n_{He}+Vn_{He}\\right)=\\frac{n_{\\alpha}}{\\tau_{sd}^{*}}
    $$

    where
    $$
    \\tau_{sd}^{*}=\\ln\\left(v_{\\alpha}^{3}/v_{c}^{3}+1\\right)\\left(m_{e}m_{\\alpha}v_{e}^{3}\\right)/\\left(64\\sqrt{\\pi}e^{4}n_{e}\\ln\\Lambda\\right)
    $$
    is the actual thermalization slowing down time.

    energetic $\\alpha$ particle flux
    $$
    \\frac{R\\Gamma_{\\alpha}}{n_{\\alpha}}=D_{\\alpha}\\left(\\frac{R}{L_{n_{\\alpha}}}C_{p_{\\alpha}}\\right)
    $$
    where
    $$
    D_{\\alpha}=D_{\\text{He}}\\left[0.02+4.5\\left(\\frac{T_{e}}{E_{\\alpha}}\\right)+8\\left(\\frac{T_{e}}{E_{\\alpha}}\\right)^{2}+350\\left(\\frac{T_{e}}{E_{\\alpha}}\\right)^{3}\\right]
    $$
    and
    $$
    C_{p_{\\alpha}}=\\frac{3}{2}\\frac{R}{L_{T_{e}}}\\left[\\frac{1}{\\log\\left[\\left(E_{\\alpha}/E_{c}\\right)^{3/2}+1\\right]\\left[1+\\left(E_{c}/E_{\\alpha}\\right)^{3/2}\\right]}-1\\right]
    $$
    Here $E_{c}$ is the slowing down critical energy. We remind that $E_{c}/E_{\\alpha}=33.05 T_e/E_{\\alpha}$, where $E_{\\alpha}=3500 keV$  is the thirth energy of $\\alpha$ particles.
    """

    identifier = "fusion"

    code = {"name": "fusion", "description": "Fusion reaction"}  # type: ignore

    def fetch(self, x: Variable, **variables: Expression) -> CoreSources.Source.TimeSlice:
        current: CoreSources.Source.TimeSlice = super().fetch()

        source_1d = current.profiles_1d

        fusion_reactions: typing.List[str] = self.code.parameters.fusion_reactions or []

        # Te = variables.get("electrons/temperature")
        # ne = variables.get("electrons/density")

        lnGamma = 17

        # tau_slowing_down = 1.99 * ((Te / 1000) ** (3 / 2)) / (ne * 1.0e-19 * lnGamma)

        for tag in fusion_reactions:
            reaction = nuclear_reaction[tag]

            r0, r1 = reaction.reactants
            p0, p1 = reaction.products

            pa = atoms[p1].label

            mass_p0 = atoms[p0].mass
            mass_p1 = atoms[p1].mass

            n0 = variables.get(f"ion/{r0}/density")
            n1 = variables.get(f"ion/{r1}/density")

            T0 = variables.get(f"ion/{r0}/temperature")
            T1 = variables.get(f"ion/{r1}/temperature")
            ni = n0 + n1
            Ti = (n0 * T0 + n1 * T1) / ni
            nEP = variables.get(f"ion/{p1}/density")

            nu_slowing_down = (ni * 1.0e-19 * lnGamma) / (1.99 * ((Ti / 1000) ** (3 / 2)))

            S = reaction.reactivities(Ti) * n0 * n1

            if r0 == r1:
                S *= 0.5

            source_1d.ion[r0].particles -= S
            source_1d.ion[r1].particles -= S
            source_1d.ion[p0].particles += S
            source_1d.ion[p1].particles += S - nEP * nu_slowing_down
            source_1d.ion[pa].particles += nEP * nu_slowing_down

            fusion_energy = reaction.energy / scipy.constants.electron_volt

            if atoms[p0].z == 0:
                fusion_energy *= mass_p0 / (mass_p0 + mass_p1)
            elif atoms[p1].z == 0:
                fusion_energy *= mass_p1 / (mass_p0 + mass_p1)

            fusion_energy *= nEP * nu_slowing_down

            # 假设 He ash 的温度为离子平均温度，alpha 粒子慢化后能量传递给电子
            # t_i_average = variables.get("t_i_average", Ti)
            # 加热
            source_1d.electrons.energy += fusion_energy

        return current


CoreSources.Source.register(["fusion"], FusionReaction)