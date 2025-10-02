import hcl2
from pydantic import BaseModel
from typing import Dict, Any, List
from pprint import pprint


class BaseResource(BaseModel):
    name: str


class ResourceFile(BaseResource):
    description: str
    extension: str


resource_type_mapping = {
    "file": ResourceFile
}


def generate_resource_models(resource_dicts: List[Dict[str, Any]]) -> List[BaseResource]:
    
    for rd in resource_dicts:
        ...


def parse_hcl(filename: str) -> Dict[str, Any]:
    with open(filename, "r") as f:
        return hcl2.load(f)



pprint(parse_hcl("sample.cw"))
