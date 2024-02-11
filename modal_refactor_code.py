import ast
import json
from typing import Dict

import modal
import openai
from modal import Stub, web_endpoint

image = modal.Image.debian_slim().pip_install("openai", "black")

APP_NAME = "refactor_code_v0"
stub = modal.Stub(APP_NAME, image=image)

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
{"refactored_functions": [{original_name: "function_name", docstring: "the docstring", arguments: "the arguments with typing", new_name: "the new name if changing", complexity_score: 0.5, readability_score: 0.5}, ...], "code_feedback": "Some feedback about the code in destination of the author. Make a bullet list of things to improve upon"}
"""


class FunctionTransformer(ast.NodeTransformer):
    def __init__(self, transformations):
        super().__init__()
        self.transformations = {t['original_name']: t for t in transformations}
    
    def visit_FunctionDef(self, node):
        transformation = self.transformations.get(node.name)
        if transformation:
            # Update the function name
            node.name = transformation['new_name']
            
            # Handle arguments and default values without separate parsing
            # Assume transformation['arguments'] is a list of (arg_name, arg_type, default_value)
            transformed_args = []
            for arg in transformation['arguments']:
                arg_name, arg_type, default_value = arg.split(':')
                # Create a new argument node with type annotation
                new_arg = ast.arg(arg=arg_name.strip(), annotation=ast.parse(arg_type.strip(), mode='eval').body)
                transformed_args.append(new_arg)
                # Handling default values directly without separate parsing by adding them to node.args.defaults as needed
                if default_value:
                    # This part needs to be adjusted based on how default values are represented and stored
                    pass  # Add logic to handle default values appropriately
            
            node.args.args = transformed_args
            
            # Insert the docstring at the first position of the function body
            docstring = ast.Expr(value=ast.Constant(value=transformation['docstring']))
            node.body.insert(0, docstring)
            
            return node
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


@stub.function(secrets=[modal.Secret.from_name("simon-openai-secrets")])
def refactor_code(source_code: str):
    refactored_functions = get_refactored_functions(source_code)
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


@stub.function(secrets=[modal.Secret.from_name("simon-openai-secrets")])
@web_endpoint(method="POST")
def refactor_code_web(item: Dict):
    source_code:str = item['source_code']
    refactored_code, refactored_functions = (refactor_code.local(source_code))
    reformatted_code = reformat_code(refactored_code)
    return {"reformated_code": reformatted_code, "refactored_functions": refactored_functions}


