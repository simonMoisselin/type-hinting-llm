import ast
import json
import logging
from typing import Dict

import modal
import openai
from modal import Stub, web_endpoint

image = modal.Image.debian_slim().pip_install("openai", "black", "autoflake", "isort")

APP_NAME = "refactor_code_v0"
stub = modal.Stub(APP_NAME, image=image)





vol = modal.Volume.persisted("cache-gpt")
def get_messages(system_content: str, prompt: str):
    messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ]
    return messages 



prompt_format = """
Help refactor this code:
{code}
"""
system_content = """
Your goal is to help refactoring some code. You will receive a python file, and your goal is, for each function, add typing into the arguments. Also I want to know a score for the complexity of the function, and a score for the readability of the overal code, named complexity_score and readability_score. (between 0 and 1). Don't forget to return the code needed to make the type hinting works, nothing more (from typing import .. , )
The answer will be in the following JSON format:
{"refactored_functions": [{name: "function_name",  arguments: {"arg_1": str,...}}, ...], complexity_score: 0.5, readability_score: 0.5, "import_code": "imports needed for the refactored code"}
"""


# Ensure logging is configured in your script


class FunctionTransformer(ast.NodeTransformer):
    def __init__(self, transformations):
        super().__init__()
        self.transformations = {t['name']: t for t in transformations}
        logging.debug("FunctionTransformer initialized with transformations.")

    def visit_FunctionDef(self, node):
        logging.info(f"Visiting function definition: {node.name}")
        transformation = self.transformations.get(node.name)
        if transformation:
            logging.info(f"Found transformation for function: {node.name}")
            # node.name = transformation['new_name']
            transformed_args = []

            # Handling arguments as a dictionary
            for arg_name, arg_type in transformation['arguments'].items():
                try:
                    # There's no default value handling here, as it wasn't specified in the provided data structure
                    # If defaults are needed, they should be included in the transformations data and handled accordingly
                    arg_node = ast.arg(arg=arg_name, annotation=ast.parse(arg_type, mode='eval').body)
                    transformed_args.append(arg_node)
                except SyntaxError as e:
                    logging.error(f"Syntax error parsing type annotation for argument '{arg_name}': {e}")
                    raise

            # Updating the function's arguments list
            node.args.args = transformed_args

            # Inserting the docstring
            # docstring = ast.Expr(value=ast.Constant(value=transformation['docstring']))
            # node.body.insert(0, docstring)

            logging.debug(f"Transformation applied successfully to function: {transformation['name']}")
            return node
        else:
            logging.debug(f"No transformation found for function: {node.name}")
        return node





def get_refactored_functions(source_code):
    prompt  = prompt_format.format(code=source_code)
    messages = get_messages(system_content, prompt)
    model_name = "gpt-4-0125-preview"
    model_name = "gpt-3.5-turbo-0125"
    response = openai.chat.completions.create(messages=messages, response_format={"type": "json_object"}, model=model_name)
    data: str = response.choices[0].message.content
    return json.loads(data)

def get_updated_source_code(source_code, refactored_functions):
    # Parse the source code into an AST
    parsed_code = ast.parse(source_code)

    # Transform the AST based on the transformations
    transformer = FunctionTransformer(refactored_functions)
    transformed_ast = transformer.visit(parsed_code)

    # Convert the transformed AST back to source code
    new_source_code = ast.unparse(transformed_ast)
    return new_source_code


@stub.function(secrets=[modal.Secret.from_name("simon-openai-secrets")], volumes={"/data": vol})
def refactor_code(source_code: str):
    import time
    current_time = time.time()
    result = get_refactored_functions(source_code)
    elapsed_time_seconds = time.time() - current_time
    print(f"Elapsed time: {elapsed_time_seconds} seconds")
    refactored_functions = result['refactored_functions']
    complexity_score = result['complexity_score']
    readability_score = result['readability_score']
    print(f"result:\n{result}")
    if result.get('import_code'):
        source_code_with_imports = result['import_code'] + "\n" + source_code
    new_source_code = get_updated_source_code(source_code_with_imports, refactored_functions)
    return new_source_code, refactored_functions, complexity_score, readability_score


def reformat_code(code: str) -> str:
    import black
    from black import FileMode
    from isort import code as isort_code

    """
    Reformats the given Python code using the black library.

    Parameters:
    - code: A string containing the Python code to format.

    Returns:
    - A string containing the formatted Python code.
    """
    try:
        # Use black to format the code. FileMode() specifies file-specific options.
        formatted_code = black.format_str(code, mode=FileMode())
        sorted_code = isort_code(formatted_code)
        return sorted_code
    except Exception as e:
        print(e)
        return code  # Return the original code if no changes are made


@stub.function(secrets=[modal.Secret.from_name("simon-openai-secrets")], volumes={"/data": vol})
@web_endpoint(method="POST")
def refactor_code_web(item: Dict):
    source_code:str = item['source_code']
    refactored_code, refactored_functions, complexity_score, readability_score = (refactor_code.local(source_code))
    reformatted_code = reformat_code(refactored_code)
    from datetime import datetime
    filename_with_date = "refactored_code_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
    with open(f"/data/{filename_with_date}", "w") as file:
        print(f"Writing reformatted code to /data/{filename_with_date}")
        file.write(reformatted_code)
    return {"reformated_code": reformatted_code, "refactored_functions": refactored_functions, "complexity_score": complexity_score, "readability_score": readability_score, }


