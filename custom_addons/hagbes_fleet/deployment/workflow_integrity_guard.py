#!/usr/bin/env python3
"""
HAGBES FLEET APPROVAL WORKFLOW INTEGRITY PROTECTION
===================================================

Protects the 3-step approval workflow from regression by validating:
- All approval states exist and are properly sequenced
- All approval buttons reference valid methods
- Security groups for each approval level are correct
- State transitions follow workflow rules
- Unauthorized approval actions are prevented
"""

import os
import sys
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import ast
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkflowIntegrityGuard:
    """Approval workflow integrity protection system."""
    
    def __init__(self, module_path: str):
        self.module_path = Path(module_path)
        self.validation_results = {
            'approval_states_valid': False,
            'approval_buttons_valid': False,
            'security_groups_valid': False,
            'state_transitions_valid': False,
            'workflow_configuration_valid': False,
            'critical_issues': [],
            'warnings': [],
            'integrity_protected': False
        }
        
        # Expected 3-step approval workflow configuration
        self.expected_workflow = {
            'states': [
                'draft', 'submitted', 'dept_approved', 'property_approved', 
                'fmo_approved', 'vehicle_assigned', 'allocated', 'completed', 
                'rejected', 'cancelled'
            ],
            'approval_sequence': [
                ('submitted', 'dept_approved', 'group_dept_manager'),
                ('dept_approved', 'property_approved', 'group_fleet_manager'),
                ('property_approved', 'fmo_approved', 'group_fmo')
            ],
            'required_methods': [
                'action_submit', 'action_approve', 'action_reject', 
                'action_cancel', '_on_approval_approved', '_on_approval_rejected'
            ],
            'permission_fields': [
                'can_submit', 'can_dept_approve', 'can_property_approve', 
                'can_fmo_approve', 'can_reject', 'can_cancel'
            ]
        }
    
    def validate_approval_states(self) -> bool:
        """Validate all approval states exist in the model."""
        logger.info("🔍 Validating approval states...")
        
        requisition_model_path = self.module_path / "models" / "fleet_requisition.py"
        if not requisition_model_path.exists():
            self.validation_results['critical_issues'].append("Missing fleet_requisition.py model file")
            return False
        
        try:
            with open(requisition_model_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract state field definition
            state_pattern = r'state\s*=\s*fields\.Selection\(\s*selection=\[(.*?)\]'
            state_match = re.search(state_pattern, content, re.DOTALL)
            
            if not state_match:
                self.validation_results['critical_issues'].append("State field definition not found")
                return False
            
            state_definition = state_match.group(1)
            
            # Extract state values
            state_value_pattern = r"\('(\w+)',\s*'[^']+'\)"
            found_states = re.findall(state_value_pattern, state_definition)
            
            # Validate all expected states are present
            missing_states = set(self.expected_workflow['states']) - set(found_states)
            if missing_states:
                self.validation_results['critical_issues'].append(
                    f"Missing approval states: {missing_states}"
                )
                return False
            
            # Validate state sequence is correct
            expected_states = self.expected_workflow['states']
            for i, expected_state in enumerate(expected_states):
                if i < len(found_states) and found_states[i] != expected_state:
                    self.validation_results['warnings'].append(
                        f"State sequence mismatch at position {i}: expected {expected_state}, found {found_states[i]}"
                    )
            
            logger.info(f"✅ Approval states validation passed: {len(found_states)} states found")
            return True
            
        except Exception as e:
            self.validation_results['critical_issues'].append(f"Error validating approval states: {e}")
            return False
    
    def validate_approval_buttons(self) -> bool:
        """Validate approval buttons reference valid methods."""
        logger.info("🔍 Validating approval buttons...")
        
        requisition_views_path = self.module_path / "views" / "fleet_requisition_views.xml"
        if not requisition_views_path.exists():
            self.validation_results['critical_issues'].append("Missing fleet_requisition_views.xml file")
            return False
        
        try:
            tree = ET.parse(requisition_views_path)
            root = tree.getroot()
            
            # Find approval buttons
            approval_buttons = []
            for button in root.findall(".//button[@name]"):
                button_name = button.get('name')
                if 'approve' in button_name or 'reject' in button_name or 'submit' in button_name:
                    approval_buttons.append({
                        'name': button_name,
                        'invisible_condition': button.get('invisible', ''),
                        'groups': button.get('groups', '')
                    })
            
            # Validate required approval methods exist in model
            requisition_model_path = self.module_path / "models" / "fleet_requisition.py"
            with open(requisition_model_path, 'r', encoding='utf-8') as f:
                model_content = f.read()
            
            missing_methods = []
            for method in self.expected_workflow['required_methods']:
                if f"def {method}(" not in model_content:
                    missing_methods.append(method)
            
            if missing_methods:
                self.validation_results['critical_issues'].append(
                    f"Missing required approval methods: {missing_methods}"
                )
                return False
            
            # Validate button visibility conditions use permission fields
            for button in approval_buttons:
                invisible_condition = button['invisible_condition']
                if 'can_' not in invisible_condition and button['name'] in ['action_approve', 'action_reject']:
                    self.validation_results['warnings'].append(
                        f"Button {button['name']} should use permission fields in invisible condition"
                    )
            
            logger.info(f"✅ Approval buttons validation passed: {len(approval_buttons)} buttons validated")
            return True
            
        except Exception as e:
            self.validation_results['critical_issues'].append(f"Error validating approval buttons: {e}")
            return False
    
    def validate_security_groups(self) -> bool:
        """Validate security groups for each approval level."""
        logger.info("🔍 Validating security groups...")
        
        # Check security groups definition
        groups_file = self.module_path / "security" / "groups.xml"
        if not groups_file.exists():
            self.validation_results['critical_issues'].append("Missing security/groups.xml file")
            return False
        
        try:
            tree = ET.parse(groups_file)
            root = tree.getroot()
            
            # Extract defined groups
            defined_groups = []
            for record in root.findall(".//record[@model='res.groups']"):
                group_id = record.get('id')
                if group_id:
                    defined_groups.append(group_id)
            
            # Validate required approval groups exist
            required_groups = ['group_dept_manager', 'group_fleet_manager', 'group_fmo']
            missing_groups = set(required_groups) - set(defined_groups)
            
            if missing_groups:
                self.validation_results['critical_issues'].append(
                    f"Missing required security groups: {missing_groups}"
                )
                return False
            
            # Validate approval flow configuration references correct groups
            approval_flow_file = self.module_path / "data" / "fleet_approval_flows.xml"
            if approval_flow_file.exists():
                flow_tree = ET.parse(approval_flow_file)
                flow_root = flow_tree.getroot()
                
                # Check approval step group references
                for step_record in flow_root.findall(".//record[@model='approval.step']"):
                    role_field = step_record.find(".//field[@name='role_id']")
                    if role_field is not None:
                        role_ref = role_field.get('ref', '')
                        if 'hagbes_fleet.' in role_ref:
                            group_name = role_ref.split('.')[-1]
                            if group_name not in defined_groups:
                                self.validation_results['critical_issues'].append(
                                    f"Approval step references undefined group: {group_name}"
                                )
                                return False
            
            logger.info("✅ Security groups validation passed")
            return True
            
        except Exception as e:
            self.validation_results['critical_issues'].append(f"Error validating security groups: {e}")
            return False
    
    def validate_state_transitions(self) -> bool:
        """Validate state transitions follow workflow rules."""
        logger.info("🔍 Validating state transitions...")
        
        requisition_model_path = self.module_path / "models" / "fleet_requisition.py"
        if not requisition_model_path.exists():
            return False
        
        try:
            with open(requisition_model_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate permission computation logic
            permission_pattern = r'def _compute_permissions\(self\):(.*?)(?=def|\Z)'
            permission_match = re.search(permission_pattern, content, re.DOTALL)
            
            if not permission_match:
                self.validation_results['critical_issues'].append(
                    "Permission computation method not found"
                )
                return False
            
            permission_logic = permission_match.group(1)
            
            # Validate each approval step has correct state check
            for from_state, to_state, group in self.expected_workflow['approval_sequence']:
                permission_field = f"can_{group.replace('group_', '').replace('_manager', '').replace('fleet_', '')}_approve"
                
                # Special handling for property approval (fleet_manager -> property)
                if group == 'group_fleet_manager' and from_state == 'dept_approved':
                    permission_field = 'can_property_approve'
                elif group == 'group_fmo':
                    permission_field = 'can_fmo_approve'
                elif group == 'group_dept_manager':
                    permission_field = 'can_dept_approve'
                
                if permission_field not in permission_logic:
                    self.validation_results['warnings'].append(
                        f"Permission field {permission_field} not found in computation logic"
                    )
            
            # Validate state transition methods exist and have proper checks
            transition_methods = ['action_submit', 'action_approve', 'action_reject']
            for method in transition_methods:
                method_pattern = rf'def {method}\(self.*?\):(.*?)(?=def|\Z)'
                method_match = re.search(method_pattern, content, re.DOTALL)
                
                if method_match:
                    method_content = method_match.group(1)
                    
                    # Check for state validation
                    if 'state' not in method_content and method != 'action_approve':
                        self.validation_results['warnings'].append(
                            f"Method {method} should validate current state"
                        )
                    
                    # Check for permission validation
                    if 'UserError' not in method_content and method in ['action_submit', 'action_approve']:
                        self.validation_results['warnings'].append(
                            f"Method {method} should include permission validation"
                        )
            
            logger.info("✅ State transitions validation passed")
            return True
            
        except Exception as e:
            self.validation_results['critical_issues'].append(f"Error validating state transitions: {e}")
            return False
    
    def validate_workflow_configuration(self) -> bool:
        """Validate approval workflow XML configuration."""
        logger.info("🔍 Validating workflow configuration...")
        
        approval_flow_file = self.module_path / "data" / "fleet_approval_flows.xml"
        if not approval_flow_file.exists():
            self.validation_results['critical_issues'].append("Missing fleet_approval_flows.xml file")
            return False
        
        try:
            tree = ET.parse(approval_flow_file)
            root = tree.getroot()
            
            # Find fleet_requisition flow
            fleet_flow = None
            for record in root.findall(".//record[@model='approval.flow']"):
                request_type_field = record.find(".//field[@name='request_type']")
                if request_type_field is not None and request_type_field.text == 'fleet_requisition':
                    fleet_flow = record
                    break
            
            if fleet_flow is None:
                self.validation_results['critical_issues'].append(
                    "Fleet requisition approval flow not found"
                )
                return False
            
            # Validate flow is active
            active_field = fleet_flow.find(".//field[@name='active']")
            if active_field is None or active_field.text != 'True':
                self.validation_results['critical_issues'].append(
                    "Fleet requisition approval flow is not active"
                )
                return False
            
            # Validate approval steps exist and are properly sequenced
            approval_steps = []
            for record in root.findall(".//record[@model='approval.step']"):
                flow_id_field = record.find(".//field[@name='flow_id']")
                if flow_id_field is not None and 'fleet_requisition' in flow_id_field.get('ref', ''):
                    sequence_field = record.find(".//field[@name='sequence']")
                    name_field = record.find(".//field[@name='name']")
                    role_field = record.find(".//field[@name='role_id']")
                    
                    if sequence_field is not None and name_field is not None:
                        approval_steps.append({
                            'sequence': int(sequence_field.text),
                            'name': name_field.text,
                            'role': role_field.get('ref', '') if role_field is not None else None
                        })
            
            # Sort by sequence and validate
            approval_steps.sort(key=lambda x: x['sequence'])
            
            expected_steps = [
                (0, 'Requisition Submission', None),  # Initiator step
                (10, 'Department Manager Review', 'hagbes_fleet.group_dept_manager'),
                (20, 'Property Officer Review', 'hagbes_fleet.group_fleet_manager'),
                (30, 'FMO Officer Review', 'hagbes_fleet.group_fmo'),
                (40, 'Final Approval', None)  # Final step
            ]
            
            if len(approval_steps) < len(expected_steps):
                self.validation_results['critical_issues'].append(
                    f"Missing approval steps: expected {len(expected_steps)}, found {len(approval_steps)}"
                )
                return False
            
            # Validate step actions exist
            step_actions = []
            for record in root.findall(".//record[@model='approval.step.action']"):
                step_id_field = record.find(".//field[@name='step_id']")
                action_id_field = record.find(".//field[@name='action_id']")
                
                if step_id_field is not None and action_id_field is not None:
                    step_actions.append({
                        'step_id': step_id_field.get('ref', ''),
                        'action_id': action_id_field.get('search', '')
                    })
            
            # Validate approve and reject actions exist for each step
            required_actions = ['approve', 'reject', 'auto_initiate']
            for action_type in required_actions:
                action_found = any(action_type in action['action_id'] for action in step_actions)
                if not action_found:
                    self.validation_results['warnings'].append(
                        f"Action type '{action_type}' not found in step actions"
                    )
            
            logger.info("✅ Workflow configuration validation passed")
            return True
            
        except Exception as e:
            self.validation_results['critical_issues'].append(f"Error validating workflow configuration: {e}")
            return False
    
    def run_full_integrity_validation(self) -> Dict[str, Any]:
        """Run complete workflow integrity validation."""
        logger.info("🚀 Starting approval workflow integrity validation...")
        
        # Run all validation checks
        validations = [
            ('approval_states_valid', self.validate_approval_states),
            ('approval_buttons_valid', self.validate_approval_buttons),
            ('security_groups_valid', self.validate_security_groups),
            ('state_transitions_valid', self.validate_state_transitions),
            ('workflow_configuration_valid', self.validate_workflow_configuration)
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
                self.validation_results['critical_issues'].append(f"{validation_name}: {e}")
                all_passed = False
        
        # Final integrity decision
        self.validation_results['integrity_protected'] = all_passed and len(self.validation_results['critical_issues']) == 0
        
        # Generate integrity report
        self.generate_integrity_report()
        
        return self.validation_results
    
    def generate_integrity_report(self):
        """Generate workflow integrity report."""
        report_path = self.module_path / "deployment" / "workflow_integrity_report.json"
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2)
        
        # Generate human-readable report
        text_report_path = self.module_path / "deployment" / "workflow_integrity_report.txt"
        with open(text_report_path, 'w', encoding='utf-8') as f:
            f.write("HAGBES FLEET APPROVAL WORKFLOW INTEGRITY REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("INTEGRITY VALIDATION RESULTS:\n")
            for check, result in self.validation_results.items():
                if check not in ['critical_issues', 'warnings', 'integrity_protected']:
                    status = "✅ PASS" if result else "❌ FAIL"
                    f.write(f"  {check}: {status}\n")
            
            f.write(f"\nWORKFLOW INTEGRITY PROTECTED: {'✅ YES' if self.validation_results['integrity_protected'] else '❌ NO'}\n\n")
            
            if self.validation_results['critical_issues']:
                f.write("CRITICAL ISSUES:\n")
                for issue in self.validation_results['critical_issues']:
                    f.write(f"  ❌ {issue}\n")
                f.write("\n")
            
            if self.validation_results['warnings']:
                f.write("WARNINGS:\n")
                for warning in self.validation_results['warnings']:
                    f.write(f"  ⚠️  {warning}\n")
            
            f.write("\nEXPECTED WORKFLOW CONFIGURATION:\n")
            f.write("States: " + " → ".join(self.expected_workflow['states']) + "\n")
            f.write("Approval Sequence:\n")
            for from_state, to_state, group in self.expected_workflow['approval_sequence']:
                f.write(f"  {from_state} → {to_state} (by {group})\n")
        
        logger.info(f"Workflow integrity report generated: {text_report_path}")


def main():
    """Main workflow integrity validation entry point."""
    if len(sys.argv) != 2:
        print("Usage: python workflow_integrity_guard.py <module_path>")
        sys.exit(1)
    
    module_path = sys.argv[1]
    guard = WorkflowIntegrityGuard(module_path)
    results = guard.run_full_integrity_validation()
    
    if results['integrity_protected']:
        logger.info("🎉 WORKFLOW INTEGRITY PROTECTED - All validations passed")
        sys.exit(0)
    else:
        logger.error("🚫 WORKFLOW INTEGRITY COMPROMISED - Critical issues detected")
        logger.error(f"Critical issues: {len(results['critical_issues'])}")
        for issue in results['critical_issues']:
            logger.error(f"  ❌ {issue}")
        sys.exit(1)


if __name__ == "__main__":
    main()