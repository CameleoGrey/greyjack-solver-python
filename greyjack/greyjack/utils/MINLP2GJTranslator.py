
class MINLP2GJTranslator():

    def __init__(self):
        pass

    def translate_minlp_2_gj(self, original_file_path, translated_file_path, skip_initial_values=True):

        original_lines = self._read_original_file( original_file_path )
        original_lines = self._clean_original_lines( original_lines )
        definition_blocks = self._decompose_into_definition_blocks( original_lines )
        definition_blocks["comment"] = self._process_comment_block( definition_blocks["comment"] )
        definition_blocks["pre_modeling"] = self._process_pre_modeling_block( definition_blocks["pre_modeling"] )
        definition_blocks["variables"] = self._process_variables_block( definition_blocks["variables"], skip_initial_values )
        definition_blocks["objective"] = self._process_objective_block( definition_blocks["objective"] )
        definition_blocks["constraints"] = self._process_constraints_block( definition_blocks["constraints"] )
        translated_lines = self._compose_translated_blocks( definition_blocks )
        translated_lines = self._wrap_translation_into_function( translated_lines )
        self._write_translated_file( translated_lines, translated_file_path )

        pass

    def _read_original_file(self, original_file_path):
        original_lines = []
        with open(original_file_path, "r") as original_file:
            original_lines = original_file.readlines()
        return original_lines

    def _clean_original_lines(self, original_lines):
        original_lines = "".join(original_lines)
        original_lines = original_lines.replace("\n    ", "")
        original_lines = original_lines.replace("\n\n", "\n")
        original_lines = original_lines.split("\n")
        return original_lines

    def _write_translated_file(self, translation_lines, translated_file_path):
        with open(translated_file_path, "w") as translation_file:
            translation_file.writelines( translation_lines )
        pass

    def _decompose_into_definition_blocks(self, original_lines):

        definition_blocks = {}

        definition_blocks["comment"] = []
        definition_blocks["pre_modeling"] = []
        definition_blocks["variables"] = []
        definition_blocks["objective"] = []
        definition_blocks["constraints"] = []

        for i in range(len(original_lines)):
            current_line = original_lines[i]

            if "#" in current_line:
                definition_blocks["comment"].append( current_line )
            elif "Var" in current_line:
                definition_blocks["variables"].append( current_line )
            elif "Objective" in current_line:
                definition_blocks["objective"].append( current_line )
            elif "Constraint" in current_line:
                definition_blocks["constraints"].append( current_line )
            else:
                definition_blocks["pre_modeling"].append( current_line )

        return definition_blocks

    def _process_comment_block(self, comment_block):

        comment_block[0] = "# MINLP rewritten by GreyJack Solver translator"
        comment_block = comment_block[:len(comment_block)-1]
        for i in range(len(comment_block)):
            comment_block[i] = comment_block[i] + "\n"

        return comment_block

    def _process_pre_modeling_block(self, pre_modeling_block):

        new_pre_modeling_block = []
        new_pre_modeling_block.append( "from math import pi, log, exp\n" )
        new_pre_modeling_block.append( "from greyjack.pure_math.MathModel import MathModel\n" )
        new_pre_modeling_block.append( "from greyjack.pure_math.Objective import Objective\n" )
        new_pre_modeling_block.append( "from greyjack.pure_math.Constraint import Constraint\n" )
        new_pre_modeling_block.append( "from greyjack.pure_math.variables.FloatVar import FloatVar\n" )
        new_pre_modeling_block.append( "from greyjack.pure_math.variables.IntegerVar import IntegerVar\n" )
        new_pre_modeling_block.append( "from greyjack.pure_math.variables.BinaryVar import BinaryVar\n" )
        new_pre_modeling_block.append("\n")
        new_pre_modeling_block.append( "m = model = math_model = MathModel()\n" )

        return new_pre_modeling_block

    def _process_variables_block(self, variables_block, skip_initial_values):

        for i in range(len(variables_block)):
            current_var_def = variables_block[i]
            current_var_def = self._replace_original_identificator( current_var_def, new_base="m.variables[\"" )

            current_var_def = current_var_def.split(" = ")
            left_var_def_part = current_var_def[0]
            right_var_def_part = current_var_def[1]

            right_var_def_part = right_var_def_part.split(", ")
            var_type = right_var_def_part[0]
            var_bounds = right_var_def_part[1]
            var_init = right_var_def_part[2]
            var_init = var_init[:len(var_init)-1]
            #TODO: make init in GJ variables
            var_init = var_init.split("=")[1]

            if "Reals" in var_type:
                var_type = "FloatVar"
            elif "Integers" in var_type:
                var_type = "IntegerVar"
            elif "Binary" in var_type:
                var_type = "BinaryVar"
            else:
                raise Exception("Unknown type met through translation: {}".format(var_type))

            var_bounds = var_bounds.split("=")[1]
            lower_bound, upper_bound = var_bounds.split(",")
            lower_bound = lower_bound[1:]
            upper_bound = upper_bound[:len(upper_bound)-1]

            new_var_def = None
            if var_type == "BinaryVar":
                if skip_initial_values:
                    new_var_def = left_var_def_part + " = " + var_type + "()"
                else:
                    new_var_def = left_var_def_part + " = " + var_type + "( " + "initial_value={}".format(var_init) + " )"
            elif var_type in ["FloatVar", "IntegerVar"]:
                if skip_initial_values:
                    new_var_def = left_var_def_part + " = " + var_type + "(" + lower_bound + ", " + upper_bound + " )"
                else:
                    new_var_def = left_var_def_part + " = " + var_type + "(" + lower_bound + ", " + upper_bound + ", " + "initial_value={}".format(var_init) + " )"
            else:
                raise Exception("Unknown type met through translation")
            new_var_def += "\n"

            variables_block[i] = new_var_def

        return variables_block

    def _process_objective_block(self, objective_block):

        objective_string = objective_block[0]

        definition_parts = objective_string.split(" = ")

        left_assign_part = definition_parts[0]
        left_assign_part = left_assign_part.replace( "m.obj", "m.objectives[\"f\"]" )

        # Objective(sense=..., expr= ...)
        right_assign_part = definition_parts[1]
        objective_def_parts = right_assign_part.split(", ")

        # Objective(...
        left_def_part = objective_def_parts[0]
        sense_def_parts = left_def_part.split("=")
        sense_def_parts[0] = sense_def_parts[0].replace("sense", "")
        sense_def_parts[1] = "\"" + sense_def_parts[1] + "\""
        left_def_part = sense_def_parts[0] + sense_def_parts[1]

        # expr= ...)
        expression_part = objective_def_parts[1]
        expression_part = expression_part[:len(expression_part)-1]
        expression_blocks = expression_part.split("=")
        expression_blocks[0] = "lambda v, u: "
        expression_blocks[1] = self._replace_original_identificator( expression_blocks[1], new_base="v[\"" )
        expression_part = expression_blocks[0] + expression_blocks[1]

        right_assign_part = left_def_part + ", " + expression_part + ")"

        full_objective_def = left_assign_part + " = " + right_assign_part
        objective_block[0] = full_objective_def + "\n"

        return objective_block

    def _process_constraints_block(self, constraints_block):

        for i in range(len(constraints_block)):
            current_constraint = constraints_block[i]
            left_part, right_part = current_constraint.split(" = ")

            left_part += " +"
            left_part = self._replace_original_identificator( left_part, new_base="m.constraints[\"" )
            left_part = left_part[:len(left_part)-2]

            right_part = right_part.replace( "Constraint(expr= ", "" )
            right_part = right_part[:len(right_part)-1]
            comparator = None
            if "==" in right_part: comparator = "=="
            elif "<=" in right_part: comparator = "<="
            elif ">=" in right_part: comparator = ">="
            elif "<" in right_part: comparator = "<"
            elif ">" in right_part: comparator = ">"
            else: raise Exception("Can't find comparator in {}".format(current_constraint))

            left_expr_part, right_expr_part = right_part.split(comparator)

            left_expr_part = left_expr_part.strip()
            left_expr_part += " +"
            left_expr_part = self._replace_original_identificator( left_expr_part, new_base="v[\"" )
            left_expr_part = left_expr_part[:len(left_expr_part)-2]
            left_expr_part = "lambda v, u: " + left_expr_part

            right_expr_part = right_expr_part.strip()
            right_expr_part += " +"
            right_expr_part = self._replace_original_identificator(right_expr_part, new_base="v[\"")
            right_expr_part = right_expr_part[:len(right_expr_part) - 2]
            right_expr_part = "lambda v, u: " + right_expr_part

            comparator = "\"" + comparator + "\""

            right_part = "Constraint({}, {}, {})".format( left_expr_part, comparator, right_expr_part )
            new_constraint_def = left_part + " = " + right_part + "\n"

            constraints_block[i] = new_constraint_def

        return constraints_block

    def _compose_translated_blocks(self, definition_blocks):

        translated_lines = []
        ordered_block_names = ["comment", "pre_modeling", "variables", "objective", "constraints"]
        for block_name in ordered_block_names:
            current_block = definition_blocks[block_name]
            translated_lines += current_block
            translated_lines += "\n"

        return translated_lines
    def _wrap_translation_into_function(self, translated_lines):

        model_def_start_id = 0
        for i in range(len(translated_lines)):
            if "MathModel(" in translated_lines[i]:
                model_def_start_id = i
                break

        before_func_def_lines = translated_lines[:model_def_start_id]
        func_def_lines = translated_lines[model_def_start_id:]

        new_start_line = "def build_math_model( use_hard_soft_score=True ):\n\n"
        for i in range(len(func_def_lines)):
            func_def_lines[i] = "    " + func_def_lines[i]
        new_end_line = "    return m"
        func_def_lines = [new_start_line] + func_def_lines + [new_end_line]

        translated_lines = before_func_def_lines + func_def_lines

        return translated_lines

    def _replace_original_identificator(self, expression_string, new_base="v[\""):

        if "m." not in expression_string:
            return expression_string

        expression_string = expression_string.strip()
        expression_string = expression_string.split("m.")
        for i in range(len(expression_string)):
            current_token = expression_string[i]

            if current_token == "":
                continue
            stub_token = True
            for useful_token_part in [ "x", "b", "e" ]:
                if useful_token_part in current_token:
                    stub_token = False
                    break
            if stub_token:
                continue

            # exponential digit
            if ("e" in current_token) and (current_token[0] not in ["x", "b", "e"]):
                e_pos = current_token.find("e")
                if e_pos != 0:
                    continue

            if (i == (len(expression_string)-1)) and current_token[-1].isdigit():
                current_token += " "

            j = 0
            while (current_token[j] in [ "m", ".", "x", "b", "e" ] or current_token[j].isdigit()) and (j < len(current_token)):
                j += 1

            left_token_part = current_token[:j]
            right_token_part = current_token[j:]
            left_token_part = left_token_part + "\"]"
            new_token = left_token_part + right_token_part
            expression_string[i] = new_token
        expression_string = "{}".format(new_base).join(expression_string)

        return expression_string