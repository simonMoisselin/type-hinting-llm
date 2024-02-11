from modal_refactor_code import FunctionTransformer
import ast
import unittest


from typing import List, Tuple, Dict, Optional

test_cases = [
    # Function with a List Default Value
    {
        "source_code": """
def list_example(items: List[int] = [1, 2, 3]) -> List[int]:
    return items
""",
        "expected_code": """
def process_list(items: List[int] = [1, 2, 3]) -> List[int]:
    \"\"\"This function processes a list.\"\"\"
    return items
""",
        "transformation": {
            'original_name': 'list_example', 
            'new_name': 'process_list', 
            'arguments': "items: List[int] = [1, 2, 3]", 
            'docstring': 'This function processes a list.'
        }
    },
    # Function with a Tuple Default Value
    {
        "source_code": """
def tuple_example(args: Tuple[int, int] = (1, 2)) -> Tuple[int, int]:
    return args
""",
        "expected_code": """
def process_tuple(args: Tuple[int, int] = (1, 2)) -> Tuple[int, int]:
    \"\"\"This function processes a tuple.\"\"\"
    return args
""",
        "transformation": {
            'original_name': 'tuple_example', 
            'new_name': 'process_tuple', 
            'arguments': "args: Tuple[int, int] = (1, 2)", 
            'docstring': 'This function processes a tuple.'
        }
    },
    # Function with a Dict Default Value
    {
        "source_code": """
def dict_example(settings: Dict[str, int] = {'threshold': 5, 'limit': 10}) -> Dict[str, int]:
    return settings
""",
        "expected_code": """
def process_dict(settings: Dict[str, int] = {'threshold': 5, 'limit': 10}) -> Dict[str, int]:
    \"\"\"This function processes a dictionary.\"\"\"
    return settings
""",
        "transformation": {
            'original_name': 'dict_example', 
            'new_name': 'process_dict', 
            'arguments': "settings: Dict[str, int] = {'threshold': 5, 'limit': 10}", 
            'docstring': 'This function processes a dictionary.'
        }
    },
    # Function with Optional Type Hint
    {
        "source_code": """
def optional_example(value: Optional[int] = None) -> Optional[int]:
    return value
""",
        "expected_code": """
def process_optional(value: Optional[int] = None) -> Optional[int]:
    \"\"\"This function processes an optional value.\"\"\"
    return value
""",
        "transformation": {
            'original_name': 'optional_example', 
            'new_name': 'process_optional', 
            'arguments': "value: Optional[int] = None", 
            'docstring': 'This function processes an optional value.'
        }
    },
    # Function with *args and **kwargs
    {
        "source_code": """
def args_kwargs_example(*args: int, **kwargs: str) -> List[int]:
    return list(args), kwargs
""",
        "expected_code": """
def process_args_kwargs(*args: int, **kwargs: str) -> List[int]:
    \"\"\"This function processes args and kwargs.\"\"\"
    return list(args), kwargs
""",
        "transformation": {
            'original_name': 'args_kwargs_example', 
            'new_name': 'process_args_kwargs', 
            'arguments': "*args: int, **kwargs: str", 
            'docstring': 'This function processes args and kwargs.'
        }
    },
]


import ast


# More test methods can be added here to cover different scenarios

if __name__ == '__main__':
    unittest.main()

