from copy import deepcopy
from pathlib import Path
import random
import os
import sys

# To launch normally from console
script_dir_path = Path(os.path.dirname(os.path.realpath(__file__)))
project_dir_id = script_dir_path.parts.index("greyjack-solver-python")
project_dir_path = Path(*script_dir_path.parts[:project_dir_id+1])
sys.path.append(str(project_dir_path))

from pathlib import Path
from greyjack.utils.MINLP2GJTranslator import MINLP2GJTranslator

data_dir_path = Path("examples", "pure_math", "minlp")
original_file_dir = Path( data_dir_path, "minlp_files" )
translated_file_dir = Path( data_dir_path, "gj_files" )
file_name = "finbb.py"

original_file_path = Path( original_file_dir, file_name )
translated_file_path = Path( translated_file_dir, file_name )

minlp_translator = MINLP2GJTranslator()
minlp_translator.translate_minlp_2_gj( original_file_path, translated_file_path, skip_initial_values=False )

print("done")