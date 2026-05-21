#!/usr/bin/env python3
"""
HAGBES FLEET DEPLOYMENT VALIDATION PIPELINE
===========================================

Enterprise-grade deployment validation system that prevents broken deployments
and ensures production safety for the hagbes_fleet module.

This validator MUST pass all checks before any production deployment.
"""

import os
import sys
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
import xml.etree.ElementTree as ET
import ast
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DeploymentValidator:
    """Enterprise deployment validation system for hagbes_fleet module."""
    
    def __init__(self, module_path: str):
        self.module_path = Path(module_path)
        self.validation_results = {
            'python_compilation': False,
            'xml_validation': False,
            'manifest_validation': False,
            'security_completeness': False,
            'orm_schema_consistency': False,
            'approval_workflow_integrity': False,
            'critical_errors': [],
            'warnings': [],
            'deployment_approved': False
        }
    
    def validate_python_compilation(self) -> bool:
        """Block deployment if Python compilation fails."""
        logger.info("🔍 Validating Python compilation...")
        
        python_files = list(self.module_path.rglob("*.py"))
        compilation_errors = []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    source = f.read()
                
                # Compile to bytecode
                compile(source, str(py_file), 'exec')
                
                # Parse AST for additional validation
                try:
                    ast.parse(source)
                except SyntaxError as e:
                    compilation_errors.append(f"AST Parse Error in {py_file}: {e}")
                    
            except Exception as e:
                compilation_errors.append(f"Compilation Error in {py_file}: {e}")
        
        if compilation_errors:
            self.validation_results['critical_errors'].extend(compilation_errors)
            logger.error(f"❌ Python compilation failed: {len(compilation_errors)} errors")
            return False
        
        logger.info(f"✅ Python compilation passed: {len(python_files)} files validated")
        return True
    
    def validate_xml_syntax(self) -> bool:
        """Block deployment if XML validation fails."""
        logger.info("🔍 Validating XML syntax...")
        
        xml_files = list(self.module_path.rglob("*.xml"))
        xml_errors = []
        
        for xml_file in xml_files:
            try:
                ET.parse(xml_file)
            except ET.ParseError as e:
                xml_errors.append(f"XML Parse Error in {xml_file}: {e}")
            except Exception as e:
                xml_errors.append(f"XML Error in {xml_file}: {e}")
        
        if xml_errors:
            self.validation_results['critical_errors'].extend(xml_errors)
            logger.error(f"❌ XML validation failed: {len(xml_errors)} errors")
            return False
        
        logger.info(f"✅ XML validation passed: {len(xml_files)} files validated")
        return True
    
    def validate_manifest_dependencies(self) -> bool:
        """Block deployment if manifest dependencies are invalid."""
        logger.info("🔍 Validating manifest dependencies...")
        
        manifest_path = self.module_path / "__manifest__.py"
        if not manifest_path.exists():
            self.validation_results['critical_errors'].append("Missing __manifest__.py file")
            return False
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_content = f.read()
            
            # Parse manifest as Python dict
            manifest_dict = ast.literal_eval(manifest_content)
            
            # Validate required dependencies
            required_deps = ['base', 'fleet', 'hr', 'mail', 'sms', 'hagbes_approval_workflow']
            actual_deps = manifest_dict.get('depends', [])
            
            missing_deps = set(required_deps) - set(actual_deps)
            if missing_deps:
                self.validation_results['critical_errors'].append(
                    f"Missing required dependencies: {missing_deps}"
                )
                return False
            
            # Validate data files exist
            data_files = manifest_dict.get('data', [])
            for data_file in data_files:
                file_path = self.module_path / data_file
                if not file_path.exists():
                    self.validation_results['critical_errors'].append(
                        f"Missing data file referenced in manifest: {data_file}"
                    )
                    return False
            
            logger.info("✅ Manifest validation passed")
            return True
            
        except Exception as e:
            self.validation_results['critical_errors'].append(f"Manifest validation error: {e}")
            return False
    
    def validate_security_completeness(self) -> bool:
        """Block deployment if security access rules are incomplete."""
        logger.info("🔍 Validating security access rules completeness...")
        
        # Check if all required models have access rules
        required_models = [
            'hagbes.fleet.vehicle',
            'hagbes.fleet.allocation', 
            'hagbes.fleet.trip.log',
            'hagbes.fleet.trip.gps',
            'hagbes.fleet.discrepancy',
            'hagbes.fleet.vehicle.status.log',
            'hagbes.fleet.allocation.append',
            'fleet.requisition',
            'fleet.trip',
            'fleet.vehicle.history'
        ]
        
        required_groups = [
            'group_fleet_requester',
            'group_dept_manager', 
            'group_fmo',
            'group_fleet_manager',
            'group_fleet_admin'
        ]
        
        access_file = self.module_path / "security" / "ir.model.access.csv"
        if not access_file.exists():
            self.validation_results['critical_errors'].append("Missing ir.model.access.csv file")
            return False
        
        try:
            with open(access_file, 'r', encoding='utf-8') as f:
                access_content = f.read()
            
            missing_access = []
            for model in required_models:
                model_id = f"model_{model.replace('.', '_')}"
                if model_id not in access_content:
                    missing_access.append(f"Missing access rules for model: {model}")
            
            if missing_access:
                self.validation_results['critical_errors'].extend(missing_access)
                return False
            
            logger.info("✅ Security access rules validation passed")
            return True
            
        except Exception as e:
            self.validation_results['critical_errors'].append(f"Security validation error: {e}")
            return False
    
    def validate_approval_workflow_integrity(self) -> bool:
        """Validate 3-step approval workflow configuration."""
        logger.info("🔍 Validating approval workflow integrity...")
        
        approval_flow_file = self.module_path / "data" / "fleet_approval_flows.xml"
        if not approval_flow_file.exists():
            self.validation_results['critical_errors'].append("Missing fleet_approval_flows.xml")
            return False
        
        try:
            tree = ET.parse(approval_flow_file)
            root = tree.getroot()
            
            # Check for fleet_requisition flow
            flow_found = False
            required_steps = ['dept_manager', 'property_officer', 'fmo_officer']
            steps_found = []
            
            for record in root.findall(".//record[@model='approval.flow']"):
                request_type = record.find(".//field[@name='request_type']")
                if request_type is not None and request_type.text == 'fleet_requisition':
                    flow_found = True
                    break
            
            if not flow_found:
                self.validation_results['critical_errors'].append(
                    "Missing fleet_requisition approval flow configuration"
                )
                return False
            
            # Check for required approval steps
            for record in root.findall(".//record[@model='approval.step']"):
                record_id = record.get('id', '')
                for step in required_steps:
                    if step in record_id:
                        steps_found.append(step)
            
            missing_steps = set(required_steps) - set(steps_found)
            if missing_steps:
                self.validation_results['critical_errors'].append(
                    f"Missing approval workflow steps: {missing_steps}"
                )
                return False
            
            logger.info("✅ Approval workflow integrity validation passed")
            return True
            
        except Exception as e:
            self.validation_results['critical_errors'].append(f"Workflow validation error: {e}")
            return False
    
    def validate_orm_schema_consistency(self) -> bool:
        """Validate ORM model definitions are consistent."""
        logger.info("🔍 Validating ORM schema consistency...")
        
        # Check that all models have proper field definitions
        models_dir = self.module_path / "models"
        if not models_dir.exists():
            self.validation_results['critical_errors'].append("Missing models directory")
            return False
        
        model_files = list(models_dir.glob("*.py"))
        schema_errors = []
        
        for model_file in model_files:
            if model_file.name == "__init__.py":
                continue
                
            try:
                with open(model_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for proper model inheritance
                if "models.Model" in content or "models.AbstractModel" in content:
                    # Validate _name is defined
                    if "_name = " not in content and "models.AbstractModel" not in content:
                        schema_errors.append(f"Model in {model_file.name} missing _name attribute")
                    
                    # Check for proper field definitions
                    if "fields." in content:
                        # Basic validation that fields are properly defined
                        field_pattern = r'(\w+)\s*=\s*fields\.\w+'
                        fields_found = re.findall(field_pattern, content)
                        if not fields_found and "AbstractModel" not in content:
                            self.validation_results['warnings'].append(
                                f"No fields found in model {model_file.name}"
                            )
                
            except Exception as e:
                schema_errors.append(f"Error validating {model_file.name}: {e}")
        
        if schema_errors:
            self.validation_results['critical_errors'].extend(schema_errors)
            return False
        
        logger.info("✅ ORM schema consistency validation passed")
        return True
    
    def run_full_validation(self) -> Dict[str, Any]:
        """Run complete deployment validation pipeline."""
        logger.info("🚀 Starting HAGBES FLEET deployment validation pipeline...")
        
        # Run all validation checks
        validations = [
            ('python_compilation', self.validate_python_compilation),
            ('xml_validation', self.validate_xml_syntax),
            ('manifest_validation', self.validate_manifest_dependencies),
            ('security_completeness', self.validate_security_completeness),
            ('orm_schema_consistency', self.validate_orm_schema_consistency),
            ('approval_workflow_integrity', self.validate_approval_workflow_integrity)
        ]
        
        all_passed = True
        for validation_name, validation_func in validations:
            try:
                result = validation_func()
                self.validation_results[validation_name] = result
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"Validation {validation_name} failed with exception: {e}")
                self.validation_results[validation_name] = False
                self.validation_results['critical_errors'].append(f"{validation_name}: {e}")
                all_passed = False
        
        # Final deployment decision
        self.validation_results['deployment_approved'] = all_passed and len(self.validation_results['critical_errors']) == 0
        
        # Generate validation report
        self.generate_validation_report()
        
        return self.validation_results
    
    def generate_validation_report(self):
        """Generate comprehensive validation report."""
        report_path = self.module_path / "deployment" / "validation_report.json"
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2)
        
        # Generate human-readable report
        text_report_path = self.module_path / "deployment" / "validation_report.txt"
        with open(text_report_path, 'w', encoding='utf-8') as f:
            f.write("HAGBES FLEET DEPLOYMENT VALIDATION REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("VALIDATION RESULTS:\n")
            for check, result in self.validation_results.items():
                if check not in ['critical_errors', 'warnings', 'deployment_approved']:
                    status = "✅ PASS" if result else "❌ FAIL"
                    f.write(f"  {check}: {status}\n")
            
            f.write(f"\nDEPLOYMENT APPROVED: {'✅ YES' if self.validation_results['deployment_approved'] else '❌ NO'}\n\n")
            
            if self.validation_results['critical_errors']:
                f.write("CRITICAL ERRORS:\n")
                for error in self.validation_results['critical_errors']:
                    f.write(f"  ❌ {error}\n")
                f.write("\n")
            
            if self.validation_results['warnings']:
                f.write("WARNINGS:\n")
                for warning in self.validation_results['warnings']:
                    f.write(f"  ⚠️  {warning}\n")
        
        logger.info(f"Validation report generated: {text_report_path}")


def main():
    """Main deployment validation entry point."""
    if len(sys.argv) != 2:
        print("Usage: python validate_deployment.py <module_path>")
        sys.exit(1)
    
    module_path = sys.argv[1]
    validator = DeploymentValidator(module_path)
    results = validator.run_full_validation()
    
    if results['deployment_approved']:
        logger.info("🎉 DEPLOYMENT APPROVED - All validations passed")
        sys.exit(0)
    else:
        logger.error("🚫 DEPLOYMENT BLOCKED - Critical validation failures detected")
        logger.error(f"Critical errors: {len(results['critical_errors'])}")
        for error in results['critical_errors']:
            logger.error(f"  ❌ {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()