import ast
import json
import logging
from datetime import datetime
from typing import Dict, List

import modal
import openai
from modal import Stub, web_endpoint



image = modal.Image.debian_slim().pip_install("openai", "black", "autoflake", "isort")

APP_NAME = "refactor_code_v1"

stub = modal.Stub(APP_NAME, image=image)
vol = modal.Volume.persisted("cache-gpt")


def get_messages(system_content: str, prompt: str):
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt},
    ]
    return messages


prompt_format = "\nHelp refactor this code:\n{code}\n"
prompt_format = """
Help for hint typing on this code:
{code}

Here are the functions that are missing type hinting and that you should be returning:
{missing_functions}
"""
system_content = '\nYour goal is to help refactoring some code. You will receive a python file, and a list of functions to update. Your goal is to add type hint informations from those functions. If the new types you added required new imports, add them to `imports` in the response.\nThe answer will be in the following JSON format:\n{ "functions": [{name: "function_or_submethod_name",  args: ["arg_1:int", "arg_2:type_arg_2, ...], ...], "imports": "imports needed for the new imports"}\n If the function is a class method, the first argument is always self or cls, and should not be specified in the type hinting'
import ast
import logging



class TypeHintChecker(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.missing_type_hints = []
        self.current_class_name = None  # Track the current class context

    def visit_ClassDef(self, node):
        # Store the class name when entering a class definition
        self.current_class_name = node.name
        self.generic_visit(node)  # Visit all nodes within the class
        self.current_class_name = None  # Reset the class name after leaving the class definition

    def visit_FunctionDef(self, node):
        is_class_method = any(arg.arg in ['self', 'cls'] for arg in node.args.args[:1])
        start_index = 1 if is_class_method else 0
        
        func_name = node.name
        # Prepend class name to method names if within a class context
        full_name = f"{self.current_class_name}.{func_name}" if self.current_class_name else func_name

        args_missing_types = [arg.arg for arg in node.args.args[start_index:] if not arg.annotation]
        return_missing_type = not isinstance(node.returns, ast.AST)

        if args_missing_types or return_missing_type:
            self.missing_type_hints.append({
                'name': full_name,
                'args_missing_types': args_missing_types,
                'return_missing_type': return_missing_type
        })

        self.generic_visit(node)



def find_missing_type_hints(source_code):
    tree = ast.parse(source_code)
    checker = TypeHintChecker()
    checker.visit(tree)
    return checker.missing_type_hints

class FunctionTransformer(ast.NodeTransformer):

    def __init__(self, transformations):
        super().__init__()
        self.transformations = {t["name"]: t for t in transformations}
        self.current_class_name = None
        logging.debug("FunctionTransformer initialized with transformations.")

    def visit_ClassDef(self, node):
        previous_class_name = self.current_class_name
        self.current_class_name = node.name
        self.generic_visit(node)
        self.current_class_name = previous_class_name
        return node

    def visit_FunctionDef(self, node):
        full_name = (
            f"{self.current_class_name}.{node.name}"
            if self.current_class_name
            else node.name
        )
        logging.info(f"Visiting function/method definition: {full_name}")
        transformation = self.transformations.get(full_name)
        if transformation:
            logging.info(f"Found transformation for function/method: {full_name}")
            transformed_args = []
            start_index = 0
            if (
                self.current_class_name
                and node.args.args
                and (node.args.args[0].arg in ["self", "cls"])
            ):
                transformed_args.append(node.args.args[0])
                start_index = 1
            for arg in transformation["args"]:
                parts = [x.strip() for x in arg.split(":")]
                if len(parts) == 2:
                    (arg_name, arg_type) = parts
                    try:
                        annotation = ast.parse(arg_type, mode="eval").body
                    except SyntaxError as e:
                        logging.error(
                            f"Syntax error parsing type annotation for argument '{arg_name}': {e}"
                        )
                        raise
                elif len(parts) == 1:
                    arg_name = parts[0]
                    annotation = None
                else:
                    logging.error(f"Invalid argument format: '{arg}'")
                    continue
                arg_node = ast.arg(arg=arg_name, annotation=annotation)
                if arg_name not in ["self", "cls"]:
                    transformed_args.append(arg_node)
            if len(node.args.args) > len(transformed_args):
                transformed_args.extend(node.args.args[start_index:])
            node.args.args = transformed_args
            logging.debug(
                f"Transformation applied successfully to function/method: {transformation['name']}"
            )
            return node
        else:
            logging.debug(f"No transformation found for function/method: {full_name}")
        return self.generic_visit(node)



def get_functions(source_code: str, model_name:str):
    missing_functions = find_missing_type_hints(source_code)
    missing_functions = [x['name'] for x in missing_functions if x['args_missing_types']]
    print(f"missing_functions: {missing_functions}")
    if len(missing_functions) == 0:
        return {"functions": []}
    prompt = prompt_format.format(code=source_code, missing_functions=missing_functions)
    messages = get_messages(system_content, prompt)

    response = openai.chat.completions.create(
        messages=messages,
        response_format={"type": "json_object"},
        model=model_name,
        max_tokens=1024,
        temperature=0,
        seed=42,
    )
    data: str = response.choices[0].message.content
    from ast import literal_eval
    try:
        return literal_eval(data)
    except Exception as e:
        print(f"Error parsing response from OpenAI: {data}")
        raise e




def get_updated_source_code(source_code: str, functions: list):
    parsed_code = ast.parse(source_code)
    transformer = FunctionTransformer(functions)
    transformed_ast = transformer.visit(parsed_code)
    new_source_code = ast.unparse(transformed_ast)
    return new_source_code



@stub.function(
    secrets=[modal.Secret.from_name("simon-openai-secrets")], volumes={"/data": vol},
    container_idle_timeout=60*5,
)
def refactor_code(source_code: str, model_name: str):
    import time

    current_time = time.time()
    result = get_functions(source_code, model_name)
    elapsed_time_seconds = time.time() - current_time
    print(f"Elapsed time: {elapsed_time_seconds} seconds")
    functions = result["functions"]
    print(f"result:\n{result}")
    if result.get("imports"):
        source_code_with_imports = result["imports"] + "\n" + source_code
    else:
        source_code_with_imports = source_code
    new_source_code = get_updated_source_code(source_code_with_imports, functions)
    return (new_source_code, functions)


def reformat_code(code: str) -> str:
    import black
    from black import FileMode
    from isort import code as isort_code

    "\n    Reformats the given Python code using the black library.\n\n    Parameters:\n    - code: A string containing the Python code to format.\n\n    Returns:\n    - A string containing the formatted Python code.\n    "
    try:
        formatted_code = black.format_str(code, mode=FileMode())
        sorted_code = isort_code(formatted_code)
        return sorted_code
    except Exception as e:
        print(e)
        return code


@stub.function(
    secrets=[modal.Secret.from_name("simon-openai-secrets")], volumes={"/data": vol}
)
@web_endpoint(method="POST")
def refactor_code_web(item: Dict):
    source_code: str = item["source_code"]
    model_name = item["model_name"]
    (refactored_code, functions) = refactor_code.local(source_code, model_name)
    reformatted_code = reformat_code(refactored_code)
    filename_with_date = (
        "refactored_code_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
    )
    with open(f"/data/{filename_with_date}", "w") as file:
        print(f"Writing reformatted code to /data/{filename_with_date}")
        file.write(reformatted_code)
    return {"reformated_code": reformatted_code, "functions": functions}

