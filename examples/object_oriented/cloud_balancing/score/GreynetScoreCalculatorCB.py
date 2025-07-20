
from greyjack.score_calculation.greynet.builder import ConstraintBuilder, Collectors, JoinerType
from greyjack.score_calculation.scores.HardSoftScore import HardSoftScore
from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.score_calculation.score_calculators.GreynetScoreCalculator import GreynetScoreCalculator

from examples.object_oriented.cloud_balancing.cotwin.CotProcess import CotProcess
from examples.object_oriented.cloud_balancing.cotwin.CotComputer import CotComputer
import traceback


class GreynetScoreCalculatorCB(GreynetScoreCalculator):

    def __init__(self):
        
        cb = ConstraintBuilder(name="cloud_balancing_greynet_constraint_builder", score_class=HardSoftScore)
        self.add_constraints(cb)
        
        super().__init__(constraint_builder=cb, score_variant=ScoreVariants.HardSoftScore)


    def add_constraints(self, cb: ConstraintBuilder):

        @cb.constraint("required_cpu", default_weight=1.0)
        def required_cpu_constraint():
            return (
                cb.for_each(CotProcess)
                .group_by(
                    group_key_function=lambda process: process.computer_id,
                    collector_supplier=Collectors.sum(lambda process: process.cpu_power_req)
                )
                .join(
                    cb.for_each(CotComputer),
                    JoinerType.EQUAL,
                    lambda computer_id, total_cpu: computer_id,
                    lambda computer: computer.computer_id
                )
                .filter(lambda cid, total_cpu, comp: total_cpu > comp.cpu_power)
                .penalize_hard(lambda cid, total_cpu, comp: total_cpu - comp.cpu_power)
            )

        @cb.constraint("required_memory", default_weight=1.0)
        def required_memory_constraint():
            return (
                cb.for_each(CotProcess)
                .group_by(
                    group_key_function=lambda process: process.computer_id,
                    collector_supplier=Collectors.sum(lambda process: process.memory_size_req)
                )
                .join(
                    cb.for_each(CotComputer),
                    JoinerType.EQUAL,
                    lambda computer_id, total_mem: computer_id,
                    lambda computer: computer.computer_id
                )
                .filter(lambda cid, total_mem, comp: total_mem > comp.memory_size)
                .penalize_hard(lambda cid, total_mem, comp: total_mem - comp.memory_size)
            )

        @cb.constraint("required_network", default_weight=1.0)
        def required_network_constraint():
            return (
                cb.for_each(CotProcess)
                .group_by(
                    group_key_function=lambda process: process.computer_id,
                    collector_supplier=Collectors.sum(lambda process: process.network_bandwidth_req)
                )
                .join(
                    cb.for_each(CotComputer),
                    JoinerType.EQUAL,
                    lambda computer_id, total_net: computer_id,
                    lambda computer: computer.computer_id
                )
                .filter(lambda cid, total_net, comp: total_net > comp.network_bandwidth)
                .penalize_hard(lambda cid, total_net, comp: total_net - comp.network_bandwidth)
            )

        @cb.constraint("computer_cost", default_weight=1.0)
        def computer_cost_constraint():
            return (
                cb.for_each(CotProcess)
                .group_by(
                    group_key_function=lambda process: process.computer_id,
                    collector_supplier=Collectors.to_list() # We just need to know the computer is used
                )
                .join(
                    cb.for_each(CotComputer),
                    JoinerType.EQUAL,
                    lambda computer_id, processes: computer_id,
                    lambda computer: computer.computer_id
                )
                .penalize_soft(lambda cid, procs, comp: comp.cost)
            )