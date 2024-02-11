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
system_content = '\nYour goal is to help refactoring some code. You will receive a python file, the goal is to have type hinting in all methods (functions and class sub methods). Your goal is to only add the missing type hintings args. If the new types you added required new imports, add them to `imports` in the response.\nThe answer will be in the following JSON format:\n{"functions": [{name: "function_or_submethod_name",  args: ["arg_1:int", "arg_2:type_arg_2, ...], ...], "imports": "imports needed for the new imports"}\n\n- Do not add existing functions if they are already typed.\n- Do not forget to add typing for ALL the methods for each class (can have multiple methods per class), by using this syntax: name: Classname.method_name, ...\n'
import ast
import logging


class FunctionTransformer(ast.NodeTransformer):

    def __init__(self, transformations: list):
        super().__init__()
        self.transformations = {t["name"]: t for t in transformations}
        self.current_class_name = None
        logging.debug("FunctionTransformer initialized with transformations.")

    def visit_ClassDef(self, node: ast.ClassDef):
        previous_class_name = self.current_class_name
        self.current_class_name = node.name
        self.generic_visit(node)
        self.current_class_name = previous_class_name
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
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


def get_functions(source_code: str):
    prompt = prompt_format.format(code=source_code)
    messages = get_messages(system_content, prompt)
    model_name = "gpt-3.5-turbo-0125"
    model_name = "gpt-4-0125-preview"
    response = openai.chat.completions.create(
        messages=messages,
        response_format={"type": "json_object"},
        model=model_name,
        max_tokens=512,
    )
    data: str = response.choices[0].message.content
    return json.loads(data)


def get_updated_source_code(source_code: str, functions: list):
    parsed_code = ast.parse(source_code)
    transformer = FunctionTransformer(functions)
    transformed_ast = transformer.visit(parsed_code)
    new_source_code = ast.unparse(transformed_ast)
    return new_source_code


@stub.function(
    secrets=[modal.Secret.from_name("simon-openai-secrets")], volumes={"/data": vol}
)
def refactor_code(source_code: str):
    import time

    current_time = time.time()
    result = get_functions(source_code)
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
    (refactored_code, functions) = refactor_code.local(source_code)
    reformatted_code = reformat_code(refactored_code)
    filename_with_date = (
        "refactored_code_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
    )
    with open(f"/data/{filename_with_date}", "w") as file:
        print(f"Writing reformatted code to /data/{filename_with_date}")
        file.write(reformatted_code)
    return {"reformated_code": reformatted_code, "functions": functions}
