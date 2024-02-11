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
Your goal is to help refactoring some code. You will receive a python file, and your goal is, for each function, add typing into the args. If the new types you added required new imports, add them to `imports` in the response.
The answer will be in the following JSON format:
{"functions": [{name: "function_name",  args: ["arg_1:int", "arg_2:type_arg_2, ...], "imports": "imports needed for the new imports"}
"""

# {'functions': [{'name': 'add', 'args': {'a': 'int', 'b': 'int'}}], 'imports': ''}


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
            transformed_args = []

            # Handling args as a list of strings
            for arg in transformation['args']:
                arg_name, arg_type = [x.strip() for x in arg.split(':')]  # Ensure arg_name and arg_type are stripped of leading/trailing spaces
                try:
                    arg_node = ast.arg(arg=arg_name, annotation=ast.parse(arg_type, mode='eval').body)
                    transformed_args.append(arg_node)
                except SyntaxError as e:
                    logging.error(f"Syntax error parsing type annotation for argument '{arg_name}': {e}")
                    raise

            # Updating the function's args list
            node.args.args = transformed_args

            logging.debug(f"Transformation applied successfully to function: {transformation['name']}")
            return node
        else:
            logging.debug(f"No transformation found for function: {node.name}")
        return node




def get_functions(source_code):
    prompt  = prompt_format.format(code=source_code)
    messages = get_messages(system_content, prompt)
    model_name = "gpt-4-0125-preview"
    model_name = "gpt-3.5-turbo-0125"
    response = openai.chat.completions.create(messages=messages, response_format={"type": "json_object"}, model=model_name)
    data: str = response.choices[0].message.content
    return json.loads(data)

def get_updated_source_code(source_code, functions):
    # Parse the source code into an AST
    parsed_code = ast.parse(source_code)

    # Transform the AST based on the transformations
    transformer = FunctionTransformer(functions)
    transformed_ast = transformer.visit(parsed_code)

    # Convert the transformed AST back to source code
    new_source_code = ast.unparse(transformed_ast)
    return new_source_code


@stub.function(secrets=[modal.Secret.from_name("simon-openai-secrets")], volumes={"/data": vol})
def refactor_code(source_code: str):
    import time
    current_time = time.time()
    result = get_functions(source_code)
    elapsed_time_seconds = time.time() - current_time
    print(f"Elapsed time: {elapsed_time_seconds} seconds")
    functions = result['functions']

    print(f"result:\n{result}")
    if result.get('imports'):
        source_code_with_imports = result['imports'] + "\n" + source_code
    else:
        source_code_with_imports = source_code

    new_source_code = get_updated_source_code(source_code_with_imports, functions)
    
    return new_source_code, functions


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
    refactored_code, functions = (refactor_code.local(source_code))
    reformatted_code = reformat_code(refactored_code)
    from datetime import datetime
    filename_with_date = "refactored_code_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
    with open(f"/data/{filename_with_date}", "w") as file:
        print(f"Writing reformatted code to /data/{filename_with_date}")
        file.write(reformatted_code)
    return {"reformated_code": reformatted_code, "functions": functions,}


