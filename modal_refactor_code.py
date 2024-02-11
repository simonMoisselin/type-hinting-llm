import ast
import json
import logging
from typing import Dict

import modal
import openai
from modal import Stub, web_endpoint

image = modal.Image.debian_slim().pip_install("openai", "black")

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
Your goal is to help refactoring some code. You will receive a python file, and your goal is, for each function, add a docstring to explain what this is doing, add typing into the arguments, find a better name for the function. Also I want to know a score for the complexity of the function, and a score for the readability of the function, named complexity_score and readability_score. (between 0 and 1)
The answer will be in the following JSON format:
{"refactored_functions": [{original_name: "function_name", docstring: "the docstring", arguments: {"arg_1": str,...}, new_name: "the new name if changing", complexity_score: 0.5, readability_score: 0.5}, ...]}
"""

import ast
import logging

# Ensure logging is configured in your script
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class FunctionTransformer(ast.NodeTransformer):
    def __init__(self, transformations):
        super().__init__()
        self.transformations = {t['original_name']: t for t in transformations}
        logging.debug("FunctionTransformer initialized with transformations.")

    def visit_FunctionDef(self, node):
        logging.info(f"Visiting function definition: {node.name}")
        transformation = self.transformations.get(node.name)
        if transformation:
            logging.info(f"Found transformation for function: {node.name}")
            node.name = transformation['new_name']
            transformed_args = []

            for arg_transformation in transformation['arguments']:
                try:
                    parts = arg_transformation.split(':', 2)  # Attempt to split into at most 3 parts
                    if len(parts) == 3:
                        arg_name, arg_type, default_value = parts
                        try:
                            default_ast = ast.parse(default_value.strip(), mode='eval').body
                        except SyntaxError as e:
                            logging.error(f"Syntax error parsing default value for argument '{arg_name}': {e}")
                            raise ValueError(f"Syntax error in default value: '{default_value}'")
                    elif len(parts) == 2:
                        arg_name, arg_type = parts
                        default_ast = None
                    else:
                        logging.error(f"Invalid argument format encountered: '{arg_transformation}'")
                        print(transformation)
                        raise ValueError(f"Invalid argument format: '{arg_transformation}'")

                    arg_node = ast.arg(arg=arg_name.strip(), annotation=ast.parse(arg_type.strip(), mode='eval').body)
                    transformed_args.append(arg_node)
                    if default_ast:
                        node.args.defaults.append(default_ast)
                except ValueError as e:
                    logging.error(f"Error processing argument '{arg_transformation}': {e}")
                    raise

            node.args.args = transformed_args

            docstring = ast.Expr(value=ast.Constant(value=transformation['docstring']))
            node.body.insert(0, docstring)

            logging.debug(f"Transformation applied successfully to function: {transformation['new_name']}")
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
    return json.loads(data)['refactored_functions']

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
    refactored_functions = get_refactored_functions(source_code)
    print(f"refactored_functions:\n{refactored_functions}")
    new_source_code = get_updated_source_code(source_code, refactored_functions)
    return new_source_code, refactored_functions


def reformat_code(code: str) -> str:
    import black
    from black import FileMode

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
        return formatted_code
    except Exception as e:
        print(e)
        return code  # Return the original code if no changes are made


@stub.function(secrets=[modal.Secret.from_name("simon-openai-secrets")], volumes={"/data": vol})
@web_endpoint(method="POST")
def refactor_code_web(item: Dict):
    source_code:str = item['source_code']
    refactored_code, refactored_functions = (refactor_code.local(source_code))
    reformatted_code = reformat_code(refactored_code)
    from datetime import datetime
    filename_with_date = "refactored_code_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
    with open(f"/data/{filename_with_date}", "w") as file:
        print(f"Writing reformatted code to /data/{filename_with_date}")
        file.write(reformatted_code)
    return {"reformated_code": reformatted_code, "refactored_functions": refactored_functions}


