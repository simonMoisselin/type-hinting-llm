import ast
import json
import logging
from datetime import datetime
from typing import Dict

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
            {"role": "user", "content": prompt}
        ]
    return messages 



prompt_format = """
Help refactor this code:
{code}
"""
system_content = """
Your goal is to help refactoring some code. You will receive a python file, the goal is to have type hinting in all methods (functions and class sub methods). Your goal is to only add the missing type hintings args. If the new types you added required new imports, add them to `imports` in the response.
The answer will be in the following JSON format:
{"functions": [{name: "function_or_submethod_name",  args: ["arg_1:int", "arg_2:type_arg_2, ...], ...], "imports": "imports needed for the new imports"}

- Do not add existing functions if they are already typed.
- Do not forget to add typing for ALL the methods for each class (can have multiple methods per class), by using this syntax: name: Classname.method_name, ...
"""

# {'functions': [{'name': 'add', 'args': {'a': 'int', 'b': 'int'}}], 'imports': ''}


# Ensure logging is configured in your script


import ast
import logging


class FunctionTransformer(ast.NodeTransformer):
    def __init__(self, transformations):
        super().__init__()
        self.transformations = {t['name']: t for t in transformations}
        self.current_class_name = None  # Track the current class name context
        logging.debug("FunctionTransformer initialized with transformations.")

    def visit_ClassDef(self, node):
        # Temporarily store the current class name when visiting a ClassDef
        previous_class_name = self.current_class_name
        self.current_class_name = node.name
        self.generic_visit(node)  # Visit all nodes within the class
        self.current_class_name = previous_class_name  # Restore previous context
        return node

    def visit_FunctionDef(self, node):
        # Construct the function's full name depending on context
        full_name = f"{self.current_class_name}.{node.name}" if self.current_class_name else node.name

        logging.info(f"Visiting function/method definition: {full_name}")
        transformation = self.transformations.get(full_name)
        if transformation:
            logging.info(f"Found transformation for function/method: {full_name}")
            transformed_args = []
            
            # Initialize starting index to 0 or 1 based on presence of 'self' or 'cls'
            start_index = 0
            if self.current_class_name and node.args.args and node.args.args[0].arg in ['self', 'cls']:
                # Preserve 'self' or 'cls' for class or static methods
                transformed_args.append(node.args.args[0])
                start_index = 1

            # Process transformations for other arguments
            for arg in transformation['args']:
                parts = [x.strip() for x in arg.split(':')]
                if len(parts) == 2:
                    arg_name, arg_type = parts
                    try:
                        annotation = ast.parse(arg_type, mode='eval').body
                    except SyntaxError as e:
                        logging.error(f"Syntax error parsing type annotation for argument '{arg_name}': {e}")
                        raise
                elif len(parts) == 1:
                    arg_name = parts[0]
                    annotation = None
                else:
                    logging.error(f"Invalid argument format: '{arg}'")
                    continue
                
                # Generate new argument node
                arg_node = ast.arg(arg=arg_name, annotation=annotation)
                # Add argument node if it's not the first argument or explicitly handled above
                if arg_name not in ['self', 'cls']:
                    transformed_args.append(arg_node)

            # Retain existing arguments from start_index onwards if not replaced
            if len(node.args.args) > len(transformed_args):
                transformed_args.extend(node.args.args[start_index:])
            
            # Update the function's args list
            node.args.args = transformed_args
            logging.debug(f"Transformation applied successfully to function/method: {transformation['name']}")
            return node
        else:
            logging.debug(f"No transformation found for function/method: {full_name}")
        return self.generic_visit(node)  # Continue visiting the tree if no transformation is applied




def get_functions(source_code):
    prompt  = prompt_format.format(code=source_code)
    messages = get_messages(system_content, prompt)
    model_name = "gpt-3.5-turbo-0125"
    model_name = "gpt-4-0125-preview"

    response = openai.chat.completions.create(messages=messages, response_format={"type": "json_object"}, model=model_name, max_tokens=512)
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
    
    filename_with_date = "refactored_code_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
    with open(f"/data/{filename_with_date}", "w") as file:
        print(f"Writing reformatted code to /data/{filename_with_date}")
        file.write(reformatted_code)
    return {"reformated_code": reformatted_code, "functions": functions,}


