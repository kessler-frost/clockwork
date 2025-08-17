"""
HCL Parser for Clockwork Configuration Files

This module provides functionality to parse Clockwork (.cw) files written in HCL
format and convert them into structured Python dictionaries and intermediate
representations (IR) for further processing.
"""

import hcl2
from pathlib import Path
from typing import Dict, Any, Union, List
import json


class ParseError(Exception):
    """Exception raised when parsing fails."""
    
    def __init__(self, message: str, file_path: str = None, line_number: int = None):
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        
        error_msg = f"Parse error: {message}"
        if file_path:
            error_msg += f" in file '{file_path}'"
        if line_number:
            error_msg += f" at line {line_number}"
            
        super().__init__(error_msg)


class Parser:
    """
    Parser for Clockwork configuration files.
    
    Handles the parsing of HCL (.cw) files into Python dictionaries
    and converts them to structured intermediate representations.
    """
    
    def __init__(self):
        """Initialize the parser."""
        self.parsed_files = {}
        
    def parse_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Parse a single Clockwork configuration file.
        
        Args:
            file_path: Path to the .cw file to parse
            
        Returns:
            Dictionary representation of the parsed HCL content
            
        Raises:
            ParseError: If the file cannot be parsed or read
            FileNotFoundError: If the file does not exist
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
            
        if not file_path.suffix == '.cw':
            raise ParseError(f"Expected .cw file, got {file_path.suffix}", str(file_path))
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Parse HCL content using python-hcl2
            parsed_data = hcl2.loads(content)
            
            # Cache the parsed result
            self.parsed_files[str(file_path)] = parsed_data
            
            return parsed_data
            
        except Exception as e:
            raise ParseError(f"Failed to parse HCL content: {str(e)}", str(file_path))
    
    def parse_string(self, hcl_content: str) -> Dict[str, Any]:
        """
        Parse HCL content from a string.
        
        Args:
            hcl_content: HCL content as a string
            
        Returns:
            Dictionary representation of the parsed HCL content
            
        Raises:
            ParseError: If the content cannot be parsed
        """
        try:
            return hcl2.loads(hcl_content)
        except Exception as e:
            raise ParseError(f"Failed to parse HCL content: {str(e)}")
    
    def parse_directory(self, directory_path: Union[str, Path]) -> Dict[str, Dict[str, Any]]:
        """
        Parse all .cw files in a directory.
        
        Args:
            directory_path: Path to directory containing .cw files
            
        Returns:
            Dictionary mapping file paths to their parsed content
            
        Raises:
            ParseError: If any file cannot be parsed
            NotADirectoryError: If the path is not a directory
        """
        directory_path = Path(directory_path)
        
        if not directory_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {directory_path}")
            
        parsed_files = {}
        cw_files = list(directory_path.glob("*.cw"))
        
        if not cw_files:
            return parsed_files
            
        for file_path in cw_files:
            try:
                parsed_content = self.parse_file(file_path)
                parsed_files[str(file_path)] = parsed_content
            except ParseError as e:
                # Re-raise with additional context
                raise ParseError(f"Error in directory parsing: {e.message}", e.file_path, e.line_number)
                
        return parsed_files
    
    def to_ir(self, parsed_data: Dict[str, Any], file_path: str = None) -> Dict[str, Any]:
        """
        Convert parsed HCL data to Clockwork Intermediate Representation (IR).
        
        Args:
            parsed_data: Parsed HCL data as dictionary
            file_path: Optional file path for context
            
        Returns:
            Structured IR dictionary with normalized format
            
        Raises:
            ParseError: If conversion to IR fails
        """
        try:
            ir = {
                "metadata": {
                    "source_file": file_path,
                    "version": "1.0",
                    "parsed_at": None  # Could add timestamp if needed
                },
                "resources": [],
                "variables": {},
                "outputs": {},
                "modules": []
            }
            
            # Extract different HCL block types
            for block_type, blocks in parsed_data.items():
                if isinstance(blocks, list):
                    for block in blocks:
                        self._process_block(ir, block_type, block)
                elif isinstance(blocks, dict):
                    self._process_block(ir, block_type, blocks)
                    
            return ir
            
        except Exception as e:
            raise ParseError(f"Failed to convert to IR: {str(e)}", file_path)
    
    def _process_block(self, ir: Dict[str, Any], block_type: str, block_data: Dict[str, Any]):
        """
        Process a single HCL block and add it to the IR.
        
        Args:
            ir: The IR dictionary being built
            block_type: Type of the HCL block (e.g., 'resource', 'variable')
            block_data: The block's data
        """
        if block_type == "resource":
            ir["resources"].append({
                "type": block_type,
                "data": block_data
            })
        elif block_type == "variable":
            ir["variables"].update(block_data)
        elif block_type == "output":
            ir["outputs"].update(block_data)
        elif block_type == "module":
            ir["modules"].append({
                "type": block_type,
                "data": block_data
            })
        else:
            # Handle unknown block types by adding them as generic resources
            ir["resources"].append({
                "type": block_type,
                "data": block_data
            })
    
    def get_parsed_files(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all previously parsed files.
        
        Returns:
            Dictionary mapping file paths to their parsed content
        """
        return self.parsed_files.copy()
    
    def clear_cache(self):
        """Clear the cache of parsed files."""
        self.parsed_files.clear()