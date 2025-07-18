# greyjack/score_calculation/score_calculators/GreynetScoreCalculator.py

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from greyjack.score_calculation.scores.ScoreVariants import ScoreVariants
from greyjack.variables.GJFloat import GJFloat
from greyjack.variables.GJInteger import GJInteger
from greyjack.variables.GJBinary import GJBinary
from copy import deepcopy
import numpy as np
from pprint import pprint

if TYPE_CHECKING:
    from greyjack.score_calculation.greynet.builder import ConstraintBuilder
    from greyjack.score_calculation.greynet.session import Session

class GreynetScoreCalculator:
    """
    An incremental score calculator that uses the Greynet rule engine.
    This calculator holds the Greynet session and provides methods for
    the ScoreRequester to interact with it efficiently.
    """
    def __init__(self, constraint_builder: 'ConstraintBuilder', score_variant: ScoreVariants):
        """
        Initializes the calculator by building the Greynet session from the
        provided constraint definitions.

        Args:
            constraint_builder (ConstraintBuilder): The Greynet constraint builder
                containing all the rules for the problem.
            score_variant (ScoreVariants): The score variant enumeration that
                corresponds to the score class used in the constraint builder.
        """
        from greyjack.score_calculation.greynet.builder import ConstraintBuilder as GreynetConstraintBuilder
        if not isinstance(constraint_builder, GreynetConstraintBuilder):
            raise TypeError("constraint_builder must be an instance of greynet.ConstraintBuilder")

        self.session: 'Session' = constraint_builder.build()
        self.score_variant = score_variant
        self.is_incremental = True
        self.score_type = self.session.score_class
        
        # This mapping is populated by the ScoreRequester during initialization.
        # It is essential for translating the solver's variable indices to domain objects.
        # Key: var_idx (int) -> Value: (fact_object, attribute_name_str)
        self.var_idx_to_entity_map: Dict[int, Tuple[Any, str]] = {}

    def initial_load(self, planning_entities: Dict[str, List[Any]], problem_facts: Dict[str, List[Any]]):
        """
        Performs the initial population of the Greynet session with all facts
        from the problem domain. This should only be called once.

        Args:
            planning_entities (dict): A dictionary of planning entity lists.
            problem_facts (dict): A dictionary of problem fact lists.
        """
        self.session.clear()

        for group_name in problem_facts:
            self.session.insert_batch(problem_facts[group_name])

        for group_name in planning_entities:
            self.session.insert_batch(planning_entities[group_name])
        
        self.session.flush()
    

    def get_score(self) -> Any:
        """
        Retrieves the current total score from the Greynet session.
        Assumes all pending changes have been flushed.

        Returns:
            A score object (e.g., HardSoftScore) representing the current state.
        """
        #self.session.recalculate_all_scores()
        score = self.session.get_score()
        return score
        
    def _full_sync_and_get_score(self, sample: List[float]) -> Any:
        """
        A non-incremental way to get a score for a full solution vector.
        This modifies the session state and is primarily for debugging or fallback.
        """
        changed_facts, original_vals = self._apply_deltas_internal(list(enumerate(sample)))
        score = self.get_score()
        self._revert_deltas_internal(changed_facts, original_vals)
        return score

    def _apply_and_get_score_for_batch(self, deltas: List[List[Tuple[int, float]]]) -> List[Any]:
        """
        Applies a batch of deltas, gets the score for each, and reverts the state
        between each delta application. This is the primary method for incremental scoring.
        """
        scores = []
        for delta_set in deltas:
            if not delta_set:
                scores.append(self.get_score())
                continue

            changed_facts, original_values = self._apply_deltas_internal(delta_set)
            scores.append(self.get_score())
            self._revert_deltas_internal(changed_facts, original_values)


        return scores

    def map_deltas_to_entities(self, deltas: List[Tuple[int, float]]) -> List[Any]:

        entity_objects: List[Any] = []

        for var_idx, new_value in deltas:
            entity, attr_name = self.var_idx_to_entity_map[var_idx]
            mapped_entity = deepcopy(entity)            
            setattr(mapped_entity, attr_name, new_value)
            entity_objects.append(mapped_entity)

        return entity_objects

    def update_entity_mapping_plain(self, sample):
        delta_updates = list(enumerate(sample))

        for var_idx, new_value in delta_updates:
            entity, attr_name = self.var_idx_to_entity_map[var_idx]
            setattr(entity, attr_name, new_value)
        
        self._apply_deltas_internal(delta_updates)
    
    def update_entity_mapping_incremental(self, deltas):

        for var_idx, new_value in deltas:
            entity, attr_name = self.var_idx_to_entity_map[var_idx]
            setattr(entity, attr_name, new_value)


    def _apply_deltas_internal(self, deltas: List[Tuple[int, float]]) -> Tuple[List[Any], List[Any]]:
        """
        Internal helper to apply changes to the session state by creating modified
        copies of facts, retracting the originals, and inserting the copies.
        
        Returns:
            A tuple containing (list of original facts, list of changed facts) for reverting.
        """
        original_to_changed_map: Dict[Any, Any] = {}
        for var_idx, new_value in deltas:
            entity, attr_name = self.var_idx_to_entity_map[var_idx]
            if entity not in original_to_changed_map:
                original_to_changed_map[entity] = deepcopy(entity)
            
            setattr(original_to_changed_map[entity], attr_name, new_value)
        
        originals = list(original_to_changed_map.keys())
        changed = list(original_to_changed_map.values())

        #pprint(self.session.get_constraint_matches())

        if originals:
            #print_internals_from_entity_mapping(self.var_idx_to_entity_map)
            #print_internals(originals, "row_id")
            #score_1 = self.get_score()
            self.session.retract_batch(originals)
            #self.session.flush()
            #score_2 = self.get_score()

            #print_internals(changed, "row_id")
            self.session.insert_batch(changed)
            self.session.flush()
            #score_3 = self.get_score()

            #print()
            #self.session.recalculate_all_scores()

        return originals, changed

    def _revert_deltas_internal(self, originals: List[Any], changed: List[Any]):
        """
        Internal helper to revert the changes made by _apply_deltas_internal.
        It retracts the modified copies and re-inserts the original facts.
        """
        if changed:
            
            #score_1 = self.get_score()
            self.session.retract_batch(changed)
            #self.session.flush()
            #score_2 = self.get_score()

            self.session.insert_batch(originals)
            self.session.flush()
            #score_3 = self.get_score()

            #print()
            pass
            #self.session.recalculate_all_scores()
    
    def commit_deltas(self, deltas):

        if not deltas:
            return

        original_to_changed_map = {}
        for var_idx, new_value in deltas:
            entity, attr_name = self.var_idx_to_entity_map[var_idx]
            if entity not in original_to_changed_map:
                original_to_changed_map[entity] = deepcopy(entity)
            
            setattr(original_to_changed_map[entity], attr_name, new_value)
        
        originals = list(original_to_changed_map.keys())
        changed = list(original_to_changed_map.values())

        #for i in range(len(originals)):
        #    tmp = changed[i].greynet_fact_id
        #    changed[i].greynet_fact_id = originals[i].greynet_fact_id
        #    originals[i].greynet_fact_id = tmp

        if originals:
            self.session.retract_batch(originals)
            #self.session.flush()
            self.session.insert_batch(changed)
            self.session.flush()

        original_id_to_new_entity_map = {id(orig): new for orig, new in zip(originals, changed)}
        for var_idx, (entity, attr_name) in self.var_idx_to_entity_map.items():
            original_id = id(entity)
            if original_id in original_id_to_new_entity_map:
                self.var_idx_to_entity_map[var_idx] = (original_id_to_new_entity_map[original_id], attr_name)
        
        #self.session.recalculate_all_scores()
    
# for debug
@staticmethod
def print_internals(entities, attr_name):

    values = []
    for entity in entities:
        value = getattr(entity, attr_name)
        values.append(value)
    
    print(values)

@staticmethod
def print_internals_from_entity_mapping(var_idx_to_entity_map):

    values = []
    for var_idx in var_idx_to_entity_map.keys():
        entity, attr_name = var_idx_to_entity_map[var_idx]
        value = getattr(entity, attr_name)
        values.append(value)
    
    print(values)
